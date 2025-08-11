import tkinter as tk
from tkinter import ttk
from tkinter import simpledialog, messagebox
import datetime

# 注意：实际使用时需确保导入正确的语言配置
# 此处假设从 language 模块导入 LANGUAGES，实际路径需根据项目结构调整
from language import LANGUAGES
from utils import get_system_language

# 初始化语言设置
current_lang = get_system_language()
lang = LANGUAGES[current_lang]


class DaysHoursDialog(simpledialog.Dialog):
    """用于接收用户输入的天数和小时数的对话框"""
    def body(self, master):
        tk.Label(master, text=lang['days']).grid(row=0, column=0, padx=5, pady=5)
        tk.Label(master, text=lang['hours']).grid(row=1, column=0, padx=5, pady=5)
        
        # 使用 StringVar 允许空输入
        self.days_var = tk.StringVar(value="")
        self.hours_var = tk.StringVar(value="")
        
        self.days_entry = tk.Entry(master, textvariable=self.days_var)
        self.hours_entry = tk.Entry(master, textvariable=self.hours_var)
        
        self.days_entry.grid(row=0, column=1, padx=5, pady=5)
        self.hours_entry.grid(row=1, column=1, padx=5, pady=5)
        
        return self.days_entry  # 设置初始焦点

    def apply(self):
        days_str = self.days_var.get().strip()
        hours_str = self.hours_var.get().strip()
        
        # 验证输入是否为数字
        if (days_str and not days_str.isdigit()) or (hours_str and not hours_str.isdigit()):
            self.result = None
            return
            
        custom_days = int(days_str) if days_str else 0
        custom_hours = int(hours_str) if hours_str else 0
        self.result = (custom_days, custom_hours)

    def buttonbox(self):
        box = tk.Frame(self)
        
        tk.Button(box, text=lang['confirm'], width=10, command=self.ok, default=tk.ACTIVE).pack(
            side=tk.LEFT, padx=5, pady=5
        )
        tk.Button(box, text=lang['cancel'], width=10, command=self.cancel).pack(
            side=tk.LEFT, padx=5, pady=5
        )
        
        # 绑定快捷键
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        
        box.pack()


class DateTimeDialog(simpledialog.Dialog):
    """用于修改日期时间的对话框"""
    def __init__(self, parent, title, initial_datetime):
        self.initial_datetime = initial_datetime
        super().__init__(parent, title)
    
    def body(self, master):
        # 获取初始日期时间的各个部分
        year = self.initial_datetime.year
        month = self.initial_datetime.month
        day = self.initial_datetime.day
        hour = self.initial_datetime.hour
        minute = self.initial_datetime.minute
        
        # 创建变量存储用户输入
        self.year_var = tk.IntVar(value=year)
        self.month_var = tk.IntVar(value=month)
        self.day_var = tk.IntVar(value=day)
        self.hour_var = tk.IntVar(value=hour)
        self.minute_var = tk.IntVar(value=minute)
        
        # 创建输入控件
        tk.Label(master, text=lang['_year'] + ":").grid(row=0, column=0, padx=5, pady=5)
        tk.Spinbox(master, from_=2000, to=2100, textvariable=self.year_var, width=5).grid(
            row=0, column=1, padx=5, pady=5
        )
        
        tk.Label(master, text=lang['_month'] + ":").grid(row=0, column=2, padx=5, pady=5)
        tk.Spinbox(master, from_=1, to=12, textvariable=self.month_var, width=3).grid(
            row=0, column=3, padx=5, pady=5
        )
        
        tk.Label(master, text=lang['_day'] + ":").grid(row=0, column=4, padx=5, pady=5)
        tk.Spinbox(master, from_=1, to=31, textvariable=self.day_var, width=3).grid(
            row=0, column=5, padx=5, pady=5
        )
        
        tk.Label(master, text=lang['_hour'] + ":").grid(row=1, column=0, padx=5, pady=5)
        tk.Spinbox(master, from_=0, to=23, textvariable=self.hour_var, width=3).grid(
            row=1, column=1, padx=5, pady=5
        )
        
        tk.Label(master, text=lang['_minute'] + ":").grid(row=1, column=2, padx=5, pady=5)
        tk.Spinbox(master, from_=0, to=59, textvariable=self.minute_var, width=3).grid(
            row=1, column=3, padx=5, pady=5
        )
        
        return master

    def apply(self):
        try:
            self.result = datetime.datetime(
                self.year_var.get(),
                self.month_var.get(),
                self.day_var.get(),
                self.hour_var.get(),
                self.minute_var.get()
            )
        except ValueError as e:
            messagebox.showerror(lang['input_error'], lang['invalid_datetime'].format(error=e))
            self.result = None

    def buttonbox(self):
        box = tk.Frame(self)
        
        tk.Button(box, text=lang['confirm'], width=10, command=self.ok, default=tk.ACTIVE).pack(
            side=tk.LEFT, padx=5, pady=5
        )
        tk.Button(box, text=lang['cancel'], width=10, command=self.cancel).pack(
            side=tk.LEFT, padx=5, pady=5
        )
        
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        
        box.pack()


class AddAccountDialog(simpledialog.Dialog):
    """用于手动添加账号密码的对话框，增加导入TXT功能"""
    def __init__(self, parent, title, import_txt_callback):
        self.import_txt_callback = import_txt_callback
        super().__init__(parent, title)

    def buttonbox(self):
        pass
    
    def body(self, master):
        # 说明文本
        tk.Label(master, text=lang['enter_accounts']).pack(padx=10, pady=5)
        
        # 账号输入区域
        self.text_widget = tk.Text(master, width=50, height=10)
        self.text_widget.pack(padx=10, pady=5)
        
        # 添加导入TXT按钮
        import_frame = ttk.Frame(master)
        import_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(
            import_frame, 
            text=lang['import_txt'], 
            command=self.import_txt
        ).pack(side=tk.LEFT)

        ttk.Button(
            import_frame, 
            text=lang['confirm'], 
            command=self.ok
        ).pack(side=tk.LEFT)

        ttk.Button(
            import_frame, 
            text=lang['cancel'], 
            command=self.cancel
        ).pack(side=tk.LEFT)
        
        return self.text_widget  # 设置初始焦点

    def import_txt(self):
        """调用主窗口的导入TXT功能"""
        self.import_txt_callback()
        self.destroy()