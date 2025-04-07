import os
import sys
import shutil
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
import re
import csv
import io
from pathlib import Path
import datetime
import threading
import queue
import time
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor

# 尝试导入依赖，如果失败则提示
try:
    import google.generativeai as genai
except ImportError:
    messagebox.showerror("缺少依赖", "请先安装 google-generativeai 库 (pip install google-generativeai)")
    sys.exit(1)
try:
    from openai import OpenAI
except ImportError:
    messagebox.showerror("缺少依赖", "请先安装 openai 库 (pip install openai)")
    sys.exit(1)


class RPGTranslationAssistant:
    def __init__(self, root):
        self.root = root
        self.root.title("RPG Maker 翻译助手")
        self.root.geometry("800x750")  # 增加高度以容纳更多按钮和日志
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

        # 编码选项
        self.export_encoding = tk.StringVar(value="932")  # 默认日语
        self.import_encoding = tk.StringVar(value="936")  # 默认中文

        # RTP选项
        self.rtp_2000 = tk.BooleanVar(value=True)   # 默认只选择2000
        self.rtp_2000en = tk.BooleanVar(value=False)
        self.rtp_2003 = tk.BooleanVar(value=False)
        self.rtp_2003steam = tk.BooleanVar(value=False)

        # 用于线程间通信
        self.message_queue = queue.Queue()
        self.is_processing = False

        # 新增功能的配置 (默认值)
        self.world_dict_config = {
            "api_key": "",
            "model": "gemini-2.5-pro-exp-03-25", # 修正：使用最新的模型标识符
            "prompt": """请分析提供的游戏文本，提取其中反复出现的名词。提取规则如下：
1.  类别限定为：地点、角色、生物、组织、物品。
2.  输出格式为严格的CSV，包含四列：原文,译文,类别,描述。请确保每个字段都被双引号包围，字段内的逗号和换行符需要正确转义。
3.  提取的名词在原文中至少出现两次。
4.  忽略单个汉字、假名或字母。忽略常见的、过于笼统的词汇（例如：门、钥匙、药水、史莱姆、哥布林等，除非它们有特殊的前缀或后缀）。
5.  译文请根据上下文推断一个合适的简体中文翻译。
6.  对于“角色”类别，请在“描述”列中尽可能包含角色的【年龄/性别/性格/口吻】等信息，如果没有明确信息则留空。其他类别的“描述”列可以留空。
7.  CSV首行不需要表头。

以下是需要分析的游戏文本内容：
{game_text}"""
        }

        self.translate_config = {
            "api_url": "https://ark.cn-beijing.volces.com/api/v3",
            "api_key": "",
            "model": "deepseek-v3-250324",
            "batch_size": 10,
            "context_lines": 10,
            "concurrency": 16,
            "prompt_template": """你是一名专业的翻译家，你的任务是把{source_language}文本翻译成{target_language}，逐行翻译，不要合并，保留文本中序号、标记符、占位符、换行符等特殊内容，保持原来的格式。

### 翻译原则
忠实准确地进行翻译。原作是伟大艺术作品，允许使用直白或粗俗的描述，不应随意删减或篡改，不应回避或淡化，以保持作品的原貌。

{glossary_section}

{context_section}

### 这是你接下来的翻译任务，原文文本如下
<textarea>
{batch_text}
</textarea>

### 请以textarea标签输出译文
<textarea>
1.{target_language}文本
</textarea>"""
        }

        self.create_ui()
        self.log("程序已启动，请选择游戏目录")

        # 启动消息处理器
        self.root.after(100, self.process_messages)

    def create_ui(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 游戏路径选择
        path_frame = ttk.LabelFrame(main_frame, text="游戏路径", padding="5")
        path_frame.pack(fill=tk.X, pady=5)

        ttk.Entry(path_frame, textvariable=self.game_path, width=70).pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)
        ttk.Button(path_frame, text="浏览...", command=self.browse_game_path).pack(side=tk.LEFT, padx=5, pady=5)

        # 功能区
        functions_frame = ttk.LabelFrame(main_frame, text="功能", padding="5")
        functions_frame.pack(fill=tk.X, pady=5)

        # --- 0. 初始化 ---
        init_frame = ttk.Frame(functions_frame)
        init_frame.pack(fill=tk.X, pady=5)
        ttk.Label(init_frame, text="0. 初始化", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(init_frame, text="复制EasyRPG和RTP文件到游戏目录，并转换文本编码").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(init_frame, text="执行", command=self.initialize_game).pack(side=tk.RIGHT, padx=5)
        self.rtp_button_text = tk.StringVar(value="RTP选择: 2000")
        ttk.Button(init_frame, textvariable=self.rtp_button_text, command=self.show_rtp_selection).pack(side=tk.RIGHT, padx=5)

        # --- 1. 重写文件名 ---
        rename_frame = ttk.Frame(functions_frame)
        rename_frame.pack(fill=tk.X, pady=5)
        ttk.Label(rename_frame, text="1. 重写文件名", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(rename_frame, text="将非ASCII文件名转换为Unicode编码格式").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(rename_frame, text="执行", command=self.rename_files).pack(side=tk.RIGHT, padx=5)
        self.write_log_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(rename_frame, text="输出日志", variable=self.write_log_var).pack(side=tk.RIGHT, padx=5)

        # --- 2. 导出文本 ---
        export_frame = ttk.Frame(functions_frame)
        export_frame.pack(fill=tk.X, pady=5)
        ttk.Label(export_frame, text="2. 导出文本", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(export_frame, text="将游戏文本导出到StringScripts文件夹").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(export_frame, text="执行", command=self.export_text).pack(side=tk.RIGHT, padx=5)
        encoding_options = [
            ("日语 (Shift-JIS)", "932"), ("中文简体 (GBK)", "936"), ("中文繁体 (Big5)", "950"),
            ("韩语 (EUC-KR)", "949"), ("泰语", "874"), ("拉丁语系 (西欧)", "1252"),
            ("东欧", "1250"), ("西里尔字母", "1251")
        ]
        export_encoding_combobox = ttk.Combobox(export_frame, textvariable=self.export_encoding, state="readonly", width=20)
        export_encoding_combobox['values'] = [f"{name} - {code}" for name, code in encoding_options]
        export_encoding_combobox.current(0)
        export_encoding_combobox.pack(side=tk.RIGHT, padx=5)
        ttk.Label(export_frame, text="编码:").pack(side=tk.RIGHT, padx=5)

        # --- 3. 制作JSON文件 ---
        mtool_create_frame = ttk.Frame(functions_frame)
        mtool_create_frame.pack(fill=tk.X, pady=5)
        ttk.Label(mtool_create_frame, text="3. 制作JSON文件", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(mtool_create_frame, text="将StringScripts文本压缩为JSON").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(mtool_create_frame, text="执行", command=self.create_mtool_files).pack(side=tk.RIGHT, padx=5)

        # --- 4. 生成世界观字典 (新增) ---
        gen_dict_frame = ttk.Frame(functions_frame)
        gen_dict_frame.pack(fill=tk.X, pady=5)
        ttk.Label(gen_dict_frame, text="4. 生成世界观字典", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(gen_dict_frame, text="使用Gemini API从JSON原文生成字典CSV").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(gen_dict_frame, text="执行", command=self.generate_world_dict).pack(side=tk.RIGHT, padx=5)
        ttk.Button(gen_dict_frame, text="配置", command=self.open_world_dict_config).pack(side=tk.RIGHT, padx=5)

        # --- 5. 翻译JSON文件 (新增) ---
        trans_json_frame = ttk.Frame(functions_frame)
        trans_json_frame.pack(fill=tk.X, pady=5)
        ttk.Label(trans_json_frame, text="5. 翻译JSON文件", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(trans_json_frame, text="使用DeepSeek API翻译JSON文件").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(trans_json_frame, text="执行", command=self.translate_json_file).pack(side=tk.RIGHT, padx=5)
        ttk.Button(trans_json_frame, text="配置", command=self.open_translate_config).pack(side=tk.RIGHT, padx=5)

        # --- 6. 释放JSON文件 ---
        mtool_release_frame = ttk.Frame(functions_frame)
        mtool_release_frame.pack(fill=tk.X, pady=5)
        ttk.Label(mtool_release_frame, text="6. 释放JSON文件", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(mtool_release_frame, text="将已翻译JSON释放到StringScripts").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(mtool_release_frame, text="执行", command=self.release_mtool_files).pack(side=tk.RIGHT, padx=5)

        # --- 7. 导入文本 ---
        import_frame = ttk.Frame(functions_frame)
        import_frame.pack(fill=tk.X, pady=5)
        ttk.Label(import_frame, text="7. 导入文本", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(import_frame, text="将StringScripts文本导入到游戏中").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(import_frame, text="执行", command=self.import_text).pack(side=tk.RIGHT, padx=5)
        import_encoding_combobox = ttk.Combobox(import_frame, textvariable=self.import_encoding, state="readonly", width=20)
        import_encoding_combobox['values'] = [f"{name} - {code}" for name, code in encoding_options]
        import_encoding_combobox.current(1)  # 默认选择中文
        import_encoding_combobox.pack(side=tk.RIGHT, padx=5)
        ttk.Label(import_frame, text="编码:").pack(side=tk.RIGHT, padx=5)

        # 日志区域
        log_frame = ttk.LabelFrame(main_frame, text="操作日志", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, width=80, height=15)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.log_text.tag_configure("normal", foreground="black")
        self.log_text.tag_configure("success", foreground="blue")
        self.log_text.tag_configure("error", foreground="red")
        self.log_text.config(state=tk.DISABLED)

        # 状态栏
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=5)
        self.status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor=tk.W)
        status_label.pack(fill=tk.X)

    # --- 日志和状态更新方法 (保持不变) ---
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

    # --- 线程通信方法 (保持不变) ---
    def process_messages(self):
        try:
            while True:
                message = self.message_queue.get_nowait()
                message_type, content = message
                if message_type == "log":
                    level, text = content
                    self.log(text, level)
                elif message_type == "status":
                    self.status_var.set(content)
                elif message_type == "success":
                    self.show_success(content)
                elif message_type == "error":
                    self.show_error(content)
                elif message_type == "done":
                    self.is_processing = False
                self.message_queue.task_done()
        except queue.Empty:
            pass
        self.root.after(100, self.process_messages)

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

    # --- 原始功能方法 (保持不变, 仅调整内部调用线程日志方法) ---
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
            converted_files = 0
            skipped_conversions = 0
            failed_conversions = 0
            for item in os.listdir(game_path):
                file_path = os.path.join(game_path, item)
                if os.path.isfile(file_path) and (file_path.lower().endswith('.txt') or file_path.lower().endswith('.ini')):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as file: file.read()
                        self.thread_log(f"跳过已是UTF-8的文件: {item}")
                        skipped_conversions += 1
                        continue
                    except UnicodeDecodeError: pass
                    encodings = ['Shift_JIS', 'gbk', 'cp932', 'latin1']
                    converted = False
                    for encoding in encodings:
                        try:
                            with open(file_path, 'r', encoding=encoding) as file: content = file.read()
                            with open(file_path, 'w', encoding='utf-8') as file: file.write(content)
                            self.thread_log(f"成功转换文件: {item} ({encoding} -> UTF-8)")
                            converted = True
                            converted_files += 1
                            break
                        except Exception: continue
                    if not converted:
                        self.thread_log(f"转换文件失败: {item}", "error")
                        failed_conversions += 1
            self.thread_log(f"编码转换完成: 转换 {converted_files} 个文件，跳过 {skipped_conversions} 个已是UTF-8的文件，失败 {failed_conversions} 个文件")

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

    def create_mtool_files(self):
        if not self.check_game_path(): return
        self.run_in_thread(self._create_mtool_files)

    def _create_mtool_files(self):
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

    # --- 新增：生成世界观字典 ---
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
            api_key = self.world_dict_config.get("api_key")
            model_name = self.world_dict_config.get("model")
            prompt_template = self.world_dict_config.get("prompt")

            if not api_key:
                self.thread_show_error("请在世界观字典配置中设置Gemini API Key")
                return

            self.thread_log(f"正在调用Gemini API (模型: {model_name})...")
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name,
                # 降低安全限制，避免误拦截
                safety_settings={
                    f"HARM_CATEGORY_{cat}": "BLOCK_NONE"
                    for cat in ["HARASSMENT", "HATE_SPEECH", "SEXUALLY_EXPLICIT", "DANGEROUS_CONTENT"]
                }
            )

            # 读取临时文件内容并替换到Prompt中
            with open(temp_text_path, 'r', encoding='utf-8') as f:
                game_text_content = f.read()

            # 检查文本大小，如果太大可能需要分块或用其他方法
            # 这里暂时直接嵌入，Gemini Pro 2.5 支持很长上下文
            final_prompt = prompt_template.format(game_text=game_text_content)

            # 注意：Gemini API 可能对单次请求的大小有限制，即使模型支持长上下文
            # 这里为了简化，假设文本大小在API允许范围内
            try:
                response = model.generate_content(final_prompt)
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

    # --- 新增：翻译JSON文件 ---
    def translate_json_file(self):
        if not self.check_game_path(): return
        self.run_in_thread(self._translate_json)

    def _translate_json(self):
        self.thread_update_status("正在翻译JSON文件...")
        game_path = self.game_path.get()
        game_folder_name = os.path.basename(game_path)
        work_game_dir = os.path.join(self.works_dir, game_folder_name)
        untranslated_dir = os.path.join(work_game_dir, "untranslated")
        translated_dir = os.path.join(work_game_dir, "translated")
        untranslated_json_path = os.path.join(untranslated_dir, "translation.json")
        translated_json_path = os.path.join(translated_dir, "translation_translated.json") # 输出文件名
        dict_csv_path = os.path.join(work_game_dir, "world_dictionary.csv")

        # 1. 加载未翻译JSON
        if not os.path.exists(untranslated_json_path):
            self.thread_show_error(f"未找到未翻译的JSON文件: {untranslated_json_path}")
            return
        self.thread_log("加载未翻译的JSON文件...")
        with open(untranslated_json_path, 'r', encoding='utf-8') as f:
            untranslated_data = json.load(f)
        translated_data = untranslated_data.copy() # 创建副本用于存储翻译结果
        original_items = list(untranslated_data.items()) # 转为列表以方便分批

        # 2. 加载世界观字典
        world_dictionary = []
        if os.path.exists(dict_csv_path):
            self.thread_log("加载世界观字典...")
            try:
                with open(dict_csv_path, 'r', newline='', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    world_dictionary = [row for row in reader]
                self.thread_log(f"加载了 {len(world_dictionary)} 条字典条目")
            except Exception as e:
                self.thread_log(f"加载世界观字典失败: {str(e)}", "error")
        else:
            self.thread_log("未找到世界观字典文件，将不使用字典进行翻译")

        # 3. 获取翻译配置
        api_url = self.translate_config.get("api_url")
        api_key = self.translate_config.get("api_key")
        model_name = self.translate_config.get("model")
        batch_size = self.translate_config.get("batch_size", 10)
        context_lines = self.translate_config.get("context_lines", 10)
        concurrency = self.translate_config.get("concurrency", 16)
        prompt_template = self.translate_config.get("prompt_template")
        source_language = "日语" # 假设源语言总是日语
        target_language = "简体中文" # 假设目标总是简体中文

        if not api_key:
            self.thread_show_error("请在翻译JSON配置中设置API Key")
            return
        if not api_url:
            self.thread_show_error("请在翻译JSON配置中设置API URL")
            return

        # 4. 初始化OpenAI客户端
        try:
            client = OpenAI(base_url=api_url, api_key=api_key)
        except Exception as client_err:
            self.thread_show_error(f"初始化API客户端失败: {str(client_err)}")
            return

        # 5. 分批和并发处理
        total_items = len(original_items)
        processed_count = 0
        error_count = 0
        results_lock = threading.Lock()

        def translate_batch_worker(batch_items, context_items):
            nonlocal processed_count, error_count
            try:
                # a. 提取当前批次的原文
                batch_texts_dict = {str(i+1): item[0] for i, item in enumerate(batch_items)} # 从1开始编号
                batch_text_numbered = "\n".join([f"{i+1}.{item[0]}" for i, item in enumerate(batch_items)])

                # b. 提取上下文原文
                context_texts = [item[0] for item in context_items]
                context_section = ""
                if context_texts:
                    context_section = "### 上文内容\n<context>\n" + "\n".join(context_texts) + "\n</context>\n"

                # c. 筛选相关字典条目
                relevant_dict_entries = []
                current_batch_full_text = " ".join(batch_texts_dict.values()) # 合并批次文本用于检查
                if world_dictionary:
                    for entry in world_dictionary:
                        if entry.get('原文') and entry['原文'] in current_batch_full_text:
                            relevant_dict_entries.append(f"{entry['原文']}|{entry.get('译文', '')}|{entry.get('类别', '')} - {entry.get('描述', '')}")

                glossary_section = ""
                if relevant_dict_entries:
                    glossary_section = "### 术语表\n原文|译文|类别 - 描述\n" + "\n".join(relevant_dict_entries) + "\n"

                # d. 构建最终Prompt
                final_prompt = prompt_template.format(
                    source_language=source_language,
                    target_language=target_language,
                    glossary_section=glossary_section,
                    context_section=context_section,
                    batch_text=batch_text_numbered,
                    target_language_placeholder=target_language # For the final textarea example
                )

                # e. 调用API
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": final_prompt}],
                    temperature=0.7, # 可以考虑加入配置
                    max_tokens=4000 # 可以考虑加入配置
                )
                response_content = response.choices[0].message.content

                # f. 提取翻译结果 (简化版，只取textarea内容)
                match = re.search(r'<textarea>(.*?)</textarea>', response_content, re.DOTALL)
                if match:
                    translated_block = match.group(1).strip()
                    translated_lines = translated_block.split('\n')
                    batch_results = {}
                    # 按行号匹配回原文
                    for i, item in enumerate(batch_items):
                        original_key = item[0]
                        prefix = f"{i+1}."
                        found_line = False
                        for tl in translated_lines:
                            if tl.startswith(prefix):
                                batch_results[original_key] = tl[len(prefix):].strip()
                                found_line = True
                                break
                        if not found_line:
                             self.thread_log(f"警告: 未在API响应中找到原文 '{original_key}' (序号 {i+1}) 的翻译", "error")
                             batch_results[original_key] = original_key # 使用原文作为回退
                else:
                    self.thread_log(f"警告: API响应格式错误，未找到<textarea>。批次原文: {list(batch_texts_dict.values())[:2]}...", "error")
                    self.thread_log(f"原始响应: {response_content[:200]}...", "error")
                    # 如果格式错误，整个批次都用原文作为回退
                    batch_results = {item[0]: item[0] for item in batch_items}
                    error_count += len(batch_items) # 标记整个批次为错误

                # g. 更新全局结果 (加锁)
                with results_lock:
                    for original, translated in batch_results.items():
                        translated_data[original] = translated
                    processed_count += len(batch_items)
                    # 更新状态栏进度
                    progress_percent = (processed_count / total_items) * 100
                    self.thread_update_status(f"正在翻译JSON... {processed_count}/{total_items} ({progress_percent:.1f}%)")

            except Exception as batch_err:
                with results_lock:
                    error_count += len(batch_items)
                self.thread_log(f"处理批次时出错: {str(batch_err)}", "error")
                # 记录失败的批次原文（部分）
                failed_keys = [item[0] for item in batch_items]
                self.thread_log(f"失败的批次原文(部分): {failed_keys[:3]}...", "error")


        # 6. 使用线程池执行
        self.thread_log(f"开始使用 {concurrency} 个线程进行翻译...")
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = []
            for i in range(0, total_items, batch_size):
                batch = original_items[i : i + batch_size]
                # 获取上下文（前N行原文的key）
                context_start = max(0, i - context_lines)
                context = original_items[context_start : i]
                futures.append(executor.submit(translate_batch_worker, batch, context))

            # 等待所有任务完成
            for future in concurrent.futures.as_completed(futures):
                # 这里可以添加对 future.exception() 的检查，但在worker内部已经处理了
                pass

        # 7. 保存翻译后的JSON
        self.thread_log("所有翻译任务完成，正在保存结果...")
        try:
            with open(translated_json_path, 'w', encoding='utf-8') as f:
                json.dump(translated_data, f, ensure_ascii=False, indent=4)
            self.thread_update_status("JSON文件翻译完成")
            if error_count == 0:
                self.thread_show_success(f"JSON文件翻译完成，结果已保存: {translated_json_path}")
            else:
                self.thread_show_success(f"JSON文件翻译完成，但有 {error_count} 个条目可能翻译失败（已使用原文填充），结果已保存: {translated_json_path}")
        except Exception as save_err:
            self.thread_show_error(f"保存翻译后的JSON文件失败: {str(save_err)}")


    # --- 释放和导入功能 (保持不变, 仅调整内部调用线程日志方法) ---
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

    def release_mtool_files(self):
        if not self.check_game_path(): return
        self.run_in_thread(self._release_mtool_files)

    def _release_mtool_files(self):
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

    # --- RTP选择方法 (保持不变) ---
    def show_rtp_selection(self):
        rtp_window = tk.Toplevel(self.root)
        rtp_window.title("选择RTP")
        rtp_window.geometry("240x200")
        rtp_window.transient(self.root)
        rtp_window.grab_set()
        rtp_window.resizable(False, False)
        x = self.root.winfo_rootx() + self.root.winfo_width() - 300
        y = self.root.winfo_rooty() + 150
        rtp_window.geometry(f"+{x}+{y}")
        frame = ttk.Frame(rtp_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="选择要安装的RTP文件:").pack(anchor=tk.W, pady=(0, 5))
        ttk.Checkbutton(frame, text="RPG Maker 2000", variable=self.rtp_2000).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(frame, text="RPG Maker 2000 (英文版)", variable=self.rtp_2000en).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(frame, text="RPG Maker 2003", variable=self.rtp_2003).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(frame, text="RPG Maker 2003 (Steam版)", variable=self.rtp_2003steam).pack(anchor=tk.W, pady=2)
        def on_confirm():
            selected_rtps = []
            if self.rtp_2000.get(): selected_rtps.append("2000")
            if self.rtp_2000en.get(): selected_rtps.append("2000en")
            if self.rtp_2003.get(): selected_rtps.append("2003")
            if self.rtp_2003steam.get(): selected_rtps.append("2003steam")
            if not selected_rtps: self.rtp_button_text.set("RTP选择: 无")
            elif len(selected_rtps) == 1: self.rtp_button_text.set(f"RTP选择: {selected_rtps[0]}")
            else: self.rtp_button_text.set(f"RTP选择: {len(selected_rtps)}个")
            rtp_window.destroy()
        ttk.Button(frame, text="确定", command=on_confirm).pack(anchor=tk.CENTER, pady=(10, 0))

    # --- 新增：配置窗口打开方法 ---
    def open_world_dict_config(self):
        WorldDictConfigWindow(self.root, self.world_dict_config)

    def open_translate_config(self):
        TranslateConfigWindow(self.root, self.translate_config)

# --- 新增：世界观字典配置窗口 ---
class WorldDictConfigWindow(tk.Toplevel):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        self.transient(parent)
        self.grab_set()
        self.title("世界观字典配置")
        self.geometry("600x500") # 增加高度

        frame = ttk.Frame(self, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        # API Key
        key_frame = ttk.Frame(frame)
        key_frame.pack(fill=tk.X, pady=5)
        ttk.Label(key_frame, text="Gemini API Key:", width=15).pack(side=tk.LEFT)
        self.api_key_var = tk.StringVar(value=config.get("api_key", ""))
        ttk.Entry(key_frame, textvariable=self.api_key_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Model Name
        model_frame = ttk.Frame(frame)
        model_frame.pack(fill=tk.X, pady=5)
        ttk.Label(model_frame, text="模型名称:", width=15).pack(side=tk.LEFT)
        self.model_var = tk.StringVar(value=config.get("model", "gemini-2.5-pro-latest"))
        # 提供一些常用的Gemini模型选项
        model_combobox = ttk.Combobox(model_frame, textvariable=self.model_var, values=[
            "gemini-2.5-pro-latest",
            "gemini-2.5-flash-latest",
            "gemini-pro", # 旧版Pro，可能不再推荐
            # 添加你可能需要的其他模型
        ], width=48)
        model_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)


        # Prompt
        prompt_frame = ttk.LabelFrame(frame, text="Prompt", padding="5")
        prompt_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.prompt_text = tk.Text(prompt_frame, wrap=tk.WORD, height=15) # 增加高度
        self.prompt_text.insert(tk.END, config.get("prompt", ""))
        prompt_scroll = ttk.Scrollbar(prompt_frame, command=self.prompt_text.yview)
        self.prompt_text.configure(yscrollcommand=prompt_scroll.set)
        prompt_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.prompt_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=10)
        ttk.Button(button_frame, text="保存", command=self.save_config).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="取消", command=self.destroy).pack(side=tk.RIGHT)

    def save_config(self):
        self.config["api_key"] = self.api_key_var.get()
        self.config["model"] = self.model_var.get()
        self.config["prompt"] = self.prompt_text.get("1.0", tk.END).strip()
        messagebox.showinfo("保存成功", "世界观字典配置已更新。")
        self.destroy()

# --- 新增：翻译JSON配置窗口 ---
class TranslateConfigWindow(tk.Toplevel):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        self.transient(parent)
        self.grab_set()
        self.title("翻译JSON文件配置")
        self.geometry("600x400") # 调整大小

        frame = ttk.Frame(self, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        # API URL
        url_frame = ttk.Frame(frame)
        url_frame.pack(fill=tk.X, pady=5)
        ttk.Label(url_frame, text="API URL:", width=15).pack(side=tk.LEFT)
        self.api_url_var = tk.StringVar(value=config.get("api_url", "https://api.deepseek.com/v1"))
        ttk.Entry(url_frame, textvariable=self.api_url_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # API Key
        key_frame = ttk.Frame(frame)
        key_frame.pack(fill=tk.X, pady=5)
        ttk.Label(key_frame, text="API Key:", width=15).pack(side=tk.LEFT)
        self.api_key_var = tk.StringVar(value=config.get("api_key", ""))
        ttk.Entry(key_frame, textvariable=self.api_key_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Model Name
        model_frame = ttk.Frame(frame)
        model_frame.pack(fill=tk.X, pady=5)
        ttk.Label(model_frame, text="模型名称:", width=15).pack(side=tk.LEFT)
        self.model_var = tk.StringVar(value=config.get("model", "deepseek-chat"))
        # 提供一些常用OpenAI兼容模型选项
        model_combobox = ttk.Combobox(model_frame, textvariable=self.model_var, values=[
            "deepseek-chat", "deepseek-coder", # DeepSeek
            "gpt-3.5-turbo", "gpt-4o", "gpt-4o-mini", # OpenAI
            # 添加其他你可能使用的模型
        ], width=48)
        model_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Batch Size
        batch_frame = ttk.Frame(frame)
        batch_frame.pack(fill=tk.X, pady=5)
        ttk.Label(batch_frame, text="批次大小:", width=15).pack(side=tk.LEFT)
        self.batch_var = tk.IntVar(value=config.get("batch_size", 10))
        ttk.Spinbox(batch_frame, from_=1, to=100, textvariable=self.batch_var, width=10).pack(side=tk.LEFT, padx=5)

        # Context Lines
        context_frame = ttk.Frame(frame)
        context_frame.pack(fill=tk.X, pady=5)
        ttk.Label(context_frame, text="上文行数:", width=15).pack(side=tk.LEFT)
        self.context_var = tk.IntVar(value=config.get("context_lines", 10))
        ttk.Spinbox(context_frame, from_=0, to=50, textvariable=self.context_var, width=10).pack(side=tk.LEFT, padx=5)

        # Concurrency
        concur_frame = ttk.Frame(frame)
        concur_frame.pack(fill=tk.X, pady=5)
        ttk.Label(concur_frame, text="并发数:", width=15).pack(side=tk.LEFT)
        self.concur_var = tk.IntVar(value=config.get("concurrency", 16))
        ttk.Spinbox(concur_frame, from_=1, to=64, textvariable=self.concur_var, width=10).pack(side=tk.LEFT, padx=5)

        # Prompt Template (显示部分，允许滚动)
        prompt_frame = ttk.LabelFrame(frame, text="Prompt 模板 (只读)", padding="5")
        prompt_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        prompt_display = scrolledtext.ScrolledText(prompt_frame, wrap=tk.WORD, height=5)
        prompt_display.insert(tk.END, config.get("prompt_template", ""))
        prompt_display.config(state=tk.DISABLED) # 设置为只读
        prompt_display.pack(fill=tk.BOTH, expand=True)

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=10)
        ttk.Button(button_frame, text="保存", command=self.save_config).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="取消", command=self.destroy).pack(side=tk.RIGHT)

    def save_config(self):
        self.config["api_url"] = self.api_url_var.get()
        self.config["api_key"] = self.api_key_var.get()
        self.config["model"] = self.model_var.get()
        self.config["batch_size"] = self.batch_var.get()
        self.config["context_lines"] = self.context_var.get()
        self.config["concurrency"] = self.concur_var.get()
        # Prompt 模板通常不在此处修改，但如果需要也可以添加
        messagebox.showinfo("保存成功", "翻译JSON文件配置已更新。")
        self.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    # 添加样式，可选
    style = ttk.Style(root)
    try:
        # 尝试使用 'clam' 主题，如果可用的话
        style.theme_use('clam')
    except tk.TclError:
        # 如果 'clam' 不可用，则使用默认主题
        pass
    app = RPGTranslationAssistant(root)
    root.mainloop()