# ui/config_dialogs.py
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, font
import threading
import json # For advanced settings JSON validation
import logging

# 导入 API 客户端模块用于连接测试
from core.api_clients import gemini # Only Gemini needed now
# 导入默认配置以获取默认 Prompt 值和模型名
from core.config import DEFAULT_WORLD_DICT_CONFIG, DEFAULT_TRANSLATE_CONFIG

log = logging.getLogger(__name__)

# --- Unified Gemini Configuration Window ---
class GeminiConfigWindow(tk.Toplevel):
    """统一配置 Gemini API (字典生成与翻译)。"""

    def __init__(self, parent, app_controller, world_dict_config, translate_config):
        """
        初始化 Gemini 配置窗口。

        Args:
            parent (tk.Widget): 父窗口。
            app_controller (RPGTranslatorApp): 应用控制器实例。
            world_dict_config (dict): 当前的世界观字典配置字典。
            translate_config (dict): 当前的翻译配置字典。
        """
        super().__init__(parent)
        # 需要 app controller 来调用 save_config
        # from app import RPGTranslatorApp # 避免循环导入，假设 parent 是 App 或能访问 App
        # self.app = parent # 或者通过参数传入 app_controller
        if hasattr(parent, 'app_controller') and parent.app_controller: # 检查父级是否有 app_controller 属性
             self.app = parent.app_controller
        elif app_controller: # 或者直接使用传入的 app_controller
             self.app = app_controller
        else:
             log.error("无法获取 App 控制器实例，保存功能将不可用。")
             self.app = None # 确保 self.app 存在

        self.world_dict_config = world_dict_config
        self.translate_config = translate_config

        # --- 状态标志 ---
        self.initializing = True
        self.connection_tested_ok = False

        # --- 窗口设置 ---
        self.title("Gemini API 配置 (字典生成与翻译)")
        self.geometry("850x700")
        self.transient(parent)
        self.grab_set()

        # --- 主框架 ---
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(1, weight=1)

        # --- 控件变量 ---
        self.api_key_var = tk.StringVar(value=self.world_dict_config.get("api_key", "") or self.translate_config.get("api_key", ""))
        self.show_key_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="请先测试连接 (翻译模型)")
        self.dict_model_var = tk.StringVar(value=self.world_dict_config.get("model", DEFAULT_WORLD_DICT_CONFIG["model"]))
        self.trans_model_var = tk.StringVar(value=self.translate_config.get("model", DEFAULT_TRANSLATE_CONFIG["model"]))
        # 使用 get 获取值，若不存在则用默认值，并确保是 int
        self.chunk_tokens_var = tk.IntVar(value=int(self.translate_config.get("chunk_max_tokens", DEFAULT_TRANSLATE_CONFIG["chunk_max_tokens"])))
        self.concur_var = tk.IntVar(value=int(self.translate_config.get("concurrency", DEFAULT_TRANSLATE_CONFIG["concurrency"])))
        self.retries_var = tk.IntVar(value=int(self.translate_config.get("max_retries", DEFAULT_TRANSLATE_CONFIG["max_retries"])))
        self.source_lang_var = tk.StringVar(value=self.translate_config.get("source_language", DEFAULT_TRANSLATE_CONFIG["source_language"]))
        self.target_lang_var = tk.StringVar(value=self.translate_config.get("target_language", DEFAULT_TRANSLATE_CONFIG["target_language"]))
        self.gen_config_var = tk.StringVar(value=json.dumps(self.translate_config.get("generation_config", DEFAULT_TRANSLATE_CONFIG["generation_config"]), indent=2, ensure_ascii=False))
        self.safety_var = tk.StringVar(value=json.dumps(self.translate_config.get("safety_settings", DEFAULT_TRANSLATE_CONFIG["safety_settings"]), indent=2, ensure_ascii=False))

        # --- 创建通用控件 (API Key) ---
        row_idx = 0
        ttk.Label(main_frame, text="Gemini API Key:").grid(row=row_idx, column=0, padx=5, pady=5, sticky="w")
        key_frame = ttk.Frame(main_frame)
        key_frame.grid(row=row_idx, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        key_frame.columnconfigure(0, weight=1)
        self.api_key_entry = ttk.Entry(key_frame, textvariable=self.api_key_var, width=60, show="*")
        self.api_key_entry.grid(row=0, column=0, sticky="ew")
        key_toggle_button = ttk.Checkbutton(key_frame, text="显示", variable=self.show_key_var, command=self._toggle_key_visibility)
        key_toggle_button.grid(row=0, column=1, padx=(5, 0))
        row_idx += 1

        # --- 创建选项卡 Notebook ---
        notebook = ttk.Notebook(main_frame)
        notebook.grid(row=row_idx, column=0, columnspan=3, padx=5, pady=10, sticky="nsew")
        main_frame.rowconfigure(row_idx, weight=1)
        row_idx += 1

        # --- 选项卡 1: 字典生成 ---
        dict_tab = ttk.Frame(notebook, padding="10")
        notebook.add(dict_tab, text="字典生成设置")
        dict_tab.columnconfigure(1, weight=1)

        d_row = 0
        ttk.Label(dict_tab, text="字典生成模型:").grid(row=d_row, column=0, padx=5, pady=5, sticky="w")
        dict_model_combobox = ttk.Combobox(dict_tab, textvariable=self.dict_model_var, values=[
            "gemini-1.5-pro-latest", "gemini-1.5-flash-latest", "gemini-pro",
            "gemini-2.5-flash-preview-04-17", "gemini-2.5-pro-exp-03-25", # 添加 2.5 系列
        ], width=48)
        dict_model_combobox.grid(row=d_row, column=1, padx=5, pady=5, sticky="ew")
        d_row += 1

        dict_prompt_area = ttk.Frame(dict_tab)
        dict_prompt_area.grid(row=d_row, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        dict_tab.rowconfigure(d_row, weight=1)
        dict_prompt_area.columnconfigure(0, weight=1); dict_prompt_area.columnconfigure(1, weight=1)
        dict_prompt_area.rowconfigure(0, weight=1)

        char_prompt_frame = ttk.LabelFrame(dict_prompt_area, text="人物提取 Prompt", padding="5")
        char_prompt_frame.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="nsew")
        char_prompt_frame.rowconfigure(0, weight=1); char_prompt_frame.columnconfigure(0, weight=1)
        self.char_prompt_text = scrolledtext.ScrolledText(char_prompt_frame, wrap=tk.WORD, height=10)
        self.char_prompt_text.grid(row=0, column=0, sticky="nsew")
        self.char_prompt_text.insert(tk.END, self.world_dict_config.get("character_prompt_template", DEFAULT_WORLD_DICT_CONFIG["character_prompt_template"]))
        self.char_prompt_text.edit_modified(False)

        entity_prompt_frame = ttk.LabelFrame(dict_prompt_area, text="事物提取 Prompt", padding="5")
        entity_prompt_frame.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="nsew")
        entity_prompt_frame.rowconfigure(0, weight=1); entity_prompt_frame.columnconfigure(0, weight=1)
        self.entity_prompt_text = scrolledtext.ScrolledText(entity_prompt_frame, wrap=tk.WORD, height=10)
        self.entity_prompt_text.grid(row=0, column=0, sticky="nsew")
        self.entity_prompt_text.insert(tk.END, self.world_dict_config.get("entity_prompt_template", DEFAULT_WORLD_DICT_CONFIG["entity_prompt_template"]))
        self.entity_prompt_text.edit_modified(False)

        # --- 选项卡 2: 翻译 ---
        trans_tab = ttk.Frame(notebook, padding="10")
        notebook.add(trans_tab, text="翻译设置")
        trans_tab.columnconfigure(1, weight=1); trans_tab.columnconfigure(3, weight=1)

        t_row = 0
        ttk.Label(trans_tab, text="翻译模型:").grid(row=t_row, column=0, padx=5, pady=5, sticky="w")
        trans_model_combobox = ttk.Combobox(trans_tab, textvariable=self.trans_model_var, values=[
            "gemini-2.5-flash-preview-04-17", "gemini-1.5-flash-latest",
            "gemini-1.5-pro-latest", "gemini-pro",
            "gemini-2.5-pro-exp-03-25", # 添加 2.5 系列
        ], width=48)
        trans_model_combobox.grid(row=t_row, column=1, columnspan=3, padx=5, pady=5, sticky="ew")
        t_row += 1

        lang_frame = ttk.Frame(trans_tab)
        lang_frame.grid(row=t_row, column=0, columnspan=4, padx=0, pady=5, sticky="ew")
        lang_frame.columnconfigure(1, weight=1); lang_frame.columnconfigure(3, weight=1)
        ttk.Label(lang_frame, text="源语言:").grid(row=0, column=0, padx=5, sticky="w")
        source_lang_combo = ttk.Combobox(lang_frame, textvariable=self.source_lang_var, values=["日语", "英语", "简体中文", "繁体中文", "韩语", "俄语", "法语", "德语", "西班牙语", "自动检测"], width=15, state="readonly")
        source_lang_combo.grid(row=0, column=1, padx=5, sticky="ew")
        ttk.Label(lang_frame, text="目标语言:").grid(row=0, column=2, padx=(10, 5), sticky="w")
        target_lang_combo = ttk.Combobox(lang_frame, textvariable=self.target_lang_var, values=["简体中文", "繁体中文", "英语", "日语", "韩语", "俄语", "法语", "德语", "西班牙语"], width=15, state="readonly")
        target_lang_combo.grid(row=0, column=3, padx=5, sticky="ew")
        t_row += 1

        num_frame = ttk.Frame(trans_tab)
        num_frame.grid(row=t_row, column=0, columnspan=4, padx=0, pady=5, sticky="w")
        ttk.Label(num_frame, text="块Token上限:").pack(side=tk.LEFT, padx=(5, 2))
        chunk_entry = ttk.Entry(num_frame, textvariable=self.chunk_tokens_var, width=10)
        chunk_entry.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(num_frame, text="并发数:").pack(side=tk.LEFT, padx=(5, 2))
        concur_spinbox = ttk.Spinbox(num_frame, from_=1, to=256, textvariable=self.concur_var, width=5)
        concur_spinbox.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(num_frame, text="重试次数:").pack(side=tk.LEFT, padx=(5, 2))
        retries_spinbox = ttk.Spinbox(num_frame, from_=0, to=10, textvariable=self.retries_var, width=5)
        retries_spinbox.pack(side=tk.LEFT, padx=(0, 5))
        t_row += 1

        trans_prompt_area = ttk.Frame(trans_tab)
        trans_prompt_area.grid(row=t_row, column=0, columnspan=4, padx=5, pady=5, sticky="nsew")
        trans_tab.rowconfigure(t_row, weight=1)
        trans_prompt_area.columnconfigure(0, weight=1); trans_prompt_area.columnconfigure(1, weight=1)
        trans_prompt_area.rowconfigure(0, weight=1)

        main_prompt_frame = ttk.LabelFrame(trans_prompt_area, text="主翻译 Prompt", padding="5")
        main_prompt_frame.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="nsew")
        main_prompt_frame.rowconfigure(0, weight=1); main_prompt_frame.columnconfigure(0, weight=1)
        self.main_trans_prompt_text = scrolledtext.ScrolledText(main_prompt_frame, wrap=tk.WORD, height=8)
        self.main_trans_prompt_text.grid(row=0, column=0, sticky="nsew")
        self.main_trans_prompt_text.insert(tk.END, self.translate_config.get("prompt_template", DEFAULT_TRANSLATE_CONFIG["prompt_template"]))
        self.main_trans_prompt_text.edit_modified(False)

        corr_prompt_frame = ttk.LabelFrame(trans_prompt_area, text="修正翻译 Prompt", padding="5")
        corr_prompt_frame.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="nsew")
        corr_prompt_frame.rowconfigure(0, weight=1); corr_prompt_frame.columnconfigure(0, weight=1)
        self.corr_trans_prompt_text = scrolledtext.ScrolledText(corr_prompt_frame, wrap=tk.WORD, height=8)
        self.corr_trans_prompt_text.grid(row=0, column=0, sticky="nsew")
        self.corr_trans_prompt_text.insert(tk.END, self.translate_config.get("prompt_template_correction", DEFAULT_TRANSLATE_CONFIG["prompt_template_correction"]))
        self.corr_trans_prompt_text.edit_modified(False)

        # --- 选项卡 3: 高级设置 ---
        adv_tab = ttk.Frame(notebook, padding="10")
        notebook.add(adv_tab, text="高级翻译设置")
        adv_tab.columnconfigure(0, weight=1)
        adv_tab.rowconfigure(0, weight=1); adv_tab.rowconfigure(1, weight=1)

        # 使用等宽字体
        try:
            json_font = font.nametofont("TkFixedFont") # 尝试获取系统默认等宽字体
        except tk.TclError:
            json_font = font.Font(family="Consolas", size=10) # 后备字体

        gen_config_frame = ttk.LabelFrame(adv_tab, text="Generation Config (JSON格式)", padding="5")
        gen_config_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        gen_config_frame.rowconfigure(0, weight=1); gen_config_frame.columnconfigure(0, weight=1)
        self.gen_config_text = scrolledtext.ScrolledText(gen_config_frame, wrap=tk.WORD, height=5, font=json_font)
        self.gen_config_text.grid(row=0, column=0, sticky="nsew")
        self.gen_config_text.insert(tk.END, self.gen_config_var.get())
        self.gen_config_text.edit_modified(False)

        safety_frame = ttk.LabelFrame(adv_tab, text="Safety Settings (JSON格式, 列表)", padding="5")
        safety_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        safety_frame.rowconfigure(0, weight=1); safety_frame.columnconfigure(0, weight=1)
        self.safety_text = scrolledtext.ScrolledText(safety_frame, wrap=tk.WORD, height=5, font=json_font)
        self.safety_text.grid(row=0, column=0, sticky="nsew")
        self.safety_text.insert(tk.END, self.safety_var.get())
        self.safety_text.edit_modified(False)

        # --- 状态标签和按钮 ---
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var, foreground="orange")
        self.status_label.grid(row=row_idx, column=0, columnspan=3, padx=5, pady=(10, 0), sticky="ew")
        row_idx += 1

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row_idx, column=0, columnspan=3, pady=10, sticky="e")
        self.test_button = ttk.Button(button_frame, text="测试连接 (翻译模型)", command=self._test_connection)
        self.test_button.pack(side=tk.LEFT, padx=5)
        self.save_button = ttk.Button(button_frame, text="保存", command=self._save_config, state=tk.DISABLED)
        self.save_button.pack(side=tk.LEFT, padx=5)
        cancel_button = ttk.Button(button_frame, text="取消", command=self.destroy)
        cancel_button.pack(side=tk.LEFT, padx=5)

        # --- 绑定事件 ---
        self.api_key_var.trace_add("write", self._on_config_change)
        self.dict_model_var.trace_add("write", self._on_config_change)
        self.char_prompt_text.bind("<<Modified>>", self._on_prompt_modified)
        self.entity_prompt_text.bind("<<Modified>>", self._on_prompt_modified)
        self.trans_model_var.trace_add("write", self._on_config_change)
        source_lang_combo.bind("<<ComboboxSelected>>", self._on_config_change)
        target_lang_combo.bind("<<ComboboxSelected>>", self._on_config_change)
        chunk_entry.bind("<FocusOut>", self._on_config_change)
        chunk_entry.bind("<KeyRelease>", self._on_config_change)
        concur_spinbox.bind("<FocusOut>", self._on_config_change)
        concur_spinbox.bind("<KeyRelease>", self._on_config_change)
        retries_spinbox.bind("<FocusOut>", self._on_config_change)
        retries_spinbox.bind("<KeyRelease>", self._on_config_change)
        self.main_trans_prompt_text.bind("<<Modified>>", self._on_prompt_modified)
        self.corr_trans_prompt_text.bind("<<Modified>>", self._on_prompt_modified)
        self.gen_config_text.bind("<<Modified>>", self._on_prompt_modified)
        self.safety_text.bind("<<Modified>>", self._on_prompt_modified)

        self.protocol("WM_DELETE_WINDOW", self.destroy)

        # --- 初始化完成 ---
        self.initializing = False
        if self.api_key_var.get():
            self._set_status("配置已加载，请测试连接 (翻译模型)", "orange")
        else:
            self._set_status("请输入 API Key 并测试连接", "red")

    def _toggle_key_visibility(self):
        if self.show_key_var.get(): self.api_key_entry.config(show="")
        else: self.api_key_entry.config(show="*")

    def _on_prompt_modified(self, event=None):
        if not self.initializing and event and event.widget.edit_modified():
            event.widget.edit_modified(False)
            self._on_config_change()

    def _on_config_change(self, *args):
        if self.initializing: return
        self.connection_tested_ok = False
        if hasattr(self, 'save_button') and self.save_button.winfo_exists():
            self.save_button.config(state=tk.DISABLED)
        self._set_status("配置已更改，请重新测试连接 (翻译模型)", "orange")

    def _set_status(self, message, color):
        if self.winfo_exists():
             self.status_var.set(message)
             self.status_label.config(foreground=color)

    def _test_connection(self):
        api_key = self.api_key_var.get().strip()
        trans_model = self.trans_model_var.get().strip()
        if not api_key: messagebox.showerror("错误", "请输入 Gemini API Key", parent=self); return
        if not trans_model: messagebox.showerror("错误", "请选择或输入翻译模型名称", parent=self); return

        self._set_status(f"正在测试连接 ({trans_model})...", "blue")
        self.test_button.config(state=tk.DISABLED)
        self.save_button.config(state=tk.DISABLED)
        thread = threading.Thread(target=self._test_connection_thread, args=(api_key, trans_model), daemon=True)
        thread.start()

    def _test_connection_thread(self, api_key, model_to_test):
        try:
            client = gemini.GeminiClient(api_key)
            success, message = client.test_connection(model_to_test)
            self.after(0, lambda: self._test_connection_result(success, message, model_to_test))
        except ConnectionError as e:
             self.after(0, lambda: self._test_connection_result(False, f"客户端初始化失败: {e}", model_to_test))
        except Exception as e:
            log.exception("Gemini 连接测试线程发生意外错误。")
            self.after(0, lambda: self._test_connection_result(False, f"测试时发生意外错误: {e}", model_to_test))

    def _test_connection_result(self, success, message, tested_model):
        if not self.winfo_exists(): return
        self.test_button.config(state=tk.NORMAL)
        if success:
            self.connection_tested_ok = True
            self._set_status(f"连接成功 ({tested_model})!", "green")
            self.save_button.config(state=tk.NORMAL)
            messagebox.showinfo("成功", message, parent=self)
        else:
            self.connection_tested_ok = False
            self._set_status(f"连接失败 ({tested_model})", "red")
            self.save_button.config(state=tk.DISABLED)
            messagebox.showerror("连接失败", message, parent=self)

    def _validate_and_get_json(self, text_widget, setting_name, require_list=False):
        """验证文本框中的 JSON 并返回解析后的对象或 None。"""
        json_str = text_widget.get("1.0", tk.END).strip()
        if not json_str:
             return {} if not require_list else [] # 空时返回空字典或空列表
        try:
            parsed_json = json.loads(json_str)
            if require_list and not isinstance(parsed_json, list):
                 messagebox.showerror("JSON 格式错误", f"{setting_name} 必须是一个 JSON 列表。", parent=self)
                 return None
            return parsed_json
        except json.JSONDecodeError as e:
            messagebox.showerror("JSON 格式错误", f"{setting_name} 中的 JSON 格式无效:\n{e}", parent=self)
            return None

    def _save_config(self):
        if not self.connection_tested_ok:
            messagebox.showwarning("无法保存", "请先成功测试连接 (翻译模型) 后再保存。", parent=self)
            return

        # --- 验证高级设置 JSON ---
        generation_config_json = self._validate_and_get_json(self.gen_config_text, "Generation Config")
        if generation_config_json is None: return

        safety_settings_json = self._validate_and_get_json(self.safety_text, "Safety Settings", require_list=True) # 强制要求是列表
        if safety_settings_json is None: return

        # --- 更新配置字典 ---
        shared_api_key = self.api_key_var.get().strip()

        # World Dict Config
        self.world_dict_config["api_key"] = shared_api_key
        self.world_dict_config["model"] = self.dict_model_var.get().strip()
        self.world_dict_config["character_prompt_template"] = self.char_prompt_text.get("1.0", tk.END).strip()
        self.world_dict_config["entity_prompt_template"] = self.entity_prompt_text.get("1.0", tk.END).strip()
        self.world_dict_config["character_dict_filename"] = self.world_dict_config.get("character_dict_filename", DEFAULT_WORLD_DICT_CONFIG["character_dict_filename"])
        self.world_dict_config["entity_dict_filename"] = self.world_dict_config.get("entity_dict_filename", DEFAULT_WORLD_DICT_CONFIG["entity_dict_filename"])

        # Translate Config
        self.translate_config["api_key"] = shared_api_key
        self.translate_config["model"] = self.trans_model_var.get().strip()
        self.translate_config["source_language"] = self.source_lang_var.get()
        self.translate_config["target_language"] = self.target_lang_var.get()
        try: self.translate_config["chunk_max_tokens"] = int(self.chunk_tokens_var.get())
        except ValueError: self.translate_config["chunk_max_tokens"] = DEFAULT_TRANSLATE_CONFIG["chunk_max_tokens"]
        try: self.translate_config["concurrency"] = int(self.concur_var.get())
        except ValueError: self.translate_config["concurrency"] = DEFAULT_TRANSLATE_CONFIG["concurrency"]
        try: self.translate_config["max_retries"] = int(self.retries_var.get())
        except ValueError: self.translate_config["max_retries"] = DEFAULT_TRANSLATE_CONFIG["max_retries"]
        self.translate_config["prompt_template"] = self.main_trans_prompt_text.get("1.0", tk.END).strip()
        self.translate_config["prompt_template_correction"] = self.corr_trans_prompt_text.get("1.0", tk.END).strip()
        self.translate_config["generation_config"] = generation_config_json
        self.translate_config["safety_settings"] = safety_settings_json # 保存验证过的列表

        # --- 通知 App 保存 ---
        if self.app and hasattr(self.app, 'save_config') and callable(self.app.save_config):
            if self.app.save_config(): # 调用保存并检查返回值
                 log.info("Gemini 配置已更新并保存。")
                 self.destroy() # 保存成功后关闭窗口
            else:
                 messagebox.showerror("保存失败", "无法将配置写入文件，请检查日志。", parent=self)
                 # 不关闭窗口，让用户可以复制配置
        else:
             log.error("无法调用 app.save_config() 方法。")
             messagebox.showerror("错误", "无法保存配置，App 控制器不可用。", parent=self)
