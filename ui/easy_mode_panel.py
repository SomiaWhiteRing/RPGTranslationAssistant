# ui/easy_mode_panel.py
import tkinter as tk
from tkinter import ttk

class EasyModePanel(ttk.Frame):
    """轻松模式的 UI 面板类。"""

    def __init__(self, parent, app_controller):
        super().__init__(parent, padding="10")
        self.app = app_controller
        self.pack(fill=tk.BOTH, expand=True)

        self.progress_var = tk.DoubleVar(value=0.0)
        self.status_var = tk.StringVar(value="选择游戏目录后点击“开始翻译”")

        button_container = ttk.Frame(self)
        button_container.pack(pady=20)

        # Gemini 配置按钮 (调用统一配置窗口)
        self.gemini_config_button = ttk.Button(
            button_container,
            text="Gemini配置",
            # 调用 App 的统一配置方法
            command=lambda: self.app._open_gemini_config_unified(),
            width=15
        )
        self.gemini_config_button.pack(side=tk.LEFT, padx=10)

        # 移除 Deepseek 配置按钮
        # self.deepseek_config_button = ttk.Button(...)

        # 开始翻译按钮
        self.start_button = ttk.Button(
            button_container,
            text="开始翻译",
            command=lambda: self.app.start_task('easy_flow', mode='easy'),
            width=15
        )
        self.start_button.pack(side=tk.LEFT, padx=10)

        # 开始游戏按钮
        self.start_game_button = ttk.Button(
            button_container,
            text="开始游戏",
            command=lambda: self.app.start_task('start_game'),
            width=15
        )
        self.start_game_button.pack(side=tk.LEFT, padx=10)

        # 进度条
        self.progressbar = ttk.Progressbar(
            self, variable=self.progress_var, maximum=100, mode='determinate'
        )
        self.progressbar.pack(fill=tk.X, padx=10, pady=(20, 5))

        # 状态标签
        self.status_label = ttk.Label(self, textvariable=self.status_var, anchor=tk.CENTER)
        self.status_label.pack(fill=tk.X, padx=10, pady=(0, 10))

        # 保存控件引用 (移除 deepseek 按钮)
        self.controls = [
            self.gemini_config_button,
            self.start_button,
            self.start_game_button,
        ]

    def get_controls(self):
        return self.controls

    def update_status(self, message):
        self.status_var.set(message)

    def update_progress(self, value):
        if 0 <= value <= 100: self.progress_var.set(value)
        else: print(f"无效的进度值: {value}")

    def reset_state(self):
        self.progress_var.set(0.0)
        self.status_var.set("选择游戏目录后点击“开始翻译”")