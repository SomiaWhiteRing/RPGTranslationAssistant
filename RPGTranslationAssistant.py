import os
import shutil
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
import re
import csv
import io
import time
import datetime
import threading
import queue
import traceback
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
from google import genai

class RPGTranslationAssistant:
    def __init__(self, root):
        self.root = root
        self.root.title("RPG Maker 翻译助手")
        # self.root.geometry("600x750") # 初始大小由模式决定
        self.root.resizable(True, True)

        # 设置程序路径
        self.program_dir = os.path.dirname(os.path.abspath(__file__))
        self.rpgrewriter_path = os.path.join(self.program_dir, "modules/RPGRewriter", "RPGRewriter.exe")
        self.easyrpg_path = os.path.join(self.program_dir, "modules/EasyRPG")
        self.rtpcollection_path = os.path.join(self.program_dir, "modules/RTPCollection")
        self.works_dir = os.path.join(self.program_dir, "Works")

        # 创建Works目录（如果不存在）
        if not os.path.exists(self.works_dir):
            os.makedirs(self.works_dir)

        # 游戏路径
        self.game_path = tk.StringVar()

        # 编码选项 (专业模式)
        self.export_encoding = tk.StringVar(value="932")
        self.import_encoding = tk.StringVar(value="936")

        # RTP选项 (专业模式)
        self.rtp_2000 = tk.BooleanVar(value=True)
        self.rtp_2000en = tk.BooleanVar(value=False)
        self.rtp_2003 = tk.BooleanVar(value=False)
        self.rtp_2003steam = tk.BooleanVar(value=False)

        # 用于线程间通信
        self.message_queue = queue.Queue()
        self.is_processing = False

        # --- 新增：模式选择 ---
        self.selected_mode = tk.StringVar(value="easy") # 默认轻松模式

        # --- 新增：轻松模式相关变量 ---
        self.easy_mode_steps = 8 # 初始化, 重命名, 导出, 创建JSON, 生成字典, 翻译, 释放JSON, 导入
        self.easy_mode_progress_var = tk.DoubleVar(value=0.0)
        self.easy_mode_status_var = tk.StringVar(value="选择游戏目录后点击“开始翻译”")

        # 创建UI
        self.create_ui()
        self.log("程序已启动，请选择游戏目录")

        # --- 配置文件路径和加载 ---
        self.config_file_path = os.path.join(self.program_dir, "app_config.json")
        self.load_config() # 加载现有配置或设置默认值

        # --- 选择初始标签 ---
        initial_mode = self.selected_mode.get()
        if initial_mode == "easy":
            self.functions_notebook.select(self.easy_mode_frame)
        else:
            self.functions_notebook.select(self.pro_mode_frame)

        # 根据加载的模式设置初始窗口大小
        self._update_window_size(self.selected_mode.get())

        # 启动消息处理器
        self.root.after(100, self.process_messages)

    def load_config(self):
        """加载配置文件，如果不存在则使用默认值"""
        # --- 默认配置 ---
        default_world_dict_config = {
            "api_key": "",
            "model": "gemini-2.5-pro-exp-03-25", # 更新为推荐模型
            "prompt": """请分析提供的游戏文本，提取其中反复出现的名词。提取规则如下：
1.  类别限定为：地点、角色、生物、组织、物品。
2.  输出格式为严格的CSV，包含四列：原文,译文,类别,描述。请确保每个字段都被双引号包围，字段内的逗号和换行符需要正确转义。
3.  提取的名词在原文中至少出现两次。
4.  忽略单个汉字、假名或字母。忽略常见的、过于笼统的词汇（例如：门、钥匙、药水、史莱姆、哥布林等，除非它们有特殊的前缀或后缀）。
5.  译文请根据上下文推断一个合适的简体中文翻译。
6.  对于"角色"类别，请在"描述"列中尽可能包含角色的【年龄/性别/性格/口吻】等信息，如果没有明确信息则留空。其他类别的"描述"列可以留空。
7.  CSV首行不需要表头。

以下是需要分析的游戏文本内容：
{game_text}"""
        }
        default_translate_config = {
            "api_url": "https://ark.cn-beijing.volces.com/api/v3", # 修正为DeepSeek官方API地址
            "api_key": "",
            "model": "deepseek-v3-250324", # 修正为正确的模型名称
            "batch_size": 10,
            "context_lines": 10,
            "concurrency": 16,
            "source_language": "日语",  # 新增：源语言配置
            "target_language": "简体中文",  # 新增：目标语言配置
            "prompt_template": """你是一名专业的翻译家，你的任务是把{source_language}文本翻译成{target_language}，逐行翻译，不要合并，保留文本中序号、标记符、占位符、换行符等特殊内容，保持原来的格式。

### 翻译原则
忠实准确地进行翻译。原作是伟大艺术作品，允许使用直白或粗俗的描述，不应随意删减或篡改，不应回避或淡化，以保持作品的原貌。

{glossary_section}

{context_section}

### 特殊字符处理规则
- 你在原文中可能会看到特殊字符，如 , , 。
- 这些是重要的占位符，**必须**在译文中原样保留，**禁止**修改、删除或翻译它们。

### 这是你接下来的翻译任务，原文文本如下
<textarea>
{batch_text}
</textarea>

### 请以textarea标签输出译文
<textarea>
1.{target_language}文本
</textarea>"""
        }
        default_selected_mode = "easy" # 默认模式

        try:
            if os.path.exists(self.config_file_path):
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    loaded_configs = json.load(f)
                # 使用加载的配置更新默认配置，确保新旧键都存在
                self.world_dict_config = default_world_dict_config.copy()
                self.world_dict_config.update(loaded_configs.get("world_dict_config", {}))

                self.translate_config = default_translate_config.copy()
                self.translate_config.update(loaded_configs.get("translate_config", {}))

                # 加载模式选择
                self.selected_mode.set(loaded_configs.get("selected_mode", default_selected_mode))

                self.log("已成功加载保存的配置。")
            else:
                self.world_dict_config = default_world_dict_config
                self.translate_config = default_translate_config
                self.selected_mode.set(default_selected_mode)
                self.log("未找到配置文件，使用默认配置。")

        except (json.JSONDecodeError, IOError, Exception) as e:
            self.log(f"加载配置失败: {e}，将使用默认配置。", "error")
            self.world_dict_config = default_world_dict_config
            self.translate_config = default_translate_config
            self.selected_mode.set(default_selected_mode)

    def save_config(self):
        """保存当前配置到文件"""
        try:
            configs_to_save = {
                "world_dict_config": self.world_dict_config,
                "translate_config": self.translate_config,
                "selected_mode": self.selected_mode.get() # 保存当前选择的模式
            }
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(configs_to_save, f, indent=4, ensure_ascii=False)
            self.log("配置已成功保存。", "success")
        except (IOError, Exception) as e:
            self.log(f"保存配置失败: {e}", "error")
            messagebox.showerror("保存失败", f"无法保存配置文件到:\n{self.config_file_path}\n错误: {e}")

    def create_ui(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 游戏路径选择 (保持不变)
        path_frame = ttk.LabelFrame(main_frame, text="游戏路径", padding="5")
        path_frame.pack(fill=tk.X, pady=5, side=tk.TOP) # 明确放到顶部
        ttk.Button(path_frame, text="浏览...", command=self.browse_game_path).pack(side=tk.RIGHT, padx=5, pady=5)
        ttk.Entry(path_frame, textvariable=self.game_path, width=70).pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)
        
        # 状态栏 (先定义，放到最下面)
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=5, side=tk.BOTTOM)
        self.status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor=tk.W)
        status_label.pack(fill=tk.X)

        # 日志区域 (放到状态栏上面)
        log_frame = ttk.LabelFrame(main_frame, text="操作日志", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5, side=tk.BOTTOM) # 明确放到下面，并扩展
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, width=80, height=10) # 高度可以根据需要调整
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.log_text.tag_configure("normal", foreground="black")
        self.log_text.tag_configure("success", foreground="blue")
        self.log_text.tag_configure("error", foreground="red")
        self.log_text.config(state=tk.DISABLED)

        # 功能区 Notebook (放到日志区上面, 路径选择下面)
        self.functions_notebook = ttk.Notebook(main_frame)
        self.functions_notebook.pack(fill=tk.X, expand=False, pady=5, side=tk.TOP) # 不垂直扩展，只水平填充
        self.functions_notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)

        # --- 轻松模式框架 ---
        # 注意：框架先定义，但添加到Notebook在后面
        self.easy_mode_frame = ttk.Frame(self.functions_notebook, padding="10")

        # 轻松模式按钮容器 (用于居中)
        easy_button_container = ttk.Frame(self.easy_mode_frame)
        easy_button_container.pack(pady=10) # 减少垂直外边距

        ttk.Button(easy_button_container, text="Gemini配置", command=self.open_world_dict_config, width=15).pack(side=tk.LEFT, padx=10)
        ttk.Button(easy_button_container, text="Deepseek配置", command=self.open_translate_config, width=15).pack(side=tk.LEFT, padx=10)
        ttk.Button(easy_button_container, text="开始翻译", command=self.start_easy_translation, width=15).pack(side=tk.LEFT, padx=10)
        ttk.Button(easy_button_container, text="开始游戏", command=self.start_game, width=15).pack(side=tk.LEFT, padx=10)

        # 轻松模式进度条
        self.easy_progressbar = ttk.Progressbar(self.easy_mode_frame, variable=self.easy_mode_progress_var, maximum=100)
        self.easy_progressbar.pack(fill=tk.X, padx=10, pady=(10, 5))

        # 轻松模式状态标签
        self.easy_status_label = ttk.Label(self.easy_mode_frame, textvariable=self.easy_mode_status_var)
        self.easy_status_label.pack(fill=tk.X, padx=10, pady=(0, 10))


        # --- 专业模式框架 ---
        # 注意：框架先定义，但添加到Notebook在后面
        self.pro_mode_frame = ttk.Frame(self.functions_notebook, padding="5")
        functions_frame_pro = self.pro_mode_frame # 使用 pro_mode_frame 作为容器

        # --- 0. 初始化 (放入专业模式) ---
        init_frame = ttk.Frame(functions_frame_pro)
        init_frame.pack(fill=tk.X, pady=2) # 减少专业模式内部垂直间距
        ttk.Label(init_frame, text="0. 初始化", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(init_frame, text="复制EasyRPG/RTP并转换编码").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(init_frame, text="执行", command=self.initialize_game).pack(side=tk.RIGHT, padx=5)
        self.rtp_button_text = tk.StringVar() # 初始文本在下面更新
        ttk.Button(init_frame, textvariable=self.rtp_button_text, command=self.show_rtp_selection).pack(side=tk.RIGHT, padx=5)
        self._update_rtp_button_text() # 初始化时更新按钮文本

        # --- 1. 重写文件名 (放入专业模式) ---
        rename_frame = ttk.Frame(functions_frame_pro)
        rename_frame.pack(fill=tk.X, pady=2)
        ttk.Label(rename_frame, text="1. 重写文件名", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(rename_frame, text="非ASCII文件名转Unicode").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(rename_frame, text="执行", command=self.rename_files).pack(side=tk.RIGHT, padx=5)
        self.write_log_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(rename_frame, text="输出日志", variable=self.write_log_var).pack(side=tk.RIGHT, padx=5)

        # --- 2. 导出文本 (放入专业模式) ---
        export_frame = ttk.Frame(functions_frame_pro)
        export_frame.pack(fill=tk.X, pady=2)
        ttk.Label(export_frame, text="2. 导出文本", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(export_frame, text="导出文本到StringScripts").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(export_frame, text="执行", command=self.export_text).pack(side=tk.RIGHT, padx=5)
        encoding_options = [
            ("日语 (Shift-JIS)", "932"), ("中文简体 (GBK)", "936"), ("中文繁体 (Big5)", "950"),
            ("韩语 (EUC-KR)", "949"), ("泰语", "874"), ("拉丁语系 (西欧)", "1252"),
            ("东欧", "1250"), ("西里尔字母", "1251")
        ]
        export_encoding_combobox = ttk.Combobox(export_frame, textvariable=self.export_encoding, state="readonly", width=20)
        export_encoding_combobox['values'] = [f"{name} - {code}" for name, code in encoding_options]
        current_export_code = self.export_encoding.get()
        export_index = next((i for i, (_, code) in enumerate(encoding_options) if code == current_export_code), 0)
        export_encoding_combobox.current(export_index)
        export_encoding_combobox.pack(side=tk.RIGHT, padx=5)
        ttk.Label(export_frame, text="编码:").pack(side=tk.RIGHT, padx=5)

        # --- 3. 制作JSON文件 (放入专业模式) ---
        transjson_create_frame = ttk.Frame(functions_frame_pro)
        transjson_create_frame.pack(fill=tk.X, pady=2)
        ttk.Label(transjson_create_frame, text="3. 制作JSON文件", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(transjson_create_frame, text="StringScripts文本压缩为JSON").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(transjson_create_frame, text="执行", command=self.create_transjson_files).pack(side=tk.RIGHT, padx=5)

        # --- 4. 生成世界观字典 (放入专业模式) ---
        gen_dict_frame = ttk.Frame(functions_frame_pro)
        gen_dict_frame.pack(fill=tk.X, pady=2)
        ttk.Label(gen_dict_frame, text="4. 生成世界观字典", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(gen_dict_frame, text="Gemini API从JSON生成字典").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(gen_dict_frame, text="执行", command=self.generate_world_dict).pack(side=tk.RIGHT, padx=5)
        ttk.Button(gen_dict_frame, text="调整字典", command=self.edit_world_dict).pack(side=tk.RIGHT, padx=5)
        ttk.Button(gen_dict_frame, text="配置", command=self.open_world_dict_config).pack(side=tk.RIGHT, padx=5)

        # --- 5. 翻译JSON文件 (放入专业模式) ---
        trans_json_frame = ttk.Frame(functions_frame_pro)
        trans_json_frame.pack(fill=tk.X, pady=2)
        ttk.Label(trans_json_frame, text="5. 翻译JSON文件", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(trans_json_frame, text="DeepSeek API翻译JSON").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(trans_json_frame, text="执行", command=self.translate_json_file).pack(side=tk.RIGHT, padx=5)
        ttk.Button(trans_json_frame, text="配置", command=self.open_translate_config).pack(side=tk.RIGHT, padx=5)

        # --- 6. 释放JSON文件 (放入专业模式) ---
        transjson_release_frame = ttk.Frame(functions_frame_pro)
        transjson_release_frame.pack(fill=tk.X, pady=2)
        ttk.Label(transjson_release_frame, text="6. 释放JSON文件", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(transjson_release_frame, text="翻译后JSON释放到StringScripts").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(transjson_release_frame, text="执行", command=self.release_transjson_files).pack(side=tk.RIGHT, padx=5)

        # --- 7. 导入文本 (放入专业模式) ---
        import_frame = ttk.Frame(functions_frame_pro)
        import_frame.pack(fill=tk.X, pady=2)
        ttk.Label(import_frame, text="7. 导入文本", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(import_frame, text="StringScripts文本导入游戏").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(import_frame, text="执行", command=self.import_text).pack(side=tk.RIGHT, padx=5)
        import_encoding_combobox = ttk.Combobox(import_frame, textvariable=self.import_encoding, state="readonly", width=20)
        import_encoding_combobox['values'] = [f"{name} - {code}" for name, code in encoding_options]
        current_import_code = self.import_encoding.get()
        import_index = next((i for i, (_, code) in enumerate(encoding_options) if code == current_import_code), 1) # 默认中文
        import_encoding_combobox.current(import_index)
        import_encoding_combobox.pack(side=tk.RIGHT, padx=5)
        ttk.Label(import_frame, text="编码:").pack(side=tk.RIGHT, padx=5)

        # --- 将模式框架添加到Notebook ---
        # 必须在Notebook pack之后添加
        self.functions_notebook.add(self.easy_mode_frame, text="轻松模式")
        self.functions_notebook.add(self.pro_mode_frame, text="专业模式")
    
    def on_tab_change(self, event):
        """处理Notebook标签切换事件"""
        selected_tab_text = self.functions_notebook.tab(self.functions_notebook.select(), "text")
        new_mode = "easy" if selected_tab_text == "轻松模式" else "pro"
        if new_mode != self.selected_mode.get():
            self.selected_mode.set(new_mode)
            self.log(f"切换到 {selected_tab_text}")
            self._update_window_size(new_mode)
            # 可以在这里保存配置，如果希望每次切换都保存的话
            self.save_config()

    def _update_window_size(self, mode):
        """根据模式调整窗口高度"""
        current_width = self.root.winfo_width()
        target_width = max(current_width, 600) # 确保宽度不小于600

        if mode == "easy":
            new_height = 450 # 轻松模式高度
        else: # pro mode
            new_height = 750 # 专业模式高度

        # 尝试平滑调整大小（可能效果不明显）
        # self.root.geometry(f"{target_width}x{new_height}+{self.root.winfo_x()}+{self.root.winfo_y()}")
        # 使用 update_idletasks 确保几何计算准确
        self.root.update_idletasks()
        self.root.geometry(f"{target_width}x{new_height}")
        # 调整功能区框架的扩展行为
        # self.functions_notebook.pack_configure(expand=(mode == 'pro')) # 专业模式下扩展填充

    # --- 日志和状态更新方法 ---
    def log(self, message, level="normal"):
        self.log_text.config(state=tk.NORMAL)
        timestamp = datetime.datetime.now().strftime("[%H:%M:%S] ")
        self.log_text.insert(tk.END, timestamp + message + "\n", level)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update()

    def show_error(self, message):
        self.log(message, "error")

    def show_success(self, message):
        self.log(message, "success")

    def browse_game_path(self):
        path = filedialog.askdirectory(title="选择游戏目录")
        if path:
            self.game_path.set(path)
            self.log(f"已选择游戏目录: {path}")

    def update_status(self, message):
        self.status_var.set(message)
        self.log(message)
        self.root.update()

    def check_game_path(self):
        game_path = self.game_path.get()
        if not game_path:
            self.show_error("请先选择游戏目录")
            return False
        lmt_path = os.path.join(game_path, "RPG_RT.lmt")
        if not os.path.exists(lmt_path):
            self.show_error("选择的目录不是有效的RPG Maker游戏目录（未找到RPG_RT.lmt）")
            return False
        return True

    # --- 线程通信方法 ---
    def process_messages(self):
        try:
            while True:
                message = self.message_queue.get_nowait()
                message_type, content = message
                if message_type == "log":
                    level, text = content
                    self.log(text, level)
                elif message_type == "status":
                    self.status_var.set(content) # 更新底部状态栏
                elif message_type == "success":
                    self.show_success(content)
                elif message_type == "error":
                    self.show_error(content)
                elif message_type == "done":
                    self.is_processing = False
                    # 如果当前是轻松模式，并且没有错误，可以重置进度条？或者保持完成状态
                    # if self.selected_mode.get() == 'easy' and not self.status_var.get().startswith("Error"):
                    #     pass # 保留 100%
                # --- 新增：处理轻松模式进度 ---
                elif message_type == "progress":
                    # 确保进度条控件存在
                    if hasattr(self, 'easy_progressbar') and self.easy_progressbar.winfo_exists():
                        self.easy_mode_progress_var.set(content)
                # --- 新增：处理轻松模式状态标签 ---
                elif message_type == "easy_status":
                     # 确保状态标签控件存在
                    if hasattr(self, 'easy_status_label') and self.easy_status_label.winfo_exists():
                        self.easy_mode_status_var.set(content)

                self.message_queue.task_done()
        except queue.Empty:
            pass
        finally: # 使用 finally 确保 after 总能被调用
            self.root.after(100, self.process_messages) # 保持循环检查

    def thread_log(self, message, level="normal"):
        self.message_queue.put(("log", (level, message)))

    def thread_update_status(self, message):
        self.message_queue.put(("status", message))

    def thread_show_success(self, message):
        self.message_queue.put(("success", message))

    def thread_show_error(self, message):
        self.message_queue.put(("error", message))

    def run_in_thread(self, target_func, *args, **kwargs):
        if self.is_processing:
            self.log("请等待当前操作完成", "error")
            return
        self.is_processing = True
        def wrapper():
            try:
                target_func(*args, **kwargs)
            except Exception as e:
                self.message_queue.put(("error", f"操作过程中出错: {str(e)}\n{traceback.format_exc()}"))
            finally:
                self.message_queue.put(("done", None))
        thread = threading.Thread(target=wrapper)
        thread.daemon = True
        thread.start()

    # --- 原始功能方法 ---
    def initialize_game(self):
        if not self.check_game_path():
            return
        self.run_in_thread(self._initialize_game)

    def _initialize_game(self):
        game_path = self.game_path.get()
        self.thread_update_status("正在初始化...")
        try:
            # ... (复制EasyRPG的代码，使用 self.thread_log) ...
            copied_files = 0
            skipped_files = 0
            self.thread_log("正在复制EasyRPG文件...")
            for item in os.listdir(self.easyrpg_path):
                src = os.path.join(self.easyrpg_path, item)
                dst = os.path.join(game_path, item)
                if os.path.isfile(src):
                    if not os.path.exists(dst):
                        shutil.copy2(src, dst)
                        copied_files += 1
                    else:
                        skipped_files += 1
            self.thread_log(f"EasyRPG文件复制完成: 复制 {copied_files} 个文件，跳过 {skipped_files} 个已存在文件")

            # ... (解压RTP的代码，使用 self.thread_log) ...
            self.thread_log("正在处理RTP文件...")
            import zipfile
            import tempfile
            if not (self.rtp_2000.get() or self.rtp_2000en.get() or self.rtp_2003.get() or self.rtp_2003steam.get()):
                self.thread_log("警告: 未选择任何RTP文件", "error")
            rtp_files = []
            if self.rtp_2000.get(): rtp_files.append("2000.zip")
            if self.rtp_2000en.get(): rtp_files.append("2000en.zip")
            if self.rtp_2003.get(): rtp_files.append("2003.zip")
            if self.rtp_2003steam.get(): rtp_files.append("2003steam.zip")

            for rtp_file in rtp_files:
                rtp_path = os.path.join(self.rtpcollection_path, rtp_file)
                if os.path.exists(rtp_path):
                    self.thread_log(f"正在解压 {rtp_file}...")
                    rtp_copied = 0
                    rtp_skipped = 0
                    try:
                        with tempfile.TemporaryDirectory() as temp_dir:
                            self.thread_log(f"创建临时目录: {temp_dir}")
                            with zipfile.ZipFile(rtp_path, 'r') as zip_ref:
                                zip_ref.extractall(temp_dir)
                            self.thread_log(f"从临时目录复制文件到游戏目录...")
                            for root, dirs, files in os.walk(temp_dir):
                                rel_path = os.path.relpath(root, temp_dir)
                                if rel_path == '.': rel_path = ''
                                target_dir = os.path.normpath(os.path.join(game_path, rel_path))
                                os.makedirs(target_dir, exist_ok=True)
                                for file in files:
                                    src_file = os.path.join(root, file)
                                    dst_file = os.path.join(target_dir, file)
                                    if os.path.exists(dst_file):
                                        rtp_skipped += 1
                                        continue
                                    try:
                                        shutil.copy2(src_file, dst_file)
                                        rtp_copied += 1
                                    except Exception as e:
                                        self.thread_log(f"复制文件失败: {src_file} -> {dst_file}: {str(e)}", "error")
                        self.thread_log(f"{rtp_file} 处理完成: 复制 {rtp_copied} 个文件，跳过 {rtp_skipped} 个已存在文件")
                    except Exception as e:
                        self.thread_log(f"解压 {rtp_file} 时出错: {str(e)}", "error")
                else:
                    self.thread_log(f"找不到RTP文件: {rtp_file}", "error")

            # ... (转换文本编码的代码，使用 self.thread_log) ...
            self.thread_log("正在转换文本文件编码...")
            processed_files = 0
            corrected_or_converted = 0

            japanese_encodings = ['shift_jis', 'cp932']
            kana_pattern = re.compile(r'[\u3040-\u30FF]')

            for item in os.listdir(game_path):
                file_path = os.path.join(game_path, item)
                if not (os.path.isfile(file_path) and (item.lower().endswith('.txt') or item.lower().endswith('.ini'))):
                    continue

                processed_files += 1

                with open(file_path, 'rb') as f_bytes:
                    raw_content = f_bytes.read()
                if not raw_content:
                    self.thread_log(f"跳过空文件: {item}", "normal")
                    continue

                needs_conversion = False
                decoded_content = None
                encoding_used = None

                for encoding in japanese_encodings:
                    try:
                        current_decoded = raw_content.decode(encoding, errors='strict') # strict 会在失败时抛出异常
                        if kana_pattern.search(current_decoded):
                            decoded_content = current_decoded
                            encoding_used = encoding
                            needs_conversion = True
                            self.thread_log(f"文件 {item} 用 {encoding} 解码后发现假名，标记为需要处理。", "normal")
                            break # 找到一个含假名的解码就够了
                        else:
                            # 解码成功但不含假名，也跳出内部循环
                            break
                    except UnicodeDecodeError:
                        # 捕获解码错误，继续尝试下一个编码
                        continue

                # 4. 如果标记为需要转换，则强制写入GBK
                if needs_conversion and decoded_content is not None and encoding_used is not None:
                    with open(file_path, 'w', encoding='gbk', errors='replace') as file_out:
                        file_out.write(decoded_content)
                    self.thread_log(f"已处理文件: {item} (检测到假名，从 {encoding_used} 强制转换为 GBK)", "success")
                    corrected_or_converted += 1

            # --- 最终日志总结 (不再包含失败计数) ---
            skipped_files = processed_files - corrected_or_converted
            self.thread_log(f"编码检查完成: 处理 {corrected_or_converted} 个文件, 跳过 {skipped_files} 个文件。")

            # --- 新增步骤：检查并按需修改 RPG_RT.ini ---
            self.thread_log("正在检查并更新 RPG_RT.ini 配置...")
            ini_path = os.path.join(game_path, "RPG_RT.ini")

            if os.path.exists(ini_path):
                self.thread_log(f"找到 RPG_RT.ini: {ini_path}")

                lines = []
                # 假设文件已被转为GBK
                with open(ini_path, 'r', encoding='gbk') as f:
                    lines = f.readlines()

                # --- 1. 分析内容，找到段落和键值 ---
                has_rpg_rt_section = False
                rpg_rt_section_end_index = -1 # 下一个 section 或文件末尾

                has_full_package_flag = False # 是否在 RPG_RT 段内找到

                has_easyrpg_section = False
                easyrpg_section_end_index = -1 # 下一个 section 或文件末尾

                has_encoding_936 = False # 是否在 EasyRPG 段内找到

                current_section = None
                for i, line in enumerate(lines):
                    line_strip = line.strip()

                    if line_strip.startswith('['):
                        section_name = line_strip
                        # 记录上一个 section 的结束位置（即当前行的索引）
                        if current_section == '[RPG_RT]':
                            rpg_rt_section_end_index = i
                        elif current_section == '[EasyRPG]':
                            easyrpg_section_end_index = i

                        current_section = section_name # 更新当前 section

                        if section_name == '[RPG_RT]':
                            has_rpg_rt_section = True
                        elif section_name == '[EasyRPG]':
                            has_easyrpg_section = True
                    # 检查键值对是否在对应的段落内
                    elif current_section == '[RPG_RT]' and line_strip == 'FullPackageFlag=1':
                        has_full_package_flag = True
                    elif current_section == '[EasyRPG]' and line_strip == 'Encoding=936':
                        has_encoding_936 = True

                # 如果文件结束了，设置最后一个 section 的结束索引为文件总行数
                if current_section == '[RPG_RT]' and rpg_rt_section_end_index == -1:
                    rpg_rt_section_end_index = len(lines)
                if current_section == '[EasyRPG]' and easyrpg_section_end_index == -1:
                    easyrpg_section_end_index = len(lines)


                # --- 2. 构建新的文件内容，并在需要时插入 ---
                output_lines = []
                needs_write = False

                # 确定 FullPackageFlag 的插入位置 (如果需要)
                insert_fpf_at = -1
                if has_rpg_rt_section and not has_full_package_flag:
                    insert_fpf_at = rpg_rt_section_end_index if rpg_rt_section_end_index != -1 else len(lines)
                    needs_write = True

                # 确定 Encoding=936 的插入位置 (如果需要)
                insert_enc_at = -1
                if has_easyrpg_section and not has_encoding_936:
                    insert_enc_at = easyrpg_section_end_index if easyrpg_section_end_index != -1 else len(lines)
                    needs_write = True

                # 遍历原始行，构建输出列表
                for i, line in enumerate(lines):
                    # 检查是否到达插入 FullPackageFlag 的点
                    if i == insert_fpf_at:
                        output_lines.append("FullPackageFlag=1\n")
                        self.thread_log("在 [RPG_RT] 段落末尾添加 FullPackageFlag=1")

                    # 检查是否到达插入 Encoding=936 的点
                    if i == insert_enc_at:
                        output_lines.append("Encoding=936\n")
                        self.thread_log("在 [EasyRPG] 段落末尾添加 Encoding=936")

                    # 添加当前原始行到输出列表
                    output_lines.append(line)

                # 特殊处理：如果插入点正好是文件末尾
                if len(lines) == insert_fpf_at:
                    output_lines.append("FullPackageFlag=1\n")
                    self.thread_log("在文件末尾（因 [RPG_RT] 在最后）添加 FullPackageFlag=1")
                if len(lines) == insert_enc_at:
                    output_lines.append("Encoding=936\n")
                    self.thread_log("在文件末尾（因 [EasyRPG] 在最后）添加 Encoding=936")


                # 如果 [EasyRPG] 段落本身就不存在，则需要在末尾添加
                if not has_easyrpg_section:
                    # 确保添加前有换行符 (如果文件非空)
                    if output_lines and not output_lines[-1].endswith('\n'):
                        output_lines[-1] = output_lines[-1].rstrip() + '\n'
                    # 添加段落和编码
                    output_lines.append("[EasyRPG]\n")
                    output_lines.append("Encoding=936\n")
                    self.thread_log("添加 [EasyRPG] 段落和 Encoding=936")
                    needs_write = True


                # --- 3. 清理空行并写回文件 ---
                if needs_write:
                    # 清理掉完全是空白的行 (只包含空格/制表符/换行符)
                    final_output_lines = [l for l in output_lines if l.strip()]
                    # 在[EasyRPG]段落前添加换行
                    easyRPGline = final_output_lines.index("[EasyRPG]\n")
                    if easyRPGline > 0:
                        final_output_lines.insert(easyRPGline, '\n')

                    self.thread_log("正在写回更新后的 RPG_RT.ini...")
                    # 如果写入失败，流程会中断 (按要求简化错误处理)
                    with open(ini_path, 'w', encoding='gbk') as f:
                        f.writelines(final_output_lines)
                    self.thread_log("RPG_RT.ini 更新完成。")
                else:
                    self.thread_log("RPG_RT.ini 无需修改。")

            else:
                self.thread_log("未找到 RPG_RT.ini 文件，跳过配置修改。")
            # --- RPG_RT.ini 处理结束 ---

            self.thread_update_status("初始化完成")
            self.thread_show_success(f"游戏初始化完成")
        except Exception as e:
            self.thread_update_status("初始化过程中出错")
            self.thread_show_error(f"初始化过程中出错: {str(e)}")

    def rename_files(self):
        if not self.check_game_path(): return
        self.run_in_thread(self._rename_files)

    def _rename_files(self):
        game_path = self.game_path.get()
        self.thread_update_status("正在处理文件名...")
        try:
            # ... (生成filelist.txt的代码，使用 self.thread_log) ...
            lmt_path = os.path.join(game_path, "RPG_RT.lmt")
            filelist_cmd = [self.rpgrewriter_path, lmt_path, "-F", "Y"]
            self.thread_log(f"执行命令: {' '.join(filelist_cmd)}")
            process = subprocess.run(filelist_cmd, capture_output=True, text=True, check=True)
            if process.stdout: self.thread_log("命令输出: " + process.stdout.strip())
            filelist_path = os.path.join(self.program_dir, "filelist.txt")
            if not os.path.exists(filelist_path): raise FileNotFoundError("未能生成filelist.txt文件")
            with open(filelist_path, 'r', encoding='utf-8') as file: lines = file.readlines()
            lines = [line.rstrip('\r\n') for line in lines]
            blank_lines = [i for i, line in enumerate(lines) if line.strip() == "___"]
            converted_count = 0
            for line_num in blank_lines:
                if line_num > 0:
                    original_name = lines[line_num - 1]
                    if any(ord(c) > 127 for c in original_name):
                        unicode_name = "".join([f"u{ord(c):04x}" if ord(c) > 127 else c for c in original_name])
                        lines[line_num] = unicode_name
                        self.thread_log(f"转换文件名: {original_name} -> {unicode_name}")
                        converted_count += 1
                    else:
                        lines[line_num] = original_name
            input_path = os.path.join(self.program_dir, "input.txt")
            with open(input_path, 'w', encoding='utf-8') as file: file.write('\n'.join(lines))
            self.thread_log(f"已生成input.txt文件，共转换 {converted_count} 个非ASCII文件名")

            # ... (执行重命名的代码，使用 self.thread_log) ...
            self.thread_log("第1步: 重写文件名 - 正在执行重命名...")
            rename_cmd = [self.rpgrewriter_path, lmt_path, "-V"]
            self.thread_log(f"执行命令: {' '.join(rename_cmd)}")
            rename_result = subprocess.run(rename_cmd, capture_output=True, text=True)
            if rename_result.stdout: self.thread_log("命令输出: " + rename_result.stdout.strip())
            if rename_result.stderr: self.thread_log("命令错误: " + rename_result.stderr.strip(), "error")
            if rename_result.returncode != 0: raise Exception(f"文件重命名失败，返回代码: {rename_result.returncode}")

            self.thread_log("第2步: 重写文件名 - 正在重写游戏数据...")
            log_filename = "renames_log" if self.write_log_var.get() else "null"
            rewrite_cmd = [self.rpgrewriter_path, lmt_path, "-rewrite", "-all", "-log", log_filename]
            self.thread_log(f"执行命令: {' '.join(rewrite_cmd)}")
            process = subprocess.Popen(rewrite_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate(input="Y\n")
            if stdout: self.thread_log("命令输出: " + stdout.strip())
            if stderr: self.thread_log("命令错误: " + stderr.strip(), "error")
            if process.returncode != 0: raise Exception(f"数据重写失败，返回代码: {process.returncode}")

            self.thread_update_status("文件名重写完成")
            self.thread_show_success("文件名重写完成")

            if self.write_log_var.get():
                log_txt_path = os.path.join(self.program_dir, log_filename)
                if os.path.exists(log_txt_path):
                    try:
                        with open(log_txt_path, 'r', encoding='utf-8') as file: log_content = file.read()
                        missing_count = log_content.strip().count('\n') + 1 if log_content.strip() else 0
                        self.thread_log(f"有 {missing_count} 个文件名未找到翻译，详见 {log_filename}")
                    except Exception as log_e:
                        self.thread_log(f"读取日志文件 {log_filename} 时出错: {str(log_e)}", "error")

        except Exception as e:
            self.thread_update_status("文件名重写过程中出错")
            self.thread_show_error(f"文件名重写过程中出错: {str(e)}")

    def export_text(self):
        if not self.check_game_path(): return
        self.run_in_thread(self._export_text)

    def _export_text(self):
        game_path = self.game_path.get()
        encoding = self.export_encoding.get().split(' - ')[-1]
        self.thread_update_status(f"正在导出文本 (编码: {encoding})...")
        try:
            # ... (导出文本的代码，使用 self.thread_log) ...
            temp_dir = os.path.join(game_path, "_temp_problem_files")
            os.makedirs(temp_dir, exist_ok=True)
            problem_files = []
            lmt_path = os.path.join(game_path, "RPG_RT.lmt")
            export_successful = False
            max_attempts = 50
            attempts = 0
            while not export_successful and attempts < max_attempts:
                attempts += 1
                export_cmd = [self.rpgrewriter_path, lmt_path, "-export", "-readcode", encoding]
                self.thread_log(f"导出尝试 #{attempts}，执行命令: {' '.join(export_cmd)}")
                process = subprocess.Popen(export_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                stdout, stderr = process.communicate()
                if stdout: self.thread_log("命令输出: " + stdout.strip())
                if stderr: self.thread_log("命令错误: " + stderr.strip(), "error")
                if process.returncode == 0:
                    export_successful = True
                    self.thread_log("导出成功完成！")
                else:
                    if "IndexOutOfRange" in stderr or "OutOfRange" in stderr:
                        map_pattern = r"Extracting (Map\d+\.lmu)"
                        maps = re.findall(map_pattern, stdout)
                        if maps:
                            problem_map = maps[-1]
                            problem_map_path = os.path.join(game_path, problem_map)
                            if os.path.exists(problem_map_path):
                                try:
                                    target_move_path = os.path.join(temp_dir, problem_map)
                                    if os.path.exists(target_move_path): # 如果临时目录已存在同名文件，先删除
                                        os.remove(target_move_path)
                                    shutil.move(problem_map_path, target_move_path)
                                    if problem_map not in problem_files: # 避免重复添加
                                        problem_files.append(problem_map)
                                    self.thread_log(f"检测到问题文件: {problem_map}，已移动到临时目录", "error")
                                    continue
                                except Exception as move_err:
                                    self.thread_log(f"移动问题文件 {problem_map} 失败: {str(move_err)}", "error")
                                    break # 移动失败，停止尝试
                        self.thread_log("无法确定具体是哪个文件有问题，停止尝试", "error")
                        break
                    else:
                        self.thread_log("遇到未知错误，停止尝试", "error")
                        break

            string_scripts_path = os.path.join(game_path, "StringScripts")
            if os.path.exists(string_scripts_path):
                file_count = sum(len(files) for _, _, files in os.walk(string_scripts_path))
                self.thread_update_status("文本导出完成")
                for file in problem_files:
                    source = os.path.join(temp_dir, file)
                    if os.path.exists(source):
                        try:
                            destination = os.path.join(game_path, file)
                            shutil.move(source, destination)
                            self.thread_log(f"已将问题文件 {file} 移回原位置")
                        except Exception as move_back_err:
                            self.thread_log(f"移回问题文件 {file} 失败: {str(move_back_err)}", "error")
                if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                    try:
                        os.rmdir(temp_dir)
                    except Exception as rmdir_err:
                        self.thread_log(f"删除临时目录失败: {str(rmdir_err)}", "error")

                if problem_files:
                    self.thread_show_success(f"文本导出部分完成，共 {file_count} 个文件。有 {len(problem_files)} 个地图文件未能导出: {', '.join(problem_files)}")
                else:
                    self.thread_show_success(f"文本导出完成，共 {file_count} 个文件")
            else:
                self.thread_update_status("文本导出失败")
                self.thread_show_error("未能创建StringScripts文件夹")
        except Exception as e:
            self.thread_update_status("文本导出过程中出错")
            self.thread_show_error(f"文本导出过程中出错: {str(e)}")
            # 确保临时目录中的文件移回原位置 (添加更健壮的错误处理)
            try:
                temp_dir = os.path.join(game_path, "_temp_problem_files")
                if os.path.exists(temp_dir):
                    for file in os.listdir(temp_dir):
                        source = os.path.join(temp_dir, file)
                        destination = os.path.join(game_path, file)
                        try:
                            shutil.move(source, destination)
                            self.thread_log(f"已将文件 {file} 移回原位置")
                        except Exception as move_back_err:
                             self.thread_log(f"移回文件 {file} 失败: {str(move_back_err)}", "error")
                    # 尝试移除临时目录
                    if not os.listdir(temp_dir):
                        try:
                            os.rmdir(temp_dir)
                        except Exception as rmdir_err:
                            self.thread_log(f"删除临时目录失败: {str(rmdir_err)}", "error")
            except Exception as e2:
                self.thread_log(f"恢复文件时出错: {str(e2)}", "error")

    def process_file(self, file_path):
        result = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                match = re.match(r'#(.+)#', line)
                if match:
                    title = match.group(1)
                    if title == 'EventName':
                        i += 1
                    elif title == 'Message' or title == 'Choice':
                        message = ''
                        i += 1
                        start_line_index = i
                        while i < len(lines) and not lines[i].strip() == '##':
                            message += lines[i]
                            i += 1
                        if message:
                            message_stripped = message.rstrip('\n')
                            result[message_stripped] = message_stripped # 使用去尾换行的作为key
                    else: # 处理其他如 System/Terms 等
                        i += 1
                        if i < len(lines):
                            content = lines[i].strip()
                            if content:
                                result[content] = content
                i += 1
        except Exception as e:
            self.thread_log(f"处理文件 {os.path.basename(file_path)} 时出错: {str(e)}", "error")
        return result

    def create_transjson_files(self):
        if not self.check_game_path(): return
        self.run_in_thread(self._create_transjson_files)

    def _create_transjson_files(self):
        game_path = self.game_path.get()
        string_scripts_path = os.path.join(game_path, "StringScripts")
        if not os.path.exists(string_scripts_path):
            self.thread_show_error("未找到StringScripts文件夹，请先导出文本")
            return
        self.thread_update_status("正在创建JSON文件...")
        try:
            # ... (创建Works子目录的代码) ...
            game_folder_name = os.path.basename(game_path)
            work_game_dir = os.path.join(self.works_dir, game_folder_name)
            untranslated_dir = os.path.join(work_game_dir, "untranslated")
            translated_dir = os.path.join(work_game_dir, "translated")
            os.makedirs(work_game_dir, exist_ok=True)
            os.makedirs(untranslated_dir, exist_ok=True)
            os.makedirs(translated_dir, exist_ok=True)
            self.thread_log(f"确保目录存在: {untranslated_dir}")
            self.thread_log(f"确保目录存在: {translated_dir}")

            all_results = {}
            file_count = 0
            string_count = 0
            for root, dirs, files in os.walk(string_scripts_path):
                for file in files:
                    if file.endswith('.txt'):
                        file_path = os.path.join(root, file)
                        file_results = self.process_file(file_path)
                        all_results.update(file_results)
                        file_count += 1
                        string_count += len(file_results)
            self.thread_log(f"已处理 {file_count} 个文件，提取 {string_count} 个字符串")
            json_path = os.path.join(untranslated_dir, "translation.json")
            with open(json_path, 'w', encoding='utf-8') as json_file:
                json.dump(all_results, json_file, ensure_ascii=False, indent=4)
            self.thread_update_status("JSON文件创建完成")
            self.thread_show_success(f"JSON文件已创建在 {untranslated_dir}，共 {string_count} 个字符串")
        except Exception as e:
            self.thread_update_status("创建JSON文件过程中出错")
            self.thread_show_error(f"创建JSON文件过程中出错: {str(e)}")

    # --- 生成世界观字典 ---
    def generate_world_dict(self):
        if not self.check_game_path(): return
        self.run_in_thread(self._generate_world_dict)

    def _generate_world_dict(self):
        self.thread_update_status("正在生成世界观字典...")
        game_path = self.game_path.get()
        game_folder_name = os.path.basename(game_path)
        work_game_dir = os.path.join(self.works_dir, game_folder_name)
        untranslated_dir = os.path.join(work_game_dir, "untranslated")
        json_path = os.path.join(untranslated_dir, "translation.json")
        dict_csv_path = os.path.join(work_game_dir, "world_dictionary.csv")
        temp_text_path = os.path.join(work_game_dir, "temp_world_text.txt") # 临时文件

        if not os.path.exists(json_path):
            self.thread_show_error(f"未找到未翻译的JSON文件: {json_path}，请先执行步骤3")
            return

        try:
            # 1. 加载JSON并提取原文
            self.thread_log("加载JSON文件并提取原文...")
            with open(json_path, 'r', encoding='utf-8') as f:
                translations = json.load(f)
            original_texts = list(translations.keys())
            self.thread_log(f"共提取 {len(original_texts)} 条原文")

            # 2. 将原文写入临时文件
            self.thread_log("将原文写入临时文件...")
            with open(temp_text_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(original_texts))
            self.thread_log(f"临时文件已创建: {temp_text_path}")

            # 3. 调用Gemini API
            api_key = self.world_dict_config.get("api_key").strip()
            model_name = self.world_dict_config.get("model").strip()
            prompt_template = self.world_dict_config.get("prompt")

            if not api_key:
                self.thread_show_error("请在世界观字典配置中设置Gemini API Key")
                return

            self.thread_log(f"正在调用Gemini API (模型: {model_name})...")
            self.thread_log(f"这一步一般会消耗3~5分钟，请耐心等待")

            client = genai.Client(api_key=api_key)

            # 读取临时文件内容并替换到Prompt中
            with open(temp_text_path, 'r', encoding='utf-8') as f:
                game_text_content = f.read()

            # 检查文本大小，如果太大可能需要分块或用其他方法
            # 这里暂时直接嵌入，Gemini Pro 2.5 支持很长上下文
            final_prompt = prompt_template.format(game_text=game_text_content)

            # 注意：Gemini API 可能对单次请求的大小有限制，即使模型支持长上下文
            # 这里为了简化，假设文本大小在API允许范围内
            try:
                response = client.models.generate_content(
                    model=model_name, contents=final_prompt
                )
                csv_response = response.text
            except Exception as api_err:
                 # 捕获并记录详细的API错误信息
                error_details = getattr(api_err, 'message', str(api_err))
                self.thread_show_error(f"Gemini API调用失败: {error_details}")
                # 打印更多调试信息
                self.thread_log(f"Gemini API 错误详情: {api_err}", "error")
                # 可以考虑检查 response.prompt_feedback 是否有 block reason
                try:
                    if response and response.prompt_feedback:
                         self.thread_log(f"Gemini Block Reason: {response.prompt_feedback.block_reason}", "error")
                except Exception:
                    pass # 忽略检查feedback时可能发生的错误
                return # API失败，停止执行

            self.thread_log("Gemini API调用成功")

            # 4. 解析CSV响应
            self.thread_log("解析Gemini返回的CSV数据...")
            parsed_data = []
            if csv_response:
                try:
                    # 使用 io.StringIO 将字符串模拟成文件
                    csv_file = io.StringIO(csv_response.strip())
                    reader = csv.reader(csv_file, quotechar='"', delimiter=',', quoting=csv.QUOTE_ALL, skipinitialspace=True)
                    for row in reader:
                        if len(row) == 4: # 确保有4列
                            parsed_data.append(row)
                        else:
                            self.thread_log(f"跳过格式错误的CSV行: {row}", "error")
                except Exception as parse_err:
                    self.thread_log(f"解析CSV时出错: {str(parse_err)}", "error")
                    self.thread_log(f"原始CSV响应内容:\n{csv_response}", "error") # 记录原始响应以供调试
                    # 即使解析出错，也尝试继续保存已成功解析的部分（如果有）
            else:
                self.thread_log("Gemini API未返回有效的CSV数据", "error")

            # 5. 保存为CSV文件
            self.thread_log("保存世界观字典为CSV文件...")
            try:
                with open(dict_csv_path, 'w', newline='', encoding='utf-8-sig') as f: # utf-8-sig 确保Excel能正确打开
                    writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                    # 写入表头
                    writer.writerow(['原文', '译文', '类别', '描述'])
                    writer.writerows(parsed_data)
                self.thread_update_status("世界观字典生成完成")
                self.thread_show_success(f"世界观字典已保存: {dict_csv_path}，共 {len(parsed_data)} 条")
            except Exception as write_err:
                 self.thread_show_error(f"保存CSV文件失败: {str(write_err)}")

        except Exception as e:
            self.thread_update_status("生成世界观字典过程中出错")
            self.thread_show_error(f"生成世界观字典过程中出错: {str(e)}")
        finally:
            # 清理临时文件
            if os.path.exists(temp_text_path):
                try:
                    os.remove(temp_text_path)
                    self.thread_log(f"已删除临时文件: {temp_text_path}")
                except Exception as del_err:
                    self.thread_log(f"删除临时文件失败: {str(del_err)}", "error")

    # --- 翻译JSON文件 ---
    def translate_json_file(self):
        if not self.check_game_path(): return
        self.run_in_thread(self._translate_json)
    
    def post_process_translation(self, text, original_text):
        """
        对翻译后的文本进行后处理，以适应目标编码或中文习惯。
        Args:
            text (str): 待处理的译文文本。
        Returns:
            str: 处理后的文本。
        """
        if not isinstance(text, str): # 基本类型检查
            return text

        # 规则 1: 将日语分割号(・)转换为半角分割号(·)
        processed_text = text.replace('・', '·')

        # 规则 2: 将音符符号(♪)转换为波浪号(~)
        processed_text = processed_text.replace('♪', '~')

        # 规则 3: 移除多余引号
        count_source_open = original_text.count('「')
        count_processed_open = processed_text.count('「')
        if count_source_open == 0 and count_processed_open > 0:
            # 如果原文没有开引号，但处理后的文本有，移除处理后的开引号
            processed_text = processed_text.replace('「', '', count_processed_open)

        # 规则 4: 引号平衡 - 检查整个字符串
        count_open = processed_text.count('「')
        count_close = processed_text.count('」')

        if count_open > count_close:
            # 如果开引号数量大于闭引号，在字符串末尾添加一个闭引号
            processed_text += '」' * (count_open - count_close) # 添加缺失的数量

        return processed_text

    # --- Helper function for validation ---
    def validate_translation(self, original, translated):
        """
        验证译文是否保留了原文中的特定标记。
        Args:
            original (str): 原文文本。
            translated (str): 译文文本。
        Returns:
            bool: True 如果验证通过，False 否则。
        """
        try:
            # 1. 检查反斜杠 + 半角字符 (排除 \\ 和 \n)
            # Regex: (?<!\\) - negative lookbehind,确保前面不是反斜杠
            #        \\ - 匹配一个反斜杠
            #        [ -~] - 匹配任何可打印的ASCII字符(空格到~)
            pattern_backslash_ascii = r'(?<!\\)\\[ -~]'
            original_backslash_count = len(re.findall(pattern_backslash_ascii, original))
            translated_backslash_count = len(re.findall(pattern_backslash_ascii, translated))
            if original_backslash_count != translated_backslash_count:
                self.thread_log(f"验证失败: 反斜杠标记数量不匹配。原文({original_backslash_count}): '{original[:50]}...', 译文({translated_backslash_count}): '{translated[:50]}...'", "error")
                return False

            # 2. 检查上半直角引号「
            original_quote_count = original.count('「')
            translated_quote_count = translated.count('「')
            if original_quote_count > translated_quote_count:
                self.thread_log(f"验证失败: 上半引号「数量不匹配。原文({original_quote_count}): '{original[:50]}...', 译文({translated_quote_count}): '{translated[:50]}...'", "error")
                return False
            
            # 3. 检查下半直角双引号『
            original_double_quote_count = original.count('『')
            translated_double_quote_count = translated.count('『')
            if original_double_quote_count > translated_double_quote_count:
                self.thread_log(f"验证失败: 下半引号『数量不匹配。原文({original_double_quote_count}): '{original[:50]}...', 译文({translated_double_quote_count}): '{translated[:50]}...'", "error")
                return False

            # 如果所有检查都通过
            return True
        except Exception as e:
            self.thread_log(f"验证函数内部出错: {e}", "error")
            return False # 出错时视为验证失败

    def pre_process_text(self, text):
        """在发送给 LLM 前替换特殊标记为 PUA 占位符"""
        if not isinstance(text, str): return text # 添加类型检查
        processed_text = text.replace('「', '\uE000')
        processed_text = processed_text.replace('」', '\uE001')
        processed_text = processed_text.replace('\!', '\uE002')
        processed_text = processed_text.replace('『', '\uE003')
        processed_text = processed_text.replace('』', '\uE004')
        processed_text = processed_text.replace('\.', '\uE005')
        processed_text = processed_text.replace('\<', '\uE006')
        processed_text = processed_text.replace('\>', '\uE007')
        processed_text = processed_text.replace('\|', '\uE008')
        processed_text = processed_text.replace('\^', '\uE009')
        return processed_text
    
    def restore_pua_placeholders(self, text):
        """将译文中的 PUA 占位符还原为原始标记"""
        if not isinstance(text, str): return text # 添加类型检查
        processed_text = text.replace('\uE000', '「')
        processed_text = processed_text.replace('\uE001', '」')
        processed_text = processed_text.replace('\uE002', '\!')
        processed_text = processed_text.replace('\uE003', '『')
        processed_text = processed_text.replace('\uE004', '』')
        processed_text = processed_text.replace('\uE005', '\.')
        processed_text = processed_text.replace('\uE006', '\<')
        processed_text = processed_text.replace('\uE007', '\>')
        processed_text = processed_text.replace('\uE008', '\|')
        processed_text = processed_text.replace('\uE009', '\^')
        return processed_text

    # --- Recursive translation helper with retry and split ---
    def _translate_item_recursive(self, _original_text, context_items, world_dictionary, api_client, config, error_log_path, error_log_lock, max_retries=3):
        """
        递归翻译单个文本项，包含验证、重试和拆分逻辑。
        Args:
            original_text (str): 需要翻译的原文。
            context_items (list): 上下文 [(key, val), ...] (此处简化，可能仅用于构建prompt)。
            world_dictionary (list): 世界观字典。
            api_client (OpenAI): API客户端实例。
            config (dict): 翻译配置。
            error_log_path (str): 错误日志文件路径。
            error_log_lock (threading.Lock): 文件写入锁。
            max_retries (int): 最大重试次数。
        Returns:
            str: 最终的翻译结果（可能经过后处理）或原文（如果所有尝试失败）。
        """
        prompt_template = config.get("prompt_template")
        model_name = config.get("model")
        source_language = config.get("source_language", "日语")
        target_language = config.get("target_language", "简体中文")

        # *** 步骤 1: 预处理原文 ***
        original_text = self.pre_process_text(_original_text)

        last_failed_translation = None # 记录最后一次失败的译文，用于日志

        for attempt in range(max_retries + 1):
            try:
                # a. 构建上下文和术语表 (针对单个条目简化处理)
                context_texts = [item[0] for item in context_items[-config.get("context_lines", 10):]] # 取最近N条原文
                context_section = ""
                if context_texts:
                    context_section = "### 上文内容\n<context>\n" + "\n".join(context_texts) + "\n</context>\n"

                relevant_dict_entries = []
                if world_dictionary:
                    for entry in world_dictionary:
                        if entry.get('原文') and entry['原文'] in original_text: # 检查单个文本
                            relevant_dict_entries.append(f"{entry['原文']}|{entry.get('译文', '')}|{entry.get('类别', '')} - {entry.get('描述', '')}")

                glossary_section = ""
                if relevant_dict_entries:
                    glossary_section = "### 术语表\n原文|译文|类别 - 描述\n" + "\n".join(relevant_dict_entries) + "\n"

                # b. 构建最终Prompt (注意：这里是为单条文本构建，而不是批次)
                # 为了复用模板，我们仍然模拟编号，但只包含一条
                numbered_text = f"1.{original_text}"
                timestamp_suffix = f"\n[timestamp: {datetime.datetime.now().timestamp()}]" if attempt > 0 else "" # 重试时加时间戳

                final_prompt = prompt_template.format(
                    source_language=source_language,
                    target_language=target_language,
                    glossary_section=glossary_section,
                    context_section=context_section,
                    batch_text=numbered_text, # 传入单条编号文本
                    target_language_placeholder=target_language
                ) + timestamp_suffix

                # c. 调用API
                self.thread_log(f"调用API翻译 (尝试 {attempt+1}/{max_retries+1}): '{original_text[:30]}...'")
                response = api_client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": final_prompt}],
                    temperature=0.7,
                    max_tokens=4000
                )
                response_content = response.choices[0].message.content

                # d. 提取翻译结果 (处理单条)
                match = re.search(r'<textarea>(.*?)</textarea>', response_content, re.DOTALL)
                if match:
                    translated_block = match.group(1).strip()
                    # 移除可能的编号前缀 "1."
                    if translated_block.startswith("1."):
                        _translated_text = translated_block[2:].strip()
                    else:
                        # 如果没有找到"1."，可能API返回格式略有不同，尝试直接使用
                        self.thread_log(f"警告: API响应未找到预期的'1.'前缀，将直接使用提取内容: '{translated_block[:50]}...'", "error")
                        _translated_text = translated_block

                    translated_text = self.restore_pua_placeholders(_translated_text) # 还原PUA占位符
                    last_failed_translation = translated_text # 记录本次尝试结果

                    # e. 验证翻译
                    if self.validate_translation(_original_text, translated_text):
                        self.thread_log(f"验证通过 (尝试 {attempt+1}): '{original_text[:30]}...' -> '{translated_text[:30]}...'")
                        # f. 后处理
                        final_translation = self.post_process_translation(translated_text, _original_text)
                        return final_translation # 成功，返回结果
                    else:
                        # 验证失败，记录日志（已在validate_translation内完成）
                        if attempt < max_retries:
                            self.thread_log(f"验证失败，准备重试 (尝试 {attempt+1}/{max_retries+1}) for '{_original_text[:30]}...'")
                            continue # 继续下一次重试
                        else:
                            self.thread_log(f"验证失败，达到最大重试次数 ({max_retries+1}) for '{_original_text[:30]}...'")
                            break # 跳出重试循环，进入拆分或回退

                else: # API响应格式错误
                    self.thread_log(f"API响应格式错误 (尝试 {attempt+1})，未找到<textarea> for '{_original_text[:30]}...'", "error")
                    self.thread_log(f"原始响应预览: {response_content[:200]}", "error")
                    last_failed_translation = f"[API响应格式错误: {response_content[:100]}]"
                    if attempt < max_retries:
                        continue
                    else:
                        break

            except Exception as api_err:
                self.thread_log(f"API调用失败 (尝试 {attempt+1}): {str(api_err)} for '{_original_text[:30]}...'", "error")
                last_failed_translation = f"[API调用错误: {str(api_err)}]"
                if attempt < max_retries:
                    continue
                else:
                    break # API连续失败，跳出重试

        # --- 重试循环结束 ---
        # 如果执行到这里，说明所有重试都失败了

        # g. 尝试拆分翻译 (如果文本包含多行且不止一行)
        lines = original_text.split('\n')
        if len(lines) > 1:
            self.thread_log(f"翻译和重试均失败，尝试拆分: '{_original_text[:30]}...'")
            mid_point = (len(lines) + 1) // 2 # 前半部分多一行（如果总行数是奇数）
            first_half_text = '\n'.join(lines[:mid_point])
            second_half_text = '\n'.join(lines[mid_point:])

            # 递归调用自身处理两个部分
            translated_first_half = self._translate_item_recursive(first_half_text, context_items, world_dictionary, api_client, config, error_log_path, error_log_lock, max_retries)
            translated_second_half = self._translate_item_recursive(second_half_text, context_items, world_dictionary, api_client, config, error_log_path, error_log_lock, max_retries)

            # 拼接结果（即使子部分是原文回退，也要拼接）
            combined_translation = translated_first_half + '\n' + translated_second_half
            self.thread_log(f"拆分翻译完成，合并结果 for '{_original_text[:30]}...'")
            # 注意：拆分后的结果不再进行整体的后处理，因为子部分已经处理过了
            return combined_translation
        else:
            # h. 无法拆分（只有一行）或拆分后仍然失败，执行最终回退
            self.thread_log(f"翻译、重试、拆分均失败或无法拆分，回退到原文: '{_original_text[:50]}...'", "error")
            # 记录到错误日志
            try:
                with error_log_lock: # 确保线程安全写入
                    with open(error_log_path, 'a', encoding='utf-8') as elog:
                        elog.write(f"[{datetime.datetime.now().isoformat()}] 翻译失败，使用原文回退:\n")
                        elog.write(f"  原文: {_original_text}\n")
                        if last_failed_translation:
                            elog.write(f"  最后尝试的译文: {last_failed_translation}\n")
                        elog.write("-" * 20 + "\n")
            except Exception as log_err:
                self.thread_log(f"写入错误日志失败: {log_err}", "error")

            # 返回原文作为最终结果
            return original_text

    # --- Modified translate_batch_worker ---
    def translate_batch_worker(self, batch_items, context_items, world_dictionary, api_client, config, translated_data, results_lock, progress_lock, processed_count_shared, error_log_path, error_log_lock):
        """
        处理一个批次的翻译任务，调用递归助手函数处理每个条目。
        """
        batch_results = {}
        processed_in_batch = 0
        total_items = len(batch_items) # 当前批次的总数

        # self.thread_log(f"Worker开始处理批次，包含 {total_items} 个条目")

        for i, (original_key, _) in enumerate(batch_items):
            try:
                # 调用递归翻译助手处理单个条目
                final_translation = self._translate_item_recursive(
                    original_key,
                    context_items + batch_items[:i], # 提供之前的上下文（包括当前批次中已处理的）
                    world_dictionary,
                    api_client,
                    config,
                    error_log_path,
                    error_log_lock,
                    max_retries=3 # 默认最大重试次数
                )
                batch_results[original_key] = final_translation
                processed_in_batch += 1

            except Exception as item_err:
                # 捕获递归函数本身抛出的意外错误（理论上不应发生，因其内部已处理）
                self.thread_log(f"处理条目时发生意外错误: {item_err} for '{original_key[:50]}...' - 将使用原文回退", "error")
                batch_results[original_key] = original_key # 极端情况下的回退
                processed_in_batch += 1 # 即使出错，也算处理了一个
                # 记录到错误日志
                try:
                    with error_log_lock:
                        with open(error_log_path, 'a', encoding='utf-8') as elog:
                            elog.write(f"[{datetime.datetime.now().isoformat()}] 处理条目时发生意外错误，使用原文回退:\n")
                            elog.write(f"  原文: {original_key}\n")
                            elog.write(f"  错误: {item_err}\n")
                            elog.write("-" * 20 + "\n")
                except Exception as log_err:
                    self.thread_log(f"写入错误日志失败: {log_err}", "error")


            # 更新全局结果和进度 (在每个条目处理后更新，提供更平滑的进度)
            # 使用锁确保线程安全
            with results_lock:
                if original_key in batch_results: # 确保结果存在
                    translated_data[original_key] = batch_results[original_key]

            with progress_lock:
                processed_count_shared['value'] += 1 # 使用方括号访问 key 'value'
                current_total_processed = processed_count_shared['value'] # 使用方括号访问 key 'value'
                # 更新状态 (主线程负责显示，这里只计算)
                # progress_percent = (current_total_processed / config['total_items_global']) * 100
                # status_message = f"正在翻译JSON... {current_total_processed}/{config['total_items_global']} ({progress_percent:.1f}%)"
                # self.thread_update_status(status_message) # 可能过于频繁，考虑移到主线程处理

        # 批次完成后可以记录一下
        self.thread_log(f"Worker完成批次，处理 {processed_in_batch}/{total_items} 个条目。")
            
    def _translate_json(self):
        self.thread_update_status("正在翻译JSON文件...")
        game_path = self.game_path.get()
        game_folder_name = os.path.basename(game_path)
        work_game_dir = os.path.join(self.works_dir, game_folder_name)
        untranslated_dir = os.path.join(work_game_dir, "untranslated")
        translated_dir = os.path.join(work_game_dir, "translated")
        os.makedirs(translated_dir, exist_ok=True) # <--- 添加：确保目录存在
        untranslated_json_path = os.path.join(untranslated_dir, "translation.json")
        translated_json_path = os.path.join(translated_dir, "translation_translated.json") # 输出文件名
        dict_csv_path = os.path.join(work_game_dir, "world_dictionary.csv")
        
        # --- 添加：定义错误日志路径和锁 ---
        error_log_path = os.path.join(translated_dir, "error.log")
        error_log_lock = threading.Lock()
        # --- 添加：可选：运行时删除旧日志 ---
        if os.path.exists(error_log_path):
             try:
                 os.remove(error_log_path)
                 self.thread_log(f"已删除旧的错误日志文件: {error_log_path}")
             except Exception as del_err:
                 self.thread_log(f"删除旧错误日志失败: {del_err}", "error")
        # ------------------------------------

        # 1. 加载未翻译JSON
        if not os.path.exists(untranslated_json_path):
            self.thread_show_error(f"未找到未翻译的JSON文件: {untranslated_json_path}")
            return
        self.thread_log("加载未翻译的JSON文件...")
        with open(untranslated_json_path, 'r', encoding='utf-8') as f:
            untranslated_data = json.load(f)
        translated_data = untranslated_data.copy() # 创建副本用于存储翻译结果
        original_items = list(untranslated_data.items()) # 转为列表以方便分批
        total_items = len(original_items) # <--- 添加：获取总数
        self.thread_log(f"成功加载JSON文件，共有 {len(original_items)} 个待翻译条目")

        # 2. 加载世界观字典
        world_dictionary = []
        if os.path.exists(dict_csv_path):
            self.thread_log("加载世界观字典...")
            try:
                with open(dict_csv_path, 'r', newline='', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    world_dictionary = [row for row in reader]
                self.thread_log(f"成功加载世界观字典，共 {len(world_dictionary)} 条条目")
            except Exception as e:
                self.thread_log(f"加载世界观字典失败: {str(e)}", "error")
        else:
            self.thread_log("未找到世界观字典文件，将不使用字典进行翻译")

        # 3. 获取翻译配置
        config = self.translate_config.copy() # <--- 修改：复制配置以便修改
        config['total_items_global'] = total_items # <--- 添加：将总数存入配置传递

        api_url = self.translate_config.get("api_url")
        api_key = self.translate_config.get("api_key").strip()
        model_name = self.translate_config.get("model").strip()
        batch_size = self.translate_config.get("batch_size", 10)
        context_lines = self.translate_config.get("context_lines", 10)
        concurrency = self.translate_config.get("concurrency", 16)
        prompt_template = self.translate_config.get("prompt_template")
        source_language = self.translate_config.get("source_language", "日语")
        target_language = self.translate_config.get("target_language", "简体中文")

        self.thread_log(f"翻译配置:")
        self.thread_log(f"- API URL: {api_url}")
        self.thread_log(f"- 模型: {model_name}")
        self.thread_log(f"- 批次大小: {batch_size}")
        self.thread_log(f"- 上下文行数: {context_lines}")
        self.thread_log(f"- 并发数: {concurrency}")

        if not api_key:
            self.thread_show_error("请在翻译JSON配置中设置API Key")
            return
        if not api_url:
            self.thread_show_error("请在翻译JSON配置中设置API URL")
            return

        # 4. 初始化OpenAI客户端
        try:
            self.thread_log("正在初始化API客户端...")
            client = OpenAI(base_url=api_url, api_key=api_key)
            self.thread_log("API客户端初始化成功")
        except Exception as client_err:
            self.thread_show_error(f"初始化API客户端失败: {str(client_err)}")
            return

        # 5. 分批和并发处理
        translated_data = untranslated_data.copy() # 用于存储最终结果
        results_lock = threading.Lock() # 锁translated_data
        progress_lock = threading.Lock() # 锁共享计数器
        processed_count_tracker = {'value': 0} # 使用字典模拟可变对象

        self.thread_log(f"开始翻译处理，总条目数: {total_items}")

        # 6. 使用线程池执行
        self.thread_log(f"开始使用 {concurrency} 个线程进行翻译...")
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = []
            # --- 添加：传递共享计数器和总数 ---
            processed_count_shared = {'value': 0} # 为每个执行创建一个新的计数器状态

            for i in range(0, total_items, batch_size):
                batch = original_items[i : i + batch_size]
                context_start = max(0, i - context_lines)
                context = original_items[context_start : i]

                # --- 修改：传递额外参数 ---
                futures.append(executor.submit(
                    self.translate_batch_worker,
                    batch,
                    context,
                    world_dictionary, # 确保已加载
                    client,           # 确保已初始化
                    config,           # 包含总数的配置副本
                    translated_data,
                    results_lock,
                    progress_lock,
                    processed_count_shared, # 传递共享计数器状态字典
                    error_log_path,
                    error_log_lock
                ))
                # self.thread_log(f"已提交第 {i//batch_size + 1} 批翻译任务") # 这个日志可能过多，注释掉

            # --- 修改：添加进度更新循环 ---
            completed_futures = 0
            total_futures = len(futures)
            last_logged_percent = -1
            while completed_futures < total_futures:
                # 检查已完成的任务 (可以设置超时)
                done, not_done = concurrent.futures.wait(futures, timeout=1.0, return_when=concurrent.futures.FIRST_COMPLETED)
                completed_futures += len(done)

                # 更新进度
                # processed_now = processed_count_shared.value # 使用 Value
                processed_now = processed_count_shared['value'] # 使用字典计数器
                progress_percent = (processed_now / total_items) * 100 if total_items > 0 else 0
                # 避免过于频繁地更新状态栏，可以每隔5%或10%更新一次
                if int(progress_percent // 5) > last_logged_percent: # 每5%更新一次
                    status_message = f"正在翻译JSON... {processed_now}/{total_items} ({progress_percent:.1f}%)"
                    self.thread_update_status(status_message)
                    self.thread_log(status_message) # 同时记录日志
                    last_logged_percent = int(progress_percent // 5)

                # (可选) 检查异常
                for future in done:
                    try:
                        future.result() # 获取结果或抛出异常
                    except Exception as future_err:
                        # 这里的错误通常是 worker 内部未捕获的意外错误
                        self.thread_log(f"线程池任务异常: {future_err}", "error")

                # 更新 future 列表，移除已完成的
                futures = list(not_done)
                if not futures: # 如果所有任务都完成了，退出循环
                    break

            # 确保最终进度显示100%
            self.thread_update_status(f"正在翻译JSON... {total_items}/{total_items} (100.0%)")
            self.thread_log("所有翻译任务已完成（或出错）")
            # ----------------------------

        # 7. 保存翻译后的JSON
        self.thread_log("所有翻译任务完成，正在保存结果...")

        # --- 添加：检查错误日志 ---
        error_count_in_log = 0
        if os.path.exists(error_log_path):
            try:
                with open(error_log_path, 'r', encoding='utf-8') as elog_read:
                    # 简单地计算分隔符数量来估计错误条目数
                    log_content = elog_read.read()
                    error_count_in_log = log_content.count("-" * 20)
                if error_count_in_log > 0:
                     # 使用 error 级别日志，更醒目
                    self.thread_log(f"警告: 检测到 {error_count_in_log} 个翻译条目无法自动修正并回退到原文。", "error")
                    self.thread_log(f"详情请查看错误日志: {error_log_path}", "error")
                    # 可以考虑在主界面的状态栏也提示，但日志已经很明显了
                    # self.thread_show_error(f"警告: {error_count_in_log} 个翻译使用了原文回退，请检查日志: {error_log_path}")

            except Exception as read_log_err:
                self.thread_log(f"读取错误日志时出错: {read_log_err}", "error")
        # --------------------------

        try:
            with open(translated_json_path, 'w', encoding='utf-8') as f:
                json.dump(translated_data, f, ensure_ascii=False, indent=4)

            self.thread_update_status("JSON文件翻译完成")
            if error_count_in_log == 0:
                self.thread_show_success(f"JSON文件翻译完成，结果已保存: {translated_json_path}")
            else:
                # 结果依然是成功保存，但带有警告
                self.thread_show_success(f"JSON文件翻译完成（有 {error_count_in_log} 个条目使用原文回退），结果已保存: {translated_json_path}")

        except Exception as save_err:
            self.thread_show_error(f"保存翻译后的JSON文件失败: {str(save_err)}")

    # --- 释放和导入功能 ---
    def load_translations(self, json_path):
        with open(json_path, 'r', encoding='utf-8') as file:
            return json.load(file)

    def process_translation_file(self, file_path, translations):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()
        except Exception as e:
            self.thread_log(f"读取文件失败: {file_path}: {str(e)}", "error")
            return 0

        new_lines = []
        i = 0
        translated_count = 0

        while i < len(lines):
            line = lines[i]
            match = re.match(r'#(.+)#', line.strip())
            if match:
                title = match.group(1)
                new_lines.append(line)
                i += 1
                if title == 'Message' or title == 'Choice':
                    message = ''
                    start_line_index = i # 记录消息开始的行号
                    while i < len(lines) and not lines[i].strip() == '##':
                        message += lines[i]
                        i += 1
                    message_key = message.rstrip('\n') # 使用去除尾部换行的作为key
                    if message_key in translations:
                        translated_message = translations[message_key]
                        # 确保输出与原始格式一致（是否有尾部换行符）
                        if message.endswith('\n') and not translated_message.endswith('\n'):
                            translated_message += '\n'
                        elif not message.endswith('\n') and translated_message.endswith('\n'):
                             translated_message = translated_message.rstrip('\n')
                        new_lines.append(translated_message)
                        translated_count += 1
                    else:
                        new_lines.append(message) # 未找到翻译，保留原文
                    if i < len(lines): # 确保不会越界
                        new_lines.append(lines[i]) # 添加 '##' 行
                elif title != 'EventName':
                    if i < len(lines): # 确保不会越界
                        content_key = lines[i].strip()
                        if content_key in translations:
                            translated_content = translations[content_key]
                            new_lines.append(translated_content + '\n')
                            translated_count += 1
                        else:
                            new_lines.append(lines[i]) # 未找到翻译，保留原文
                    else: # title后面没有内容行了？记录一下
                         self.thread_log(f"警告: 文件 {os.path.basename(file_path)} 中的 #{title}# 后面没有内容行", "error")
            else:
                new_lines.append(line)
            i += 1

        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                file.writelines(new_lines)
        except Exception as e:
            self.thread_log(f"写入文件失败: {file_path}: {str(e)}", "error")
            return 0 # 返回0表示写入失败

        return translated_count

    def release_transjson_files(self):
        if not self.check_game_path(): return
        self.run_in_thread(self._release_transjson_files)

    def _release_transjson_files(self):
        game_path = self.game_path.get()
        string_scripts_path = os.path.join(game_path, "StringScripts")
        if not os.path.exists(string_scripts_path):
            self.thread_show_error("未找到StringScripts文件夹，请先导出文本")
            return
        game_folder_name = os.path.basename(game_path)
        translated_dir = os.path.join(self.works_dir, game_folder_name, "translated")
        if not os.path.exists(translated_dir):
            self.thread_show_error(f"未找到已翻译的文件夹: {translated_dir}")
            return
        json_files = [f for f in os.listdir(translated_dir) if f.endswith('.json')]
        if not json_files:
            self.thread_show_error(f"在 {translated_dir} 中未找到JSON文件")
            return

        json_path_to_use = None
        if len(json_files) == 1:
            json_path_to_use = os.path.join(translated_dir, json_files[0])
            self.thread_log(f"使用翻译文件: {json_files[0]}")
        else:
             # 多文件选择逻辑（使用消息队列同步结果）
            selected_file_queue = queue.Queue()
            def show_selection_dialog():
                dialog = tk.Toplevel(self.root)
                dialog.title("选择翻译文件")
                dialog.geometry("400x300")
                dialog.transient(self.root)
                dialog.grab_set()
                ttk.Label(dialog, text="请选择要导入的翻译文件:").pack(pady=10)
                listbox = tk.Listbox(dialog, width=50, height=10)
                listbox.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
                for file in json_files: listbox.insert(tk.END, file)
                def on_select():
                    if listbox.curselection():
                        selected_file_queue.put(json_files[listbox.curselection()[0]])
                    else:
                        selected_file_queue.put(None) # 用户未选择
                    dialog.destroy()
                ttk.Button(dialog, text="选择", command=on_select).pack(pady=10)
                dialog.protocol("WM_DELETE_WINDOW", lambda: selected_file_queue.put(None) or dialog.destroy()) # 处理关闭窗口

            # 在主线程中显示对话框
            self.root.after(0, show_selection_dialog)
            # 等待用户选择结果
            selected_filename = selected_file_queue.get()

            if selected_filename:
                json_path_to_use = os.path.join(translated_dir, selected_filename)
                self.thread_log(f"使用翻译文件: {selected_filename}")
            else:
                self.thread_log("取消选择翻译文件")
                self.thread_update_status("操作已取消")
                return # 用户取消，退出线程

        if not json_path_to_use: # 双重检查
            return

        self.thread_update_status("正在释放JSON文件...")
        try:
            translations = self.load_translations(json_path_to_use)
            self.thread_log(f"已加载 {len(translations)} 个翻译条目")
            file_count = 0
            total_translated = 0
            for root, dirs, files in os.walk(string_scripts_path):
                for file in files:
                    if file.endswith('.txt'):
                        file_path = os.path.join(root, file)
                        translated = self.process_translation_file(file_path, translations)
                        total_translated += translated
                        file_count += 1
            self.thread_update_status("JSON文件释放完成")
            self.thread_show_success(f"已将翻译应用到StringScripts文件夹，处理了 {file_count} 个文件，应用了 {total_translated} 个翻译")
        except Exception as e:
            self.thread_update_status("释放JSON文件过程中出错")
            self.thread_show_error(f"释放JSON文件过程中出错: {str(e)}")

    def import_text(self):
        if not self.check_game_path(): return
        self.run_in_thread(self._import_text)

    def _import_text(self):
        game_path = self.game_path.get()
        encoding = self.import_encoding.get().split(' - ')[-1]
        self.thread_update_status(f"正在导入文本 (编码: {encoding})...")
        try:
            # ... (导入文本的代码，使用 self.thread_log) ...
            lmt_path = os.path.join(game_path, "RPG_RT.lmt")
            import_cmd = [self.rpgrewriter_path, lmt_path, "-import", "-writecode", encoding, "-nolimit", "1"]
            self.thread_log(f"执行命令: {' '.join(import_cmd)}")
            # 同样使用 Popen 处理可能的交互
            process = subprocess.Popen(import_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate()
            if stdout: self.thread_log("命令输出: " + stdout.strip())
            if stderr: self.thread_log("命令错误: " + stderr.strip(), "error")
            if process.returncode != 0: raise Exception(f"文本导入失败，返回代码: {process.returncode}")

            self.thread_update_status("文本导入完成")
            self.thread_show_success("文本已从StringScripts文件夹导入到游戏中")
        except Exception as e:
            self.thread_update_status("文本导入过程中出错")
            self.thread_show_error(f"文本导入过程中出错: {str(e)}")
    
    # --- 新增：轻松模式 - 开始翻译 ---
    def start_easy_translation(self):
        """执行轻松模式下的自动翻译流程"""
        if not self.check_game_path():
            return
        # 检查API配置是否填写（简单检查Key）
        if not self.world_dict_config.get("api_key"):
             messagebox.showwarning("配置缺失", "请先在“Gemini配置”中填写API Key。")
             return
        if not self.translate_config.get("api_key") or not self.translate_config.get("api_url"):
             messagebox.showwarning("配置缺失", "请先在“Deepseek配置”中填写API URL和API Key。")
             return

        # 重置进度和状态
        self.easy_mode_progress_var.set(0.0)
        self.easy_mode_status_var.set("准备开始...")
        self.run_in_thread(self._run_easy_mode_sequence)

    def _run_easy_mode_sequence(self):
        """在线程中按顺序执行所有翻译步骤"""
        steps = [
            ("初始化", self._initialize_game),
            ("重写文件名", self._rename_files),
            ("导出文本", self._export_text),
            ("制作JSON文件", self._create_transjson_files),
            ("生成世界观字典", self._generate_world_dict),
            ("翻译JSON文件", self._translate_json),
            ("释放JSON文件", self._release_transjson_files),
            ("导入文本", self._import_text),
        ]
        total_steps = len(steps)
        current_step_num = 0

        try:
            for name, func in steps:
                current_step_num += 1
                self.thread_update_status(f"({current_step_num}/{total_steps}) 正在执行: {name}...")
                self.message_queue.put(("easy_status", f"({current_step_num}/{total_steps}) 正在执行: {name}..."))

                # 调用实际的步骤函数
                func() # 这些函数内部会处理日志和错误

                # 更新进度条 (放在成功完成一步后)
                progress_value = (current_step_num / total_steps) * 100
                self.message_queue.put(("progress", progress_value))
                self.thread_log(f"步骤 '{name}' 完成。")

            self.thread_update_status("轻松模式翻译流程完成！")
            self.message_queue.put(("easy_status", "轻松模式翻译流程完成！"))
            self.thread_show_success("所有步骤已成功完成。")

        except Exception as e:
            # 错误已在 run_in_thread 的 wrapper 中捕获并记录
            # 这里仅更新轻松模式的状态标签
            failed_step_name = steps[current_step_num - 1][0] if current_step_num > 0 else "未知步骤"
            error_msg = f"在步骤 '{failed_step_name}' 中止 ({current_step_num}/{total_steps})"
            self.message_queue.put(("easy_status", error_msg))
            # 标记进度条为不确定或红色（可选，当前只停止）
            # self.message_queue.put(("progress_error", True)) # 示例：发送错误信号
            # 注意：run_in_thread 已经记录了详细错误

    # --- 新增：轻松模式 - 开始游戏 ---
    def start_game(self):
        """尝试运行游戏目录下的Player.exe"""
        if not self.check_game_path():
            return

        game_path = self.game_path.get()
        player_exe_path = os.path.join(game_path, "Player.exe") # EasyRPG Player 可执行文件

        if not os.path.exists(player_exe_path):
            # 尝试查找 RPG_RT.exe 作为备选
            player_exe_path = os.path.join(game_path, "RPG_RT.exe")
            if not os.path.exists(player_exe_path):
                self.show_error(f"未在游戏目录中找到 Player.exe 或 RPG_RT.exe")
                messagebox.showerror("启动失败", f"未在以下路径找到 Player.exe 或 RPG_RT.exe：\n{game_path}")
                return

        self.log(f"正在尝试启动游戏: {player_exe_path}")
        try:
            # 使用 Popen 在后台启动，不阻塞UI
            # 在Windows上，如果路径包含空格，可能需要引号，但 os.path.join 通常能处理
            # 注意：cwd 设置为游戏目录，确保游戏能正确加载资源
            subprocess.Popen([player_exe_path], cwd=game_path)
            self.show_success("游戏已启动（在单独的进程中）")
        except FileNotFoundError:
             self.show_error(f"启动失败: 未找到文件 {player_exe_path}")
             messagebox.showerror("启动失败", f"无法启动游戏，未找到文件：\n{player_exe_path}")
        except OSError as e:
            self.show_error(f"启动游戏时发生错误: {e}")
            messagebox.showerror("启动失败", f"启动游戏时发生操作系统错误：\n{e}")
        except Exception as e:
            self.show_error(f"启动游戏时发生未知错误: {e}")
            messagebox.showerror("启动失败", f"启动游戏时发生未知错误：\n{e}")

    # --- RTP选择方法---
    def _update_rtp_button_text(self):
        """根据当前选择更新RTP按钮文本"""
        selected_rtps = []
        if self.rtp_2000.get(): selected_rtps.append("2000")
        if self.rtp_2000en.get(): selected_rtps.append("2000en")
        if self.rtp_2003.get(): selected_rtps.append("2003")
        if self.rtp_2003steam.get(): selected_rtps.append("2003steam")

        if not selected_rtps:
            self.rtp_button_text.set("RTP选择: 无")
        elif len(selected_rtps) == 1:
            self.rtp_button_text.set(f"RTP选择: {selected_rtps[0]}")
        else:
            self.rtp_button_text.set(f"RTP选择: {len(selected_rtps)}个")

    def show_rtp_selection(self):
        rtp_window = tk.Toplevel(self.root)
        rtp_window.title("选择RTP")
        rtp_window.geometry("240x200")
        rtp_window.transient(self.root)
        rtp_window.grab_set()
        rtp_window.resizable(False, False)

        # 尝试将窗口定位在按钮附近 (可能需要微调)
        try:
            # 找到RTP按钮的位置来定位窗口，需要按钮可见
            # 这部分逻辑比较复杂，可能需要按钮实际渲染后才能获取位置
            # 暂时简化为屏幕相对位置
            x = self.root.winfo_rootx() + self.root.winfo_width() - 550 # 调整 X 偏移
            y = self.root.winfo_rooty() + 150 # 调整 Y 偏移
            rtp_window.geometry(f"+{x}+{y}")
        except: # 防御性编程，如果获取位置失败则忽略
            pass

        frame = ttk.Frame(rtp_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="选择要安装的RTP文件:").pack(anchor=tk.W, pady=(0, 5))
        ttk.Checkbutton(frame, text="RPG Maker 2000", variable=self.rtp_2000).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(frame, text="RPG Maker 2000 (英文版)", variable=self.rtp_2000en).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(frame, text="RPG Maker 2003", variable=self.rtp_2003).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(frame, text="RPG Maker 2003 (Steam版)", variable=self.rtp_2003steam).pack(anchor=tk.W, pady=2)

        def on_confirm():
            self._update_rtp_button_text() # 调用更新函数
            rtp_window.destroy()

        ttk.Button(frame, text="确定", command=on_confirm).pack(anchor=tk.CENTER, pady=(10, 0))
    
    # --- 配置窗口打开方法 ---
    def edit_world_dict(self):
        """打开世界观字典表格编辑器"""
        game_path = self.game_path.get()
        if not game_path:
            self.show_error("请先选择游戏目录")
            return
            
        game_folder_name = os.path.basename(game_path)
        work_dir = os.path.join(self.works_dir, game_folder_name)
        dict_csv_path = os.path.join(work_dir, "world_dictionary.csv")
        
        # 如果目录不存在则创建
        os.makedirs(work_dir, exist_ok=True)
        
        # 如果文件不存在则创建空字典
        if not os.path.exists(dict_csv_path):
            with open(dict_csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['原文', '译文', '类别', '描述'])
            self.show_success("已创建新的空字典文件")
            
        try:
            # 读取CSV文件内容
            with open(dict_csv_path, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.reader(f)
                data = list(reader)
                
            # 创建表格编辑器窗口
            edit_window = tk.Toplevel(self.root)
            edit_window.title("世界观字典编辑器")
            edit_window.geometry("1000x600")
            
            # 表格框架
            table_frame = ttk.Frame(edit_window)
            table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # 表格（启用编辑）
            self.dict_table = ttk.Treeview(table_frame, columns=('original', 'translation', 'category', 'description'), 
                                         show='headings', selectmode='extended')
            
            # 绑定双击编辑事件
            self.dict_table.bind('<Double-1>', self.on_cell_edit)
            
            # 设置列标题
            self.dict_table.heading('original', text='原文')
            self.dict_table.heading('translation', text='译文')
            self.dict_table.heading('category', text='类别')
            self.dict_table.heading('description', text='描述')
            
            # 设置列宽
            self.dict_table.column('original', width=200, anchor='w')
            self.dict_table.column('translation', width=200, anchor='w')
            self.dict_table.column('category', width=100, anchor='w')
            self.dict_table.column('description', width=400, anchor='w')
            
            # 添加滚动条
            scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.dict_table.yview)
            self.dict_table.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side="right", fill="y")
            self.dict_table.pack(fill="both", expand=True)
            
            # 填充数据(跳过表头行但保持可编辑)
            if data:  # 确保有数据
                for row in data[1:]:  # 跳过第一行表头
                    item = self.dict_table.insert('', 'end', values=row)
                    # 为每列设置可编辑状态
                    for i, col in enumerate(['original', 'translation', 'category', 'description']):
                        self.dict_table.set(item, col, row[i])
                
            # 按钮区域
            button_frame = ttk.Frame(edit_window)
            button_frame.pack(fill=tk.X, padx=5, pady=5)
            
            # 添加行按钮
            ttk.Button(button_frame, text="添加行", command=lambda: self.dict_table.insert('', 'end', values=['','','',''])).pack(side=tk.LEFT, padx=5)
            
            # 删除行按钮
            ttk.Button(button_frame, text="删除行", command=lambda: self.dict_table.delete(self.dict_table.selection()[0]) 
                      if self.dict_table.selection() else None).pack(side=tk.LEFT, padx=5)
            
            # 保存按钮
            ttk.Button(button_frame, text="保存", command=lambda: self.save_dict_table(dict_csv_path, edit_window)).pack(side=tk.RIGHT, padx=5)
            
            # 取消按钮
            ttk.Button(button_frame, text="取消", command=edit_window.destroy).pack(side=tk.RIGHT, padx=5)
            
        except Exception as e:
            self.show_error(f"打开字典编辑器失败: {str(e)}")

    def on_cell_edit(self, event):
        """处理单元格编辑"""
        region = self.dict_table.identify('region', event.x, event.y)
        if region != 'cell':
            return
            
        column = self.dict_table.identify_column(event.x)
        item = self.dict_table.identify_row(event.y)
        
        if not item or not column:
            return
            
        # 获取当前值
        col_index = int(column[1:]) - 1
        current_values = list(self.dict_table.item(item, 'values'))
        current_value = current_values[col_index]
        
        # 创建编辑框
        entry = ttk.Entry(self.dict_table)
        entry.insert(0, current_value)
        entry.select_range(0, tk.END)
        entry.focus()
        
        def save_edit(event):
            new_value = entry.get()
            current_values[col_index] = new_value
            self.dict_table.item(item, values=current_values)
            entry.destroy()
            
        entry.bind('<Return>', save_edit)
        entry.bind('<FocusOut>', lambda e: entry.destroy())
        
        # 定位并显示编辑框
        x, y, width, height = self.dict_table.bbox(item, column)
        entry.place(x=x, y=y, width=width, height=height)

    def save_dict_table(self, dict_path, window):
        """保存表格编辑器中的字典内容"""
        try:
            # 获取表格中的所有数据
            data = []
            # 添加表头行
            headers = ['原文', '译文', '类别', '描述']
            data.append(headers)
            
            # 添加数据行
            for child in self.dict_table.get_children():
                data.append(self.dict_table.item(child)['values'])
                
            # 写入CSV文件
            with open(dict_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(data)
                
            self.show_success("字典已保存")
            window.destroy()
        except Exception as e:
            self.show_error(f"保存字典失败: {str(e)}")

    def open_world_dict_config(self):
        WorldDictConfigWindow(self, self.world_dict_config)

    def open_translate_config(self):
        TranslateConfigWindow(self, self.translate_config)

# --- 新增：世界观字典配置窗口 ---
class WorldDictConfigWindow(tk.Toplevel):
    def __init__(self, parent_app, config): # 传入主应用实例 parent_app
        super().__init__(parent_app.root) # 父窗口是主应用的 root
        self.initializing = True
        self.parent_app = parent_app
        self.config = config
        self.initial_config = config.copy() # 保存初始配置用于比较
        self.connection_tested_ok = False   # 标记连接测试是否通过
        self.transient(parent_app.root)
        self.grab_set()
        self.title("世界观字典配置 (Gemini)")
        self.geometry("600x550") # 稍微增加高度容纳测试按钮和状态

        frame = ttk.Frame(self, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        # API Key
        key_frame = ttk.Frame(frame)
        key_frame.pack(fill=tk.X, pady=5)
        ttk.Label(key_frame, text="Gemini API Key:", width=15).pack(side=tk.LEFT)
        self.api_key_var = tk.StringVar(value=config.get("api_key", ""))
        self.api_key_entry = ttk.Entry(key_frame, textvariable=self.api_key_var, width=50, show="*") # 隐藏Key
        self.api_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        # 添加显示/隐藏按钮
        self.show_key_var = tk.BooleanVar(value=False)
        key_toggle_button = ttk.Checkbutton(key_frame, text="显示", variable=self.show_key_var, command=self.toggle_key_visibility)
        key_toggle_button.pack(side=tk.LEFT)


        # Model Name
        model_frame = ttk.Frame(frame)
        model_frame.pack(fill=tk.X, pady=5)
        ttk.Label(model_frame, text="模型名称:", width=15).pack(side=tk.LEFT)
        self.model_var = tk.StringVar(value=config.get("model", "gemini-2.5-pro-exp-03-25"))
        # 提供一些常用的Gemini模型选项
        model_combobox = ttk.Combobox(model_frame, textvariable=self.model_var, values=[
            "gemini-2.5-pro-exp-03-25",
            "gemini-1.5-pro-latest",
            "gemini-pro", # 旧版Pro
        ], width=48)
        model_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Prompt
        prompt_frame = ttk.LabelFrame(frame, text="Prompt", padding="5")
        prompt_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.prompt_text = tk.Text(prompt_frame, wrap=tk.WORD, height=15)
        self.prompt_text.insert(tk.END, config.get("prompt", ""))
        self.prompt_text.edit_modified(False)
        prompt_scroll = ttk.Scrollbar(prompt_frame, command=self.prompt_text.yview)
        self.prompt_text.configure(yscrollcommand=prompt_scroll.set)
        prompt_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.prompt_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 状态标签
        self.status_var = tk.StringVar(value="请先测试连接")
        status_label = ttk.Label(frame, textvariable=self.status_var, foreground="orange")
        status_label.pack(fill=tk.X, pady=(5, 0))

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=10)
        self.save_button = ttk.Button(button_frame, text="保存", command=self.save_config, state=tk.DISABLED)
        self.save_button.pack(side=tk.RIGHT, padx=5)
        self.test_button = ttk.Button(button_frame, text="测试连接", command=self.test_connection)
        self.test_button.pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="取消", command=self.destroy).pack(side=tk.RIGHT)

        # 绑定修改事件，以便在更改后需要重新测试
        self.api_key_var.trace_add("write", self.on_config_change)
        self.model_var.trace_add("write", self.on_config_change)
        self.prompt_text.bind("<<Modified>>", self.on_prompt_change)

        # --- 新增：初始化完成 ---
        self.initializing = False

        # 检查初始状态，如果key存在，提示测试
        if self.api_key_var.get():
             self.set_status("配置已加载，请测试连接", "orange")
        else:
            self.set_status("请输入 API Key 并测试连接", "red")

    def toggle_key_visibility(self):
        """切换API Key的显示状态"""
        if self.show_key_var.get():
            self.api_key_entry.config(show="")
        else:
            self.api_key_entry.config(show="*")

    def on_prompt_change(self, event=None):
        """处理Prompt文本框的修改事件"""
        # --- 新增：检查初始化标志 ---
        if self.initializing:
            return
        # Text控件的Modified事件比较特殊，需要重置标志位
        self.prompt_text.edit_modified(False)
        self.on_config_change()

    def on_config_change(self, *args):
        """配置发生变化时的处理"""
        # --- 新增：检查初始化标志 ---
        if self.initializing:
            return
        self.connection_tested_ok = False
        self.save_button.config(state=tk.DISABLED)
        self.set_status("配置已更改，请重新测试连接", "orange")

    def set_status(self, message, color):
        """更新状态标签的文本和颜色"""
        self.status_var.set(message)
        self.children['!frame'].children['!label'].config(foreground=color) # 更新状态标签颜色

    def test_connection(self):
        """启动连接测试线程"""
        api_key = self.api_key_var.get().strip()
        model = self.model_var.get().strip()
        if not api_key:
            messagebox.showerror("错误", "请输入 Gemini API Key")
            return
        if not model:
            messagebox.showerror("错误", "请输入模型名称")
            return

        self.set_status("正在测试连接...", "blue")
        self.test_button.config(state=tk.DISABLED)
        self.save_button.config(state=tk.DISABLED)

        # 使用线程执行测试，避免阻塞UI
        thread = threading.Thread(target=self._test_connection_thread, args=(api_key, model), daemon=True)
        thread.start()

    def _test_connection_thread(self, api_key, model):
        """在线程中执行实际的API连接测试"""
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model, contents="你好吗？"
            )
            if response and response.text:
                self.after(0, self.test_success) # 使用after在主线程更新UI
            else:
                self.after(0, lambda: self.test_failure("连接成功，但未收到有效响应。"))

        except Exception as e:
            # 捕获更具体的错误类型可以提供更好的反馈
            error_message = f"连接失败: {type(e).__name__} - {e}"
            # 尝试从异常中获取更详细的信息
            if hasattr(e, 'message'):
                 error_message = f"连接失败: {e.message}"
            elif hasattr(e, 'reason'):
                 error_message = f"连接失败: {e.reason}"

            self.after(0, lambda: self.test_failure(error_message)) # 使用after在主线程更新UI

    def test_success(self):
        """连接测试成功后的UI更新"""
        self.connection_tested_ok = True
        self.set_status("连接成功!", "green")
        self.test_button.config(state=tk.NORMAL)
        # 只有测试成功才允许保存
        self.save_button.config(state=tk.NORMAL)
        messagebox.showinfo("成功", "Gemini API 连接测试成功！")

    def test_failure(self, error_message):
        """连接测试失败后的UI更新"""
        self.connection_tested_ok = False
        self.set_status(f"连接失败", "red") # 简短状态
        self.test_button.config(state=tk.NORMAL)
        self.save_button.config(state=tk.DISABLED)
        messagebox.showerror("连接失败", error_message) # 详细错误弹窗

    def save_config(self):
        """保存配置"""
        if not self.connection_tested_ok:
            messagebox.showwarning("无法保存", "请先成功测试连接后再保存。")
            return

        # 更新内存中的配置字典
        self.config["api_key"] = self.api_key_var.get()
        self.config["model"] = self.model_var.get()
        self.config["prompt"] = self.prompt_text.get("1.0", tk.END).strip()

        # 调用主应用的保存方法来写入文件
        self.parent_app.save_config()

        # 更新初始配置状态，以便下次比较
        self.initial_config = self.config.copy()
        self.set_status("配置已保存", "green")
        # 保存后禁用保存按钮，直到再次修改
        self.save_button.config(state=tk.DISABLED)
        # messagebox.showinfo("保存成功", "世界观字典配置已更新并保存。") # save_config已有日志
        self.destroy() # 关闭窗口

# --- 新增：翻译JSON配置窗口 ---
class TranslateConfigWindow(tk.Toplevel):
    def __init__(self, parent_app, config): # 传入主应用实例 parent_app
        super().__init__(parent_app.root) # 父窗口是主应用的 root
        self.initializing = True
        self.parent_app = parent_app
        self.config = config
        self.initial_config = config.copy() # 保存初始配置用于比较
        self.connection_tested_ok = False   # 标记连接测试是否通过
        self.transient(parent_app.root)
        self.grab_set()
        self.title("翻译JSON文件配置 (OpenAI兼容)")
        self.geometry("600x450") # 稍微增加高度

        frame = ttk.Frame(self, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        # API URL
        url_frame = ttk.Frame(frame)
        url_frame.pack(fill=tk.X, pady=5)
        ttk.Label(url_frame, text="API URL:", width=15).pack(side=tk.LEFT)
        self.api_url_var = tk.StringVar(value=config.get("api_url", "https://ark.cn-beijing.volces.com/api/v3"))
        self.api_url_entry = ttk.Entry(url_frame, textvariable=self.api_url_var, width=50)
        self.api_url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # API Key
        key_frame = ttk.Frame(frame)
        key_frame.pack(fill=tk.X, pady=5)
        ttk.Label(key_frame, text="API Key:", width=15).pack(side=tk.LEFT)
        self.api_key_var = tk.StringVar(value=config.get("api_key", ""))
        self.api_key_entry = ttk.Entry(key_frame, textvariable=self.api_key_var, width=50, show="*")
        self.api_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        # 添加显示/隐藏按钮
        self.show_key_var = tk.BooleanVar(value=False)
        key_toggle_button = ttk.Checkbutton(key_frame, text="显示", variable=self.show_key_var, command=self.toggle_key_visibility)
        key_toggle_button.pack(side=tk.LEFT)

        # Model Name
        model_frame = ttk.Frame(frame)
        model_frame.pack(fill=tk.X, pady=5)
        ttk.Label(model_frame, text="模型名称:", width=15).pack(side=tk.LEFT)
        self.model_var = tk.StringVar(value=config.get("model", "deepseek-v3-250324"))
        # 提供一些常用OpenAI兼容模型选项
        model_combobox = ttk.Combobox(model_frame, textvariable=self.model_var, values=[
            "deepseek-v3-250324", "deepseek-r1-250120", # 火山引擎
            "deepseek-chat", "deepseek-reasoner" # Deepseek官方
            # 添加其他你可能使用的模型
        ], width=48)
        model_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Spinboxes in a subframe for better layout
        spinbox_frame = ttk.Frame(frame)
        spinbox_frame.pack(fill=tk.X, pady=5)

        # Batch Size
        batch_frame = ttk.Frame(spinbox_frame)
        batch_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(batch_frame, text="批次大小:", width=8).pack(side=tk.LEFT)
        self.batch_var = tk.IntVar(value=config.get("batch_size", 10))
        self.batch_spinbox = ttk.Spinbox(batch_frame, from_=1, to=100, textvariable=self.batch_var, width=5)
        self.batch_spinbox.pack(side=tk.LEFT)

        # Context Lines
        context_frame = ttk.Frame(spinbox_frame)
        context_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(context_frame, text="上文行数:", width=8).pack(side=tk.LEFT)
        self.context_var = tk.IntVar(value=config.get("context_lines", 10))
        self.context_spinbox = ttk.Spinbox(context_frame, from_=0, to=50, textvariable=self.context_var, width=5)
        self.context_spinbox.pack(side=tk.LEFT)

        # Concurrency
        concur_frame = ttk.Frame(spinbox_frame)
        concur_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(concur_frame, text="并发数:", width=6).pack(side=tk.LEFT)
        self.concur_var = tk.IntVar(value=config.get("concurrency", 16))
        self.concur_spinbox = ttk.Spinbox(concur_frame, from_=1, to=64, textvariable=self.concur_var, width=5)
        self.concur_spinbox.pack(side=tk.LEFT)

        # 语言选择
        lang_frame = ttk.Frame(frame)
        lang_frame.pack(fill=tk.X, pady=5)

        # 源语言
        source_lang_frame = ttk.Frame(lang_frame)
        source_lang_frame.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Label(source_lang_frame, text="源语言:", width=8).pack(side=tk.LEFT)
        self.source_lang_var = tk.StringVar(value=config.get("source_language", "日语"))
        source_lang_combobox = ttk.Combobox(source_lang_frame, textvariable=self.source_lang_var, values=[
            "日语", "英语", "韩语", "俄语", "法语", "德语", "西班牙语"
        ], width=15)
        source_lang_combobox.pack(side=tk.LEFT, padx=5)

        # 目标语言
        target_lang_frame = ttk.Frame(lang_frame)
        target_lang_frame.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Label(target_lang_frame, text="目标语言:", width=8).pack(side=tk.LEFT)
        self.target_lang_var = tk.StringVar(value=config.get("target_language", "简体中文"))
        target_lang_combobox = ttk.Combobox(target_lang_frame, textvariable=self.target_lang_var, values=[
            "简体中文", "繁体中文", "英语", "日语", "韩语", "俄语", "法语", "德语", "西班牙语"
        ], width=15)
        target_lang_combobox.pack(side=tk.LEFT, padx=5)

        # Prompt Template
        prompt_frame = ttk.LabelFrame(frame, text="Prompt 模板", padding="5")
        prompt_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.prompt_text = scrolledtext.ScrolledText(prompt_frame, wrap=tk.WORD, height=5)
        self.prompt_text.insert(tk.END, config.get("prompt_template", ""))
        self.prompt_text.edit_modified(False)
        self.prompt_text.pack(fill=tk.BOTH, expand=True)
        self.prompt_text.bind("<<Modified>>", self.on_prompt_change)

        # 状态标签
        self.status_var = tk.StringVar(value="请先测试连接")
        status_label = ttk.Label(frame, textvariable=self.status_var, foreground="orange")
        status_label.pack(fill=tk.X, pady=(5, 0))

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=10)
        self.save_button = ttk.Button(button_frame, text="保存", command=self.save_config, state=tk.DISABLED)
        self.save_button.pack(side=tk.RIGHT, padx=5)
        self.test_button = ttk.Button(button_frame, text="测试连接", command=self.test_connection)
        self.test_button.pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="取消", command=self.destroy).pack(side=tk.RIGHT)

        # 绑定修改事件
        self.api_url_var.trace_add("write", self.on_config_change)
        self.api_key_var.trace_add("write", self.on_config_change)
        self.model_var.trace_add("write", self.on_config_change)
        self.batch_var.trace_add("write", self.on_config_change)
        self.context_var.trace_add("write", self.on_config_change)
        self.concur_var.trace_add("write", self.on_config_change)
        self.source_lang_var.trace_add("write", self.on_config_change)
        self.target_lang_var.trace_add("write", self.on_config_change)

        # --- 新增：初始化完成 ---
        self.initializing = False

    def on_prompt_change(self, event=None):
        """处理Prompt文本的修改事件"""
        # --- 新增：检查初始化标志 ---
        if self.initializing:
            return
        if hasattr(self, 'prompt_text'):
            # Text控件的Modified事件需要重置标志位
            self.prompt_text.edit_modified(False)
            self.on_config_change()

        # 检查初始状态
        if self.api_key_var.get() and self.api_url_var.get():
            self.set_status("配置已加载，请测试连接", "orange")
        else:
            self.set_status("请输入 API URL 和 Key 并测试连接", "red")

    def toggle_key_visibility(self):
        """切换API Key的显示状态"""
        if self.show_key_var.get():
            self.api_key_entry.config(show="")
        else:
            self.api_key_entry.config(show="*")

    def on_config_change(self, *args):
        """配置发生变化时的处理"""
        # --- 新增：检查初始化标志 ---
        if self.initializing:
            return
        # Spinbox 的 trace 可能触发多次，简单处理
        if not hasattr(self, 'save_button') or not self.save_button.winfo_exists():
             return # 防止窗口销毁后还触发trace
        self.connection_tested_ok = False
        self.save_button.config(state=tk.DISABLED)
        self.set_status("配置已更改，请重新测试连接", "orange")

    def set_status(self, message, color):
        """更新状态标签的文本和颜色"""
        self.status_var.set(message)
        # 定位状态标签并更新颜色
        status_widget = None
        for widget in self.children['!frame'].winfo_children():
            if isinstance(widget, ttk.Label) and hasattr(widget, 'cget') and 'textvariable' in widget.keys() and str(widget.cget('textvariable')) == str(self.status_var):
                 status_widget = widget
                 break
        if status_widget:
            status_widget.config(foreground=color)


    def test_connection(self):
        """启动连接测试线程"""
        api_key = self.api_key_var.get().strip()
        api_url = self.api_url_var.get().strip()
        if not api_key or not api_url:
            messagebox.showerror("错误", "请输入 API URL 和 API Key")
            return

        self.set_status("正在测试连接...", "blue")
        self.test_button.config(state=tk.DISABLED)
        self.save_button.config(state=tk.DISABLED)

        # 使用线程执行测试
        thread = threading.Thread(target=self._test_connection_thread, args=(api_url, api_key), daemon=True)
        thread.start()

    def _test_connection_thread(self, api_url, api_key):
        """在线程中执行实际的API连接测试"""
        try:
            client = OpenAI(base_url=api_url, api_key=api_key)
            response = client.chat.completions.create(
                model=self.model_var.get().strip(),
                messages=[{"role": "user", "content": "你好吗？"}]
            )
            if response and response.choices[0].message.content:
                self.after(0, self.test_success)
            else:
                self.after(0, lambda: self.test_failure("连接成功，但未收到有效响应。"))

        except Exception as e:
            error_message = f"连接失败: {type(e).__name__} - {e}"
            self.after(0, lambda: self.test_failure(error_message))

    def test_success(self):
        """连接测试成功后的UI更新"""
        self.connection_tested_ok = True
        self.set_status("连接成功!", "green")
        self.test_button.config(state=tk.NORMAL)
        self.save_button.config(state=tk.NORMAL) # 测试成功即可保存
        messagebox.showinfo("成功", "API 连接测试成功！")

    def test_failure(self, error_message):
        """连接测试失败后的UI更新"""
        self.connection_tested_ok = False
        self.set_status(f"连接失败", "red")
        self.test_button.config(state=tk.NORMAL)
        self.save_button.config(state=tk.DISABLED)
        messagebox.showerror("连接失败", error_message)

    def save_config(self):
        """保存配置"""
        if not self.connection_tested_ok:
            messagebox.showwarning("无法保存", "请先成功测试连接后再保存。")
            return

        # 更新内存中的配置字典
        self.config["api_url"] = self.api_url_var.get()
        self.config["api_key"] = self.api_key_var.get()
        self.config["model"] = self.model_var.get()
        self.config["batch_size"] = self.batch_var.get()
        self.config["context_lines"] = self.context_var.get()
        self.config["concurrency"] = self.concur_var.get()
        self.config["source_language"] = self.source_lang_var.get()
        self.config["target_language"] = self.target_lang_var.get()
        self.config["prompt_template"] = self.prompt_text.get("1.0", tk.END).strip()

        # 调用主应用的保存方法
        self.parent_app.save_config()

        # 更新初始配置状态
        self.initial_config = self.config.copy()
        self.set_status("配置已保存", "green")
        self.save_button.config(state=tk.DISABLED) # 保存后禁用，直到修改
        # messagebox.showinfo("保存成功", "翻译JSON文件配置已更新并保存。")
        self.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    # 添加样式，可选
    style = ttk.Style(root)
    try:
        style.theme_use('Breeze')
    except tk.TclError:
        pass
    app = RPGTranslationAssistant(root)
    root.mainloop()
