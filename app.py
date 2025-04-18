# app.py
import subprocess
import os
import tkinter as tk
from tkinter import messagebox, filedialog
import queue
import threading
import traceback
import logging
import time
from concurrent.futures import ThreadPoolExecutor

# 导入 UI 层
from ui import main_window
# 不再需要导入旧的 config_dialogs, 但需要新的统一窗口
from ui.config_dialogs import GeminiConfigWindow # 导入新的统一配置窗口
from ui.rtp_dialog import RTPSelectionWindow # 保留 RTP
from ui.dict_editor import DictEditorWindow # 保留字典编辑器

# 导入 Core 层
from core import config as cfg
from core.tasks import (
    initialize, rename, export, json_creation,
    dict_generation, translate, json_release, import_task,
    easy_mode_flow
)
from core.utils import text_processing

log = logging.getLogger(__name__)

class RPGTranslatorApp:
    """主应用程序类，负责协调 UI 和核心逻辑。"""

    def __init__(self, root):
        """
        初始化应用程序。

        Args:
            root (tk.Tk): Tkinter 的根窗口。
        """
        self.root = root
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.program_dir = os.path.dirname(os.path.abspath(__file__))
        self.works_dir = os.path.join(self.program_dir, "Works")
        self.config_file_path = os.path.join(self.program_dir, "app_config.json")
        self.config_manager = cfg.ConfigManager(self.config_file_path)
        # 加载配置时，ConfigManager 会自动处理新旧格式的合并和默认值填充
        self.config = self.config_manager.load_config()

        # --- 应用状态 ---
        self.game_path = tk.StringVar()
        self.is_processing = False
        self.current_task_thread = None
        self._stop_requested = False

        # --- 后台任务处理 ---
        self.message_queue = queue.Queue()
        # 主任务线程池保持不变，因为大部分任务还是串行的
        self.thread_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="MainTask")
        self.root.after(100, self._process_messages)

        # --- 初始化 UI ---
        # 将 self (App实例) 和 config 传递给 MainWindow
        self.main_window = main_window.MainWindow(self.root, self, self.config)

        initial_mode = self.config.get('selected_mode', 'easy')
        self.main_window.switch_to_mode(initial_mode)

        log.info("RPG 翻译助手应用程序已初始化。")
        self.log_message("程序已启动，请选择游戏目录", "normal")

    # --- UI 调用接口 ---

    def browse_game_path(self):
        """弹出目录选择对话框，更新游戏路径。"""
        # (保持不变)
        path = filedialog.askdirectory(title="选择游戏目录", parent=self.root)
        if path:
            lmt_path = os.path.join(path, "RPG_RT.lmt")
            if os.path.exists(lmt_path):
                self.game_path.set(path)
                self.log_message(f"已选择游戏目录: {path}")
                self.update_status("游戏目录已选择，可以开始操作。")
            else:
                messagebox.showerror("路径无效", "选择的目录不是有效的 RPG Maker 2000/2003 游戏目录（未找到 RPG_RT.lmt）。", parent=self.root)
                self.log_message("选择了无效的游戏目录。", "error")

    def get_game_path(self):
        """获取当前游戏路径。"""
        return self.game_path.get()

    def start_task(self, task_name, mode='pro'):
        """
        根据任务名称启动相应的后台任务。

        Args:
            task_name (str): 任务的唯一标识符。
            mode (str): 当前的操作模式 ('easy' 或 'pro')。
        """
        if self.is_processing:
            self.log_message("请等待当前操作完成。", "error")
            messagebox.showwarning("操作繁忙", "请等待当前操作完成后再试。", parent=self.root)
            return

        # --- 配置和路径检查 ---
        # configure_gemini_unified 不依赖 game_path
        if task_name not in ['configure_gemini_unified', 'select_rtp']:
             if not self._check_game_path_set(): return

        # --- 准备任务参数 ---
        task_func = None
        task_args = []
        task_kwargs = {}

        game_path = self.get_game_path() # 获取当前游戏路径
        pro_config = self.config.get('pro_mode_settings', {})
        rtp_options = pro_config.get('rtp_options', {'2000': True, '2000en': False, '2003': False, '2003steam': False})
        export_encoding = pro_config.get('export_encoding', '932')
        import_encoding = pro_config.get('import_encoding', '936')
        write_log_rename = pro_config.get('write_log_rename', True)
        # 这两个配置现在都与 Gemini 相关
        world_dict_config = self.config.get('world_dict_config', {})
        translate_config = self.config.get('translate_config', {})

        # 根据 task_name 选择任务函数和参数
        if task_name == 'initialize':
            task_func = initialize.run_initialize
            task_args = [game_path, rtp_options, self.message_queue]
        elif task_name == 'rename':
            task_func = rename.run_rename
            task_args = [game_path, self.program_dir, write_log_rename, self.message_queue]
        elif task_name == 'export':
            task_func = export.run_export
            task_args = [game_path, export_encoding, self.message_queue]
        elif task_name == 'create_json':
            task_func = json_creation.run_create_json
            task_args = [game_path, self.works_dir, self.message_queue]
        elif task_name == 'generate_dictionary':
             # 检查 Gemini Key 是否配置
             if not world_dict_config.get("api_key"):
                 messagebox.showerror("配置缺失", "请先在 Gemini 配置中填写 API Key。", parent=self.root)
                 return
             task_func = dict_generation.run_generate_dictionary
             task_args = [game_path, self.works_dir, world_dict_config, self.message_queue]
        elif task_name == 'translate':
             # 检查 Gemini Key 是否配置
             if not translate_config.get("api_key"):
                 messagebox.showerror("配置缺失", "请先在 Gemini 配置中填写 API Key。", parent=self.root)
                 return
             task_func = translate.run_translate # 使用更新后的 translate.py
             task_args = [game_path, self.works_dir, translate_config, world_dict_config, self.message_queue]
        elif task_name == 'release_json':
            # (查找和选择 JSON 文件的逻辑保持不变)
            json_files = self._find_translated_json_files()
            if not json_files: messagebox.showerror("错误", f"未找到翻译后的 JSON 文件。", parent=self.root); return
            selected_json_path = None
            if len(json_files) == 1: selected_json_path = json_files[0]
            else:
                selected_filename = self.main_window.show_file_selection_dialog("选择翻译文件", "请选择要导入的翻译 JSON 文件:", [os.path.basename(p) for p in json_files])
                if selected_filename: selected_json_path = os.path.join(self._get_translated_dir(), selected_filename)
                else: self.log_message("取消选择翻译文件。", "warning"); return
            if selected_json_path:
                task_func = json_release.run_release_json
                task_args = [game_path, self.works_dir, selected_json_path, self.message_queue]
            else: return
        elif task_name == 'import':
            task_func = import_task.run_import
            task_args = [game_path, import_encoding, self.message_queue]
        elif task_name == 'easy_flow':
             # 轻松模式检查 Gemini Key
             # 注意: translate_config 和 world_dict_config 理论上应共享同一个 key
             api_key = world_dict_config.get("api_key") or translate_config.get("api_key")
             if not api_key:
                 messagebox.showerror("配置缺失", "请先在 Gemini 配置中填写 API Key。", parent=self.root)
                 return
             # 更新后的 easy_mode_flow 需要使用 Gemini 配置
             task_func = easy_mode_flow.run_easy_flow
             task_args = [
                 game_path, self.program_dir, self.works_dir,
                 rtp_options, export_encoding, import_encoding,
                 world_dict_config, # 传递 Gemini 字典配置
                 translate_config, # 传递 Gemini 翻译配置
                 write_log_rename,
                 self.message_queue
             ]
        elif task_name == 'start_game':
             self._start_game(); return
        elif task_name == 'edit_dictionary':
             self._open_dict_editor(); return
        elif task_name == 'configure_gemini_unified': # 使用新的统一配置任务名
             self._open_gemini_config_unified(); return
        # 移除 configure_deepseek 的处理
        elif task_name == 'select_rtp':
             self._open_rtp_selection(); return
        else:
            self.log_message(f"未知的任务名称: {task_name}", "error")
            messagebox.showerror("错误", f"无法识别的操作: {task_name}", parent=self.root)
            return

        if task_func:
            self._run_task_in_thread(task_func, task_args, task_kwargs, task_name, mode)

    def save_pro_mode_settings(self, settings):
        """保存专业模式的设置到配置中。"""
        # (保持不变)
        if 'pro_mode_settings' not in self.config: self.config['pro_mode_settings'] = {}
        self.config['pro_mode_settings'].update(settings)
        self.save_config()

    def save_config(self):
        """保存当前应用配置。"""
        # (保持不变)
        try:
            self.config['selected_mode'] = self.main_window.get_current_mode()
            # ConfigManager 会处理保存
            if self.config_manager.save_config(self.config):
                 self.log_message("配置已保存。", "success")
                 return True
            else:
                 self.log_message("保存配置失败 (ConfigManager 返回 False)。", "error")
                 messagebox.showerror("保存失败", "无法将配置写入文件，请检查日志。", parent=self.root)
                 return False
        except Exception as e:
            log.exception("保存配置时发生错误。")
            self.log_message(f"保存配置失败: {e}", "error")
            messagebox.showerror("保存失败", f"无法保存配置文件。\n错误: {e}", parent=self.root)
            return False

    def log_message(self, message, level="normal"):
        """将消息记录到 UI 日志区域。"""
        # (保持不变)
        if hasattr(self, 'main_window') and self.main_window: self.main_window.add_log(message, level)
        else: print(f"[{level.upper()}] {message}")

    def update_status(self, message):
        """更新 UI 状态栏文本。"""
        # (保持不变)
        if hasattr(self, 'main_window') and self.main_window: self.main_window.update_status(message)

    def update_easy_mode_status(self, message):
        """更新轻松模式状态标签。"""
        # (保持不变)
        if hasattr(self, 'main_window') and self.main_window: self.main_window.update_easy_status(message)

    def update_easy_mode_progress(self, value):
        """更新轻松模式进度条。"""
        # (保持不变)
        if hasattr(self, 'main_window') and self.main_window: self.main_window.update_easy_progress(value)

    def set_processing_state(self, processing):
        """设置应用的繁忙状态，并更新 UI 控件的可用性。"""
        # (保持不变)
        self.is_processing = processing
        if hasattr(self, 'main_window') and self.main_window: self.main_window.set_controls_enabled(not processing)

    # --- 内部方法 ---

    def _get_work_subfolder(self):
        """获取当前游戏对应的 Works 子目录名。"""
        # (保持不变)
        game_path = self.get_game_path(); 
        if not game_path: 
            return None
        game_folder_name = text_processing.sanitize_filename(os.path.basename(game_path)); return game_folder_name or "UntitledGame"

    def _get_translated_dir(self):
        """获取当前游戏翻译文件存放目录的完整路径。"""
        # (保持不变)
        subfolder = self._get_work_subfolder(); 
        if not subfolder: 
            return None
        return os.path.join(self.works_dir, subfolder, "translated")

    def _find_translated_json_files(self):
        """查找当前游戏已翻译的 JSON 文件列表。"""
        # (保持不变)
        translated_dir = self._get_translated_dir(); 
        if not translated_dir or not os.path.isdir(translated_dir): 
            return []
        try: 
            return [os.path.join(translated_dir, f) for f in os.listdir(translated_dir) if f.lower().endswith('.json')]
        except OSError as e: log.error(f"无法读取翻译目录 {translated_dir}: {e}"); return []

    def _check_game_path_set(self):
        """检查游戏路径是否已设置，如果未设置则显示错误。"""
        # (保持不变)
        if not self.get_game_path():
            self.log_message("请先选择有效的游戏目录。", "error"); messagebox.showerror("错误", "请先选择一个有效的 RPG Maker 游戏目录。", parent=self.root); return False
        return True

    def _run_task_in_thread(self, task_func, args, kwargs, task_name="后台任务", mode='pro'):
        """在后台线程中运行给定的任务函数。"""
        # (保持不变)
        self.set_processing_state(True); self.update_status(f"正在执行: {task_name}..."); self._stop_requested = False
        def wrapper():
            task_start_time = time.time()
            try: task_func(*args, **kwargs)
            except Exception as e:
                log.exception(f"任务 '{task_name}' 执行期间发生未捕获的严重错误。")
                self.message_queue.put(("error", f"任务 '{task_name}' 失败: {traceback.format_exc()}"))
                self.message_queue.put(("status", f"{task_name} 执行失败"))
            finally:
                elapsed = time.time() - task_start_time; log.info(f"任务 '{task_name}' 线程执行完毕，耗时: {elapsed:.2f} 秒。")
                self.root.after(0, lambda: self.set_processing_state(False))
                self.current_task_thread = None
        self.current_task_thread = threading.Thread(target=wrapper, daemon=True); self.current_task_thread.start()

    def _process_messages(self):
        """处理来自后台任务的消息队列。"""
        # (保持不变)
        try:
            while True:
                message = self.message_queue.get_nowait()
                msg_type, content = message
                if msg_type == "log": level, text = content; self.log_message(text, level)
                elif msg_type == "status": self.update_status(content)
                elif msg_type == "success": self.log_message(content, "success")
                elif msg_type == "error": self.log_message(content, "error")
                elif msg_type == "progress": self.update_easy_mode_progress(content) # Assume progress is only for easy mode now
                elif msg_type == "easy_status": self.update_easy_mode_status(content)
                elif msg_type == "done":
                    self.log_message("后台任务处理完成。", "normal")
                    current_mode = self.main_window.get_current_mode()
                    if current_mode == 'easy' and not self.is_processing:
                        last_status = self.main_window.get_status() # Need MainWindow.get_status()
                        if "失败" in last_status or "中止" in last_status or "错误" in last_status: self.update_easy_mode_status("轻松模式执行完毕（有错误）。")
                        else: self.update_easy_mode_status("轻松模式执行成功！")
                self.message_queue.task_done()
        except queue.Empty: pass
        except Exception as e: log.exception(f"处理消息队列时出错: {e}")
        finally: self.root.after(100, self._process_messages)

    def _start_game(self):
        """启动游戏。"""
        # (保持不变)
        if not self._check_game_path_set(): return; game_path = self.get_game_path()
        player_exe = os.path.join(game_path, "Player.exe"); rpg_rt_exe = os.path.join(game_path, "RPG_RT.exe")
        exe_to_run = player_exe if os.path.exists(player_exe) else (rpg_rt_exe if os.path.exists(rpg_rt_exe) else None)
        if not exe_to_run: messagebox.showerror("启动失败", f"未找到 Player.exe 或 RPG_RT.exe。", parent=self.root); self.log_message("无法启动游戏", "error"); return
        self.log_message(f"尝试启动游戏: {exe_to_run}");
        try: subprocess.Popen([exe_to_run], cwd=game_path); self.log_message("游戏已启动。", "success")
        except Exception as e: log.exception(f"启动游戏失败: {e}"); messagebox.showerror("启动失败", f"启动游戏出错：\n{e}", parent=self.root); self.log_message(f"启动游戏失败: {e}", "error")

    def _open_dict_editor(self):
        """打开世界观字典编辑器。"""
        # (保持不变)
        if not self._check_game_path_set(): return
        current_game_path = self.get_game_path()
        try: DictEditorWindow(parent=self.root, app_controller=self, works_dir=self.works_dir, game_path=current_game_path); self.log_message("字典编辑器已打开。", "normal")
        except Exception as e: log.exception("打开字典编辑器出错。"); messagebox.showerror("错误", f"无法打开字典编辑器:\n{e}", parent=self.root); self.log_message(f"打开字典编辑器失败: {e}", "error")

    def _open_gemini_config_unified(self): # 新方法：打开统一的 Gemini 配置窗口
        """打开统一的 Gemini 配置窗口。"""
        # 传递 world_dict_config 和 translate_config 给新窗口
        GeminiConfigWindow(
            parent=self.root,
            app_controller=self,
            world_dict_config=self.config['world_dict_config'],
            translate_config=self.config['translate_config']
        )
        self.log_message("Gemini 配置窗口已打开。", "normal")

    # 移除旧的 _open_gemini_config 和 _open_deepseek_config 方法
    # def _open_gemini_config(self): ...
    # def _open_deepseek_config(self): ...

    def _open_rtp_selection(self):
        """打开 RTP 选择窗口。"""
        # (保持不变)
        pro_settings = self.config.setdefault('pro_mode_settings', {})
        rtp_options = pro_settings.setdefault('rtp_options', {'2000': True, '2000en': False, '2003': False, '2003steam': False})
        RTPSelectionWindow(self.root, self, rtp_options)
        if hasattr(self.main_window, 'update_rtp_button_text'): self.main_window.update_rtp_button_text()

    def _on_close(self):
        """应用程序关闭时的处理。"""
        # (保持不变)
        log.info("应用程序正在关闭...")
        if self.is_processing:
            if messagebox.askyesno("确认退出", "有后台任务正在运行，确定要强制退出吗？", parent=self.root):
                log.warning("用户强制退出，后台任务可能未完成。")
                # 尝试关闭线程池，但不保证任务能优雅停止
                self.thread_pool.shutdown(wait=False, cancel_futures=True) # 尝试取消待处理任务
                self.root.destroy()
            else: return
        else:
             self.save_config()
             self.thread_pool.shutdown(wait=True)
             self.root.destroy()