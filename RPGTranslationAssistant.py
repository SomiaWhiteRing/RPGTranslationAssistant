import os
import sys
import shutil
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import re
from pathlib import Path
import datetime

class RPGTranslationAssistant:
    def __init__(self, root):
        self.root = root
        self.root.title("RPG Maker 翻译助手")
        self.root.geometry("800x650")  # 增加高度以容纳日志区域
        self.root.resizable(True, True)
        
        # 设置程序路径
        self.program_dir = os.path.dirname(os.path.abspath(__file__))
        self.rpgrewriter_path = os.path.join(self.program_dir, "RPGRewriter", "RPGRewriter.exe")
        self.easyrpg_path = os.path.join(self.program_dir, "EasyRPG")
        self.rtpcollection_path = os.path.join(self.program_dir, "RTPCollection")
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
        
        self.create_ui()
        self.log("程序已启动，请选择游戏目录")
    
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
        
        # 初始化
        init_frame = ttk.Frame(functions_frame)
        init_frame.pack(fill=tk.X, pady=5)
        ttk.Label(init_frame, text="0. 初始化", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(init_frame, text="复制EasyRPG和RTP文件到游戏目录，并转换文本编码").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 执行按钮放在最右侧
        ttk.Button(init_frame, text="执行", command=self.initialize_game).pack(side=tk.RIGHT, padx=5)
        
        # RTP选择按钮
        self.rtp_button_text = tk.StringVar(value="RTP选择: 2000")
        ttk.Button(init_frame, textvariable=self.rtp_button_text, command=self.show_rtp_selection).pack(side=tk.RIGHT, padx=5)
        
        # 重写文件名
        rename_frame = ttk.Frame(functions_frame)
        rename_frame.pack(fill=tk.X, pady=5)
        ttk.Label(rename_frame, text="1. 重写文件名", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(rename_frame, text="将非ASCII文件名转换为Unicode编码格式").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 执行按钮放在最右侧
        ttk.Button(rename_frame, text="执行", command=self.rename_files).pack(side=tk.RIGHT, padx=5)
        
        # 添加输出日志复选框
        self.write_log_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(rename_frame, text="输出日志", variable=self.write_log_var).pack(side=tk.RIGHT, padx=5)
        
        # 导出文本
        export_frame = ttk.Frame(functions_frame)
        export_frame.pack(fill=tk.X, pady=5)
        ttk.Label(export_frame, text="2. 导出文本", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(export_frame, text="将游戏文本导出到StringScripts文件夹").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        encoding_options = [
            ("日语 (Shift-JIS)", "932"),
            ("中文简体 (GBK)", "936"),
            ("中文繁体 (Big5)", "950"),
            ("韩语 (EUC-KR)", "949"),
            ("泰语", "874"),
            ("拉丁语系 (西欧)", "1252"),
            ("东欧", "1250"),
            ("西里尔字母", "1251")
        ]
        
        # 移动按钮到最右侧
        ttk.Button(export_frame, text="执行", command=self.export_text).pack(side=tk.RIGHT, padx=5)
        
        export_encoding_combobox = ttk.Combobox(export_frame, textvariable=self.export_encoding, state="readonly", width=20)
        export_encoding_combobox['values'] = [f"{name} - {code}" for name, code in encoding_options]
        export_encoding_combobox.current(0)
        export_encoding_combobox.pack(side=tk.RIGHT, padx=5)
        ttk.Label(export_frame, text="编码:").pack(side=tk.RIGHT, padx=5)
        
        # 制作JSON文件
        mtool_create_frame = ttk.Frame(functions_frame)
        mtool_create_frame.pack(fill=tk.X, pady=5)
        ttk.Label(mtool_create_frame, text="3. 制作JSON文件", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(mtool_create_frame, text="将StringScripts文本压缩为JSON").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 移动按钮到最右侧
        ttk.Button(mtool_create_frame, text="执行", command=self.create_mtool_files).pack(side=tk.RIGHT, padx=5)
        
        # 释放JSON文件
        mtool_release_frame = ttk.Frame(functions_frame)
        mtool_release_frame.pack(fill=tk.X, pady=5)
        ttk.Label(mtool_release_frame, text="4. 释放JSON文件", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(mtool_release_frame, text="将已翻译JSON释放到StringScripts").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 移动按钮到最右侧
        ttk.Button(mtool_release_frame, text="执行", command=self.release_mtool_files).pack(side=tk.RIGHT, padx=5)
        
        # 导入文本
        import_frame = ttk.Frame(functions_frame)
        import_frame.pack(fill=tk.X, pady=5)
        ttk.Label(import_frame, text="5. 导入文本", width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(import_frame, text="将StringScripts文本导入到游戏中").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 移动按钮到最右侧
        ttk.Button(import_frame, text="执行", command=self.import_text).pack(side=tk.RIGHT, padx=5)
        
        import_encoding_combobox = ttk.Combobox(import_frame, textvariable=self.import_encoding, state="readonly", width=20)
        import_encoding_combobox['values'] = [f"{name} - {code}" for name, code in encoding_options]
        import_encoding_combobox.current(1)  # 默认选择中文
        import_encoding_combobox.pack(side=tk.RIGHT, padx=5)
        ttk.Label(import_frame, text="编码:").pack(side=tk.RIGHT, padx=5)
        
        # 日志区域
        log_frame = ttk.LabelFrame(main_frame, text="操作日志", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 创建文本框和滚动条
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, width=80, height=15)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 配置文本标签
        self.log_text.tag_configure("normal", foreground="black")
        self.log_text.tag_configure("success", foreground="blue")
        self.log_text.tag_configure("error", foreground="red")
        
        # 禁止编辑
        self.log_text.config(state=tk.DISABLED)
        
        # 状态栏
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=5)
        self.status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor=tk.W)
        status_label.pack(fill=tk.X)
        
    def log(self, message, level="normal"):
        """向日志区域添加消息"""
        self.log_text.config(state=tk.NORMAL)
        timestamp = datetime.datetime.now().strftime("[%H:%M:%S] ")
        self.log_text.insert(tk.END, timestamp + message + "\n", level)
        self.log_text.see(tk.END)  # 自动滚动到最新消息
        self.log_text.config(state=tk.DISABLED)
        self.root.update()
        
    def show_error(self, message):
        """显示错误消息"""
        self.log(message, "error")
        
    def show_success(self, message):
        """显示成功消息"""
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
        
        # 检查是否有RPG_RT.lmt文件
        lmt_path = os.path.join(game_path, "RPG_RT.lmt")
        if not os.path.exists(lmt_path):
            self.show_error("选择的目录不是有效的RPG Maker游戏目录（未找到RPG_RT.lmt）")
            return False
            
        return True
        
    def initialize_game(self):
        if not self.check_game_path():
            return
            
        game_path = self.game_path.get()
        self.update_status("正在初始化...")
        
        try:
            # 复制EasyRPG到游戏目录
            copied_files = 0
            skipped_files = 0
            
            self.log("正在复制EasyRPG文件...")
            for item in os.listdir(self.easyrpg_path):
                src = os.path.join(self.easyrpg_path, item)
                dst = os.path.join(game_path, item)
                if os.path.isfile(src):
                    if not os.path.exists(dst):
                        shutil.copy2(src, dst)
                        copied_files += 1
                    else:
                        skipped_files += 1
            
            self.log(f"EasyRPG文件复制完成: 复制 {copied_files} 个文件，跳过 {skipped_files} 个已存在文件")
                        
            # 解压选择的RTP文件到游戏目录
            self.log("正在处理RTP文件...")
            
            import zipfile
            import tempfile
            
            # 检查至少选择了一个RTP
            if not (self.rtp_2000.get() or self.rtp_2000en.get() or self.rtp_2003.get() or self.rtp_2003steam.get()):
                self.log("警告: 未选择任何RTP文件", "error")
            
            # 定义要处理的RTP文件
            rtp_files = []
            if self.rtp_2000.get():
                rtp_files.append("2000.zip")
            if self.rtp_2000en.get():
                rtp_files.append("2000en.zip")
            if self.rtp_2003.get():
                rtp_files.append("2003.zip")
            if self.rtp_2003steam.get():
                rtp_files.append("2003steam.zip")
            
            # 解压选择的RTP文件
            for rtp_file in rtp_files:
                rtp_path = os.path.join(self.rtpcollection_path, rtp_file)
                if os.path.exists(rtp_path):
                    self.log(f"正在解压 {rtp_file}...")
                    
                    rtp_copied = 0
                    rtp_skipped = 0
                    
                    try:
                        # 创建临时目录进行解压
                        with tempfile.TemporaryDirectory() as temp_dir:
                            self.log(f"创建临时目录: {temp_dir}")
                            
                            # 解压到临时目录
                            with zipfile.ZipFile(rtp_path, 'r') as zip_ref:
                                zip_ref.extractall(temp_dir)
                                
                            # 从临时目录复制到游戏目录
                            self.log(f"从临时目录复制文件到游戏目录...")
                            
                            # 遍历临时目录中的所有文件
                            for root, dirs, files in os.walk(temp_dir):
                                # 计算相对路径
                                rel_path = os.path.relpath(root, temp_dir)
                                if rel_path == '.':
                                    rel_path = ''
                                
                                # 确保目标目录存在
                                target_dir = os.path.normpath(os.path.join(game_path, rel_path))
                                os.makedirs(target_dir, exist_ok=True)
                                
                                # 复制文件
                                for file in files:
                                    src_file = os.path.join(root, file)
                                    dst_file = os.path.join(target_dir, file)
                                    
                                    # 跳过已存在的文件
                                    if os.path.exists(dst_file):
                                        rtp_skipped += 1
                                        continue
                                    
                                    try:
                                        shutil.copy2(src_file, dst_file)
                                        rtp_copied += 1
                                    except Exception as e:
                                        self.log(f"复制文件失败: {src_file} -> {dst_file}: {str(e)}", "error")
                        
                        self.log(f"{rtp_file} 处理完成: 复制 {rtp_copied} 个文件，跳过 {rtp_skipped} 个已存在文件")
                    except Exception as e:
                        self.log(f"解压 {rtp_file} 时出错: {str(e)}", "error")
                else:
                    self.log(f"找不到RTP文件: {rtp_file}", "error")
            
            # 转换文本文件编码
            self.log("正在转换文本文件编码...")
            converted_files = 0
            skipped_conversions = 0
            failed_conversions = 0
            
            for item in os.listdir(game_path):
                file_path = os.path.join(game_path, item)
                if os.path.isfile(file_path) and (file_path.lower().endswith('.txt') or file_path.lower().endswith('.ini')):
                    # 首先检查文件是否已经是UTF-8编码
                    try:
                        with open(file_path, 'r', encoding='utf-8') as file:
                            content = file.read()
                            # 如果能正常读取为UTF-8，认为文件已经转换过
                            self.log(f"跳过已是UTF-8的文件: {item}")
                            skipped_conversions += 1
                            continue
                    except UnicodeDecodeError:
                        # 不是UTF-8，需要进行转换
                        pass
                        
                    # 尝试不同的编码打开文件
                    encodings = ['Shift_JIS', 'gbk', 'cp932', 'latin1']
                    converted = False
                    
                    for encoding in encodings:
                        try:
                            with open(file_path, 'r', encoding=encoding) as file:
                                content = file.read()
                                
                            # 成功读取，转换为UTF-8
                            with open(file_path, 'w', encoding='utf-8') as file:
                                file.write(content)
                                
                            self.log(f"成功转换文件: {item} ({encoding} -> UTF-8)")
                            converted = True
                            converted_files += 1
                            break
                        except Exception:
                            # 当前编码不匹配，尝试下一个
                            continue
                            
                    if not converted:
                        self.log(f"转换文件失败: {item}", "error")
                        failed_conversions += 1
            
            # 编码转换统计
            self.log(f"编码转换完成: 转换 {converted_files} 个文件，跳过 {skipped_conversions} 个已是UTF-8的文件，失败 {failed_conversions} 个文件")
            
            self.update_status("初始化完成")
            self.show_success(f"游戏初始化完成")
            
        except Exception as e:
            self.update_status("初始化过程中出错")
            self.show_error(f"初始化过程中出错: {str(e)}")
            
    def rename_files(self):
        if not self.check_game_path():
            return
            
        game_path = self.game_path.get()
        self.update_status("正在处理文件名...")
        
        try:
            # 生成文件列表
            lmt_path = os.path.join(game_path, "RPG_RT.lmt")
            filelist_cmd = [self.rpgrewriter_path, lmt_path, "-F", "Y"]
            self.log(f"执行命令: {' '.join(filelist_cmd)}")
            
            # 执行命令并捕获输出
            process = subprocess.run(filelist_cmd, capture_output=True, text=True, check=True)
            if process.stdout:
                self.log("命令输出: " + process.stdout.strip())
            
            # 读取生成的filelist.txt文件
            filelist_path = os.path.join(self.program_dir, "filelist.txt")
            if not os.path.exists(filelist_path):
                raise FileNotFoundError("未能生成filelist.txt文件")
                
            # 读取文件内容
            with open(filelist_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()
            
            # 去除每行末尾的换行符
            lines = [line.rstrip('\r\n') for line in lines]
            
            # 查找所有"___"行
            blank_lines = []
            for i, line in enumerate(lines):
                if line.strip() == "___":
                    blank_lines.append(i)
            
            # 记录转换数量
            converted_count = 0
            
            # 对每个"___"行进行处理
            for line_num in blank_lines:
                if line_num > 0:  # 确保有上一行
                    original_name = lines[line_num - 1]
                    
                    # 检查是否包含非ASCII字符
                    if any(ord(c) > 127 for c in original_name):
                        # 生成Unicode名称
                        unicode_name = ""
                        for c in original_name:
                            if ord(c) > 127:
                                unicode_name += f"u{ord(c):04x}"
                            else:
                                unicode_name += c
                        
                        # 替换"___"行
                        lines[line_num] = unicode_name
                        
                        self.log(f"转换文件名: {original_name} -> {unicode_name}")
                        converted_count += 1
                    else:
                        # 如果是ASCII文件名，直接使用原名替换
                        lines[line_num] = original_name
            
            # 保存修改后的内容
            input_path = os.path.join(self.program_dir, "input.txt")
            with open(input_path, 'w', encoding='utf-8') as file:
                file.write('\n'.join(lines))
            
            self.log(f"已生成input.txt文件，共转换 {converted_count} 个非ASCII文件名")
            
            # 应用重写 - 拆分为两个步骤
            self.log("第1步: 重写文件名 - 正在执行重命名...")
            
            # 使用 subprocess.run 简单调用文件重命名功能
            rename_cmd = [self.rpgrewriter_path, lmt_path, "-V"]  # 只重命名资源文件
            self.log(f"执行命令: {' '.join(rename_cmd)}")
            
            rename_result = subprocess.run(rename_cmd, capture_output=True, text=True)
            if rename_result.stdout:
                self.log("命令输出: " + rename_result.stdout.strip())
            if rename_result.stderr:
                self.log("命令错误: " + rename_result.stderr.strip(), "error")
            
            if rename_result.returncode != 0:
                self.log(f"文件重命名失败，返回代码: {rename_result.returncode}", "error")
                raise Exception(f"文件重命名失败，返回代码: {rename_result.returncode}")
                
            self.log("第2步: 重写文件名 - 正在重写游戏数据...")
            
            # 生成一个不需要Y/N回答的日志文件名
            log_filename = "renames_log.txt" if self.write_log_var.get() else "null"
            
            # 重写数据文件，使用管道方式处理可能的交互式提示
            rewrite_cmd = [self.rpgrewriter_path, lmt_path, "-rewrite", "-all", "-log", log_filename]
            self.log(f"执行命令: {' '.join(rewrite_cmd)}")
            
            # 使用Popen代替run，这样可以处理交互式提示
            process = subprocess.Popen(
                rewrite_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # 向进程发送"Y"以应对可能的"是否保存日志"提示
            stdout, stderr = process.communicate(input="Y\n")
            
            if stdout:
                self.log("命令输出: " + stdout.strip())
            if stderr:
                self.log("命令错误: " + stderr.strip(), "error")
            
            if process.returncode != 0:
                self.log(f"数据重写失败，返回代码: {process.returncode}", "error")
                raise Exception(f"数据重写失败，返回代码: {process.returncode}")
            
            self.update_status("文件名重写完成")
            self.show_success("文件名重写完成")
            
            # 如果生成了日志文件，显示信息
            if self.write_log_var.get():
                log_txt_path = os.path.join(self.program_dir, log_filename)
                if os.path.exists(log_txt_path):
                    with open(log_txt_path, 'r', encoding='utf-8') as file:
                        log_content = file.read()
                    
                    missing_count = log_content.count('\n')
                    self.log(f"有 {missing_count} 个文件名未找到翻译，详见{log_filename}")
                
        except Exception as e:
            self.update_status("文件名重写过程中出错")
            self.show_error(f"文件名重写过程中出错: {str(e)}")
            
    def export_text(self):
        if not self.check_game_path():
            return
            
        game_path = self.game_path.get()
        encoding = self.export_encoding.get().split(' - ')[-1]
        self.update_status(f"正在导出文本 (编码: {encoding})...")
        
        try:
            # 设置编码
            lmt_path = os.path.join(game_path, "RPG_RT.lmt")
            export_cmd = [
                self.rpgrewriter_path,
                lmt_path,
                "-export",
                "-readcode", encoding
            ]
            self.log(f"执行命令: {' '.join(export_cmd)}")
            subprocess.run(export_cmd, check=True)
            
            # 检查StringScripts文件夹是否已创建
            string_scripts_path = os.path.join(game_path, "StringScripts")
            if os.path.exists(string_scripts_path):
                # 计算文件数量
                file_count = 0
                for root, dirs, files in os.walk(string_scripts_path):
                    file_count += len(files)
                
                self.update_status("文本导出完成")
                self.show_success(f"文本已导出到StringScripts文件夹，共 {file_count} 个文件")
            else:
                self.update_status("文本导出完成")
                self.show_success("文本已导出到StringScripts文件夹")
            
        except Exception as e:
            self.update_status("文本导出过程中出错")
            self.show_error(f"文本导出过程中出错: {str(e)}")
            
    def process_file(self, file_path):
        result = {}
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                match = re.match(r'#(.+)#', line)
                if match:
                    title = match.group(1)
                    if title == 'EventName':
                        i += 1  # 跳过 EventName 的内容
                    elif title == 'Message' or title == 'Choice':
                        message = ''
                        i += 1
                        while i < len(lines) and not lines[i].strip() == '##':
                            message += lines[i]
                            i += 1
                        if message:  # 保留原始格式
                            # 移除尾部换行符，但保留中间的换行符
                            message_stripped = message.rstrip('\n')
                            result[message_stripped] = message_stripped
                    else:
                        i += 1
                        if i < len(lines):
                            content = lines[i].strip()
                            if content:  # 只有当内容不为空时才添加
                                result[content] = content
                i += 1
        return result
            
    def create_mtool_files(self):
        if not self.check_game_path():
            return
            
        game_path = self.game_path.get()
        string_scripts_path = os.path.join(game_path, "StringScripts")
        
        if not os.path.exists(string_scripts_path):
            self.show_error("未找到StringScripts文件夹，请先导出文本")
            return
            
        self.update_status("正在创建JSON文件...")
        
        try:
            # 获取游戏文件夹名称
            game_folder_name = os.path.basename(game_path)
            
            # 创建Works子目录
            work_game_dir = os.path.join(self.works_dir, game_folder_name)
            untranslated_dir = os.path.join(work_game_dir, "untranslated")
            translated_dir = os.path.join(work_game_dir, "translated")
            
            if not os.path.exists(work_game_dir):
                os.makedirs(work_game_dir)
                self.log(f"创建目录: {game_folder_name}")
            if not os.path.exists(untranslated_dir):
                os.makedirs(untranslated_dir)
                self.log(f"创建目录: {game_folder_name}/untranslated")
            if not os.path.exists(translated_dir):
                os.makedirs(translated_dir)
                self.log(f"创建目录: {game_folder_name}/translated")
                
            # 处理所有txt文件
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
                        
            self.log(f"已处理 {file_count} 个文件，提取 {string_count} 个字符串")
            
            # 保存未翻译的JSON文件
            json_path = os.path.join(untranslated_dir, "translation.json")
            with open(json_path, 'w', encoding='utf-8') as json_file:
                json.dump(all_results, json_file, ensure_ascii=False, indent=4)
                
            self.update_status("JSON文件创建完成")
            self.show_success(f"JSON文件已创建在 {untranslated_dir}，共 {string_count} 个字符串")
            
        except Exception as e:
            self.update_status("创建JSON文件过程中出错")
            self.show_error(f"创建JSON文件过程中出错: {str(e)}")
            
    def load_translations(self, json_path):
        with open(json_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    
    def process_translation_file(self, file_path, translations):
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
    
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
                    start_i = i
                    while i < len(lines) and not lines[i].strip() == '##':
                        message += lines[i]
                        i += 1
                    
                    # 尝试多种可能的消息格式来匹配翻译
                    found_translation = False
                    
                    # 1. 尝试原始消息
                    if message in translations:
                        translated_message = translations[message].replace('\\n', '\n')
                        new_lines.append(translated_message)
                        translated_count += 1
                        found_translation = True
                    else:
                        # 2. 尝试移除尾部换行符的消息
                        message_stripped = message.rstrip('\n')
                        if message_stripped in translations:
                            translated_message = translations[message_stripped].replace('\\n', '\n')
                            # 保持与原始消息相同的格式（是否有尾部换行符）
                            if message.endswith('\n') and not translated_message.endswith('\n'):
                                translated_message += '\n'
                            new_lines.append(translated_message)
                            translated_count += 1
                            found_translation = True
                    
                    # 如果没有找到翻译，使用原始消息
                    if not found_translation:
                        new_lines.append(message)
                    
                    new_lines.append(lines[i])  # 添加 '##' 行
                elif title != 'EventName':
                    content = lines[i].strip()
                    if content in translations:
                        translated_content = translations[content].replace('\\n', '\n')
                        new_lines.append(translated_content + '\n')
                        translated_count += 1
                    else:
                        new_lines.append(lines[i])
            else:
                new_lines.append(line)
            i += 1
    
        with open(file_path, 'w', encoding='utf-8') as file:
            file.writelines(new_lines)
            
        return translated_count
            
    def release_mtool_files(self):
        if not self.check_game_path():
            return
            
        game_path = self.game_path.get()
        string_scripts_path = os.path.join(game_path, "StringScripts")
        
        if not os.path.exists(string_scripts_path):
            self.show_error("未找到StringScripts文件夹，请先导出文本")
            return
            
        # 获取游戏文件夹名称
        game_folder_name = os.path.basename(game_path)
        
        # 获取translated文件夹路径
        translated_dir = os.path.join(self.works_dir, game_folder_name, "translated")
        
        if not os.path.exists(translated_dir):
            self.show_error(f"未找到已翻译的文件夹: {translated_dir}")
            return
            
        # 查找JSON文件
        json_files = [f for f in os.listdir(translated_dir) if f.endswith('.json')]
        
        if not json_files:
            self.show_error(f"在 {translated_dir} 中未找到JSON文件")
            return
            
        # 如果只有一个JSON文件，直接使用；否则让用户选择
        json_path = None
        if len(json_files) == 1:
            json_path = os.path.join(translated_dir, json_files[0])
            self.log(f"使用翻译文件: {json_files[0]}")
        else:
            # 创建选择对话框
            selection = tk.StringVar()
            
            dialog = tk.Toplevel(self.root)
            dialog.title("选择翻译文件")
            dialog.geometry("400x300")
            dialog.transient(self.root)
            dialog.grab_set()
            
            ttk.Label(dialog, text="请选择要导入的翻译文件:").pack(pady=10)
            
            listbox = tk.Listbox(dialog, width=50, height=10)
            listbox.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
            
            for file in json_files:
                listbox.insert(tk.END, file)
                
            def on_select():
                if listbox.curselection():
                    selection.set(json_files[listbox.curselection()[0]])
                    dialog.destroy()
                    
            ttk.Button(dialog, text="选择", command=on_select).pack(pady=10)
            
            # 等待用户选择
            self.root.wait_window(dialog)
            
            if selection.get():
                json_path = os.path.join(translated_dir, selection.get())
                self.log(f"使用翻译文件: {selection.get()}")
            else:
                self.log("取消选择翻译文件")
                return
        
        self.update_status("正在释放JSON文件...")
        
        try:
            # 加载翻译
            translations = self.load_translations(json_path)
            self.log(f"已加载 {len(translations)} 个翻译条目")
            
            # 应用到所有文本文件
            file_count = 0
            total_translated = 0
            
            for root, dirs, files in os.walk(string_scripts_path):
                for file in files:
                    if file.endswith('.txt'):
                        file_path = os.path.join(root, file)
                        translated = self.process_translation_file(file_path, translations)
                        total_translated += translated
                        file_count += 1
                        
            self.update_status("JSON文件释放完成")
            self.show_success(f"已将翻译应用到StringScripts文件夹，处理了 {file_count} 个文件，应用了 {total_translated} 个翻译")
            
        except Exception as e:
            self.update_status("释放JSON文件过程中出错")
            self.show_error(f"释放JSON文件过程中出错: {str(e)}")
            
    def import_text(self):
        if not self.check_game_path():
            return
            
        game_path = self.game_path.get()
        encoding = self.import_encoding.get().split(' - ')[-1]
        self.update_status(f"正在导入文本 (编码: {encoding})...")
        
        try:
            # 设置编码
            lmt_path = os.path.join(game_path, "RPG_RT.lmt")
            import_cmd = [
                self.rpgrewriter_path,
                lmt_path,
                "-import",
                "-writecode", encoding
            ]
            self.log(f"执行命令: {' '.join(import_cmd)}")
            subprocess.run(import_cmd, check=True)
            
            self.update_status("文本导入完成")
            self.show_success("文本已从StringScripts文件夹导入到游戏中")
            
        except Exception as e:
            self.update_status("文本导入过程中出错")
            self.show_error(f"文本导入过程中出错: {str(e)}")
            
    def show_rtp_selection(self):
        """显示RTP选择对话框"""
        rtp_window = tk.Toplevel(self.root)
        rtp_window.title("选择RTP")
        rtp_window.geometry("240x200")
        rtp_window.transient(self.root)
        rtp_window.grab_set()
        rtp_window.resizable(False, False)
        
        # 设置窗口位置在按钮下方
        x = self.root.winfo_rootx() + self.root.winfo_width() - 300
        y = self.root.winfo_rooty() + 150
        rtp_window.geometry(f"+{x}+{y}")
        
        frame = ttk.Frame(rtp_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="选择要安装的RTP文件:").pack(anchor=tk.W, pady=(0, 5))
        
        # 添加复选框
        ttk.Checkbutton(frame, text="RPG Maker 2000", variable=self.rtp_2000).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(frame, text="RPG Maker 2000 (英文版)", variable=self.rtp_2000en).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(frame, text="RPG Maker 2003", variable=self.rtp_2003).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(frame, text="RPG Maker 2003 (Steam版)", variable=self.rtp_2003steam).pack(anchor=tk.W, pady=2)
        
        def on_confirm():
            # 更新按钮文本以反映选择
            selected_rtps = []
            if self.rtp_2000.get():
                selected_rtps.append("2000")
            if self.rtp_2000en.get():
                selected_rtps.append("2000en")
            if self.rtp_2003.get():
                selected_rtps.append("2003")
            if self.rtp_2003steam.get():
                selected_rtps.append("2003steam")
                
            if not selected_rtps:
                self.rtp_button_text.set("RTP选择: 无")
            elif len(selected_rtps) == 1:
                self.rtp_button_text.set(f"RTP选择: {selected_rtps[0]}")
            else:
                self.rtp_button_text.set(f"RTP选择: {len(selected_rtps)}个")
                
            rtp_window.destroy()
            
        ttk.Button(frame, text="确定", command=on_confirm).pack(anchor=tk.CENTER, pady=(10, 0))

if __name__ == "__main__":
    root = tk.Tk()
    app = RPGTranslationAssistant(root)
    root.mainloop() 