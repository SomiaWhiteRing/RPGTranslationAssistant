# ui/pro_mode_panel.py
import tkinter as tk
from tkinter import ttk

class ProModePanel(ttk.Frame):
    def __init__(self, parent, app_controller, config):
        super().__init__(parent, padding="5")
        self.app = app_controller
        self.config = config
        self.pack(fill=tk.BOTH, expand=True)

        self.columnconfigure(0, weight=1)
        pro_settings = self.config.setdefault('pro_mode_settings', {})

        self.export_encoding_var = tk.StringVar(value=pro_settings.get('export_encoding', '932'))
        self.import_encoding_var = tk.StringVar(value=pro_settings.get('import_encoding', '936'))
        self.write_log_var = tk.BooleanVar(value=pro_settings.get('write_log_rename', True))
        self.rtp_button_text = tk.StringVar()

        self.encoding_options = [
            ("日语 (Shift-JIS)", "932"), ("中文简体 (GBK)", "936"), ("中文繁体 (Big5)", "950"),
            ("韩语 (EUC-KR)", "949"), ("泰语", "874"), ("拉丁语系 (西欧)", "1252"),
            ("东欧", "1250"), ("西里尔字母", "1251")
        ]
        self.encoding_display_values = [f"{name} - {code}" for name, code in self.encoding_options]

        all_controls_list = []
        row_idx = 0
        pady_val = 3; padx_val = 5; button_width = 8; config_button_width = 6; config_control_width = 20

        def create_row(parent_frame, description_title, description_text=None):
            row_frame = ttk.Frame(parent_frame)
            row_frame.grid(row=row_idx, column=0, sticky="ew", pady=pady_val)
            ttk.Label(row_frame, text=description_title, width=16).pack(side=tk.LEFT, padx=(padx_val, 0))
            if description_text: # 只有在提供了描述文本时才创建标签
                 ttk.Label(row_frame, text=description_text).pack(side=tk.LEFT, padx=(padx_val, 0))
            return row_frame

        # --- 0. 初始化 ---
        row_frame_0 = create_row(self, "0. 初始化", "复制RTP并转换编码")
        self.init_button = ttk.Button(row_frame_0, text="执行", width=button_width, command=lambda: self.app.start_task('initialize'))
        self.init_button.pack(side=tk.RIGHT, padx=padx_val)
        self.rtp_button = ttk.Button(row_frame_0, textvariable=self.rtp_button_text, width=config_control_width, command=lambda: self.app.start_task('select_rtp'))
        self.rtp_button.pack(side=tk.RIGHT, padx=padx_val)
        self.update_rtp_button_text()
        all_controls_list.extend([self.init_button, self.rtp_button])
        row_idx += 1

        # --- 1. 重写文件名 ---
        row_frame_1 = create_row(self, "1. 重写文件名", "非ASCII文件名转Unicode")
        self.rename_button = ttk.Button(row_frame_1, text="执行", width=button_width, command=lambda: self.app.start_task('rename'))
        self.rename_button.pack(side=tk.RIGHT, padx=padx_val)
        self.log_checkbutton = ttk.Checkbutton(row_frame_1, text="输出日志", variable=self.write_log_var, command=self._save_settings)
        self.log_checkbutton.pack(side=tk.RIGHT, padx=padx_val)
        all_controls_list.extend([self.rename_button, self.log_checkbutton])
        row_idx += 1

        # --- 2. 导出文本 ---
        row_frame_2 = create_row(self, "2. 导出文本", "导出文本到 StringScripts")
        self.export_button = ttk.Button(row_frame_2, text="执行", width=button_width, command=lambda: self.app.start_task('export'))
        self.export_button.pack(side=tk.RIGHT, padx=padx_val)
        encoding_frame_export = ttk.Frame(row_frame_2)
        encoding_frame_export.pack(side=tk.RIGHT, padx=padx_val)
        self.export_encoding_combo = ttk.Combobox(encoding_frame_export, textvariable=self.export_encoding_var, values=self.encoding_display_values, state="readonly", width=config_control_width - 2)
        ttk.Label(encoding_frame_export, text="编码:").pack(side=tk.LEFT, padx=(0, 2))
        self.export_encoding_combo.pack(side=tk.LEFT)
        self.export_encoding_combo.bind("<<ComboboxSelected>>", self._on_encoding_change)
        self._set_combobox_value(self.export_encoding_combo, self.export_encoding_var.get())
        all_controls_list.extend([self.export_button, self.export_encoding_combo])
        row_idx += 1

        # --- 3. 制作JSON文件 ---
        row_frame_3 = create_row(self, "3. 制作JSON文件", "StringScripts 压缩为 JSON")
        self.create_json_button = ttk.Button(row_frame_3, text="执行", width=button_width, command=lambda: self.app.start_task('create_json'))
        self.create_json_button.pack(side=tk.RIGHT, padx=padx_val)
        all_controls_list.append(self.create_json_button)
        row_idx += 1

        # --- 4. 生成世界观字典 ---
        row_frame_4 = create_row(self, "4. 生成世界观字典", "Gemini API 生成字典")
        self.gen_dict_button = ttk.Button(row_frame_4, text="执行", width=button_width, command=lambda: self.app.start_task('generate_dictionary'))
        self.gen_dict_button.pack(side=tk.RIGHT, padx=padx_val)
        # 修改 Gemini 配置按钮的命令
        self.gemini_config_button = ttk.Button(row_frame_4, text="配置", width=config_button_width,
                                            # 调用 App 的统一配置方法
                                            command=lambda: self.app._open_gemini_config_unified())
        self.gemini_config_button.pack(side=tk.RIGHT, padx=padx_val)
        self.edit_dict_button = ttk.Button(row_frame_4, text="编辑字典", width=10, command=lambda: self.app.start_task('edit_dictionary'))
        self.edit_dict_button.pack(side=tk.RIGHT, padx=padx_val)
        all_controls_list.extend([self.gen_dict_button, self.gemini_config_button, self.edit_dict_button])
        row_idx += 1

        # --- 5. 翻译JSON文件 ---
        row_frame_5 = create_row(self, "5. 翻译JSON文件", "Gemini API 翻译 JSON") # 修改描述
        self.translate_button = ttk.Button(row_frame_5, text="执行", width=button_width, command=lambda: self.app.start_task('translate'))
        self.translate_button.pack(side=tk.RIGHT, padx=padx_val)
        # 移除 Deepseek 配置按钮
        # self.deepseek_config_button = ttk.Button(...)
        # 可以选择在这里也加一个 Gemini 配置按钮，指向同一个统一配置窗口
        self.gemini_config_button_trans = ttk.Button(row_frame_5, text="配置", width=config_button_width,
                                                 command=lambda: self.app._open_gemini_config_unified())
        self.gemini_config_button_trans.pack(side=tk.RIGHT, padx=padx_val)
        all_controls_list.extend([self.translate_button, self.gemini_config_button_trans])
        row_idx += 1

        # --- 6. 释放JSON文件 ---
        row_frame_6 = create_row(self, "6. 释放JSON文件", "翻译后 JSON 释放")
        self.release_json_button = ttk.Button(row_frame_6, text="执行", width=button_width, command=lambda: self.app.start_task('release_json'))
        self.release_json_button.pack(side=tk.RIGHT, padx=padx_val)
        all_controls_list.append(self.release_json_button)
        row_idx += 1

        # --- 7. 导入文本 ---
        row_frame_7 = create_row(self, "7. 导入文本", "StringScripts 导入游戏")
        self.import_button = ttk.Button(row_frame_7, text="执行", width=button_width, command=lambda: self.app.start_task('import'))
        self.import_button.pack(side=tk.RIGHT, padx=padx_val)
        encoding_frame_import = ttk.Frame(row_frame_7)
        encoding_frame_import.pack(side=tk.RIGHT, padx=padx_val)
        self.import_encoding_combo = ttk.Combobox(encoding_frame_import, textvariable=self.import_encoding_var, values=self.encoding_display_values, state="readonly", width=config_control_width - 2)
        ttk.Label(encoding_frame_import, text="编码:").pack(side=tk.LEFT, padx=(0, 2))
        self.import_encoding_combo.pack(side=tk.LEFT)
        self.import_encoding_combo.bind("<<ComboboxSelected>>", self._on_encoding_change)
        self._set_combobox_value(self.import_encoding_combo, self.import_encoding_var.get())
        all_controls_list.extend([self.import_button, self.import_encoding_combo])
        row_idx += 1

        self.all_controls = all_controls_list

    def get_controls(self):
        return self.all_controls

    def update_rtp_button_text(self):
        pro_settings = self.config.get('pro_mode_settings', {}); rtp_opts = pro_settings.get('rtp_options', {})
        selected_rtps = [name for name, selected in rtp_opts.items() if selected]
        if not selected_rtps: self.rtp_button_text.set("RTP选择: 无")
        elif len(selected_rtps) == 1:
            name_map = {'2000': '2k', '2000en': '2kEN', '2003': '2k3', '2003steam': '2k3Steam'}; display_name = name_map.get(selected_rtps[0], selected_rtps[0])
            self.rtp_button_text.set(f"RTP: {display_name}")
        else: self.rtp_button_text.set(f"RTP: {len(selected_rtps)}个")

    def _set_combobox_value(self, combobox, code_value):
        for display_value in self.encoding_display_values:
            if display_value.endswith(f" - {code_value}"): combobox.set(display_value); return
        if self.encoding_display_values: combobox.set(self.encoding_display_values[0]) # Fallback

    def _on_encoding_change(self, event=None): self._save_settings()

    def _save_settings(self):
        export_display = self.export_encoding_var.get(); import_display = self.import_encoding_var.get()
        export_code = export_display.split(' - ')[-1] if ' - ' in export_display else '932'
        import_code = import_display.split(' - ')[-1] if ' - ' in import_display else '936'
        settings_to_save = {
            'export_encoding': export_code, 'import_encoding': import_code,
            'write_log_rename': self.write_log_var.get(),
        }
        if hasattr(self.app, 'save_pro_mode_settings'): self.app.save_pro_mode_settings(settings_to_save)