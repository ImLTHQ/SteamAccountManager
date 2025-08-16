import tkinter as tk
from tkinter import simpledialog, messagebox, ttk
import datetime

from language import LANGUAGES
from utils import get_system_language

# 初始化语言设置
current_lang = get_system_language()
lang = LANGUAGES[current_lang]


class DaysHoursDialog(simpledialog.Dialog):
    """用于接收用户输入的天数和小时数的对话框"""
    def body(self, master):
        ttk.Label(master, text=lang['days'] + ":").grid(row=0, column=0, padx=5, pady=5)
        ttk.Label(master, text=lang['hours'] + ":").grid(row=1, column=0, padx=5, pady=5)
        
        # 使用 StringVar 允许空输入
        self.days_var = tk.StringVar(value="")
        self.hours_var = tk.StringVar(value="")
        
        self.days_entry = ttk.Entry(master, textvariable=self.days_var)
        self.hours_entry = ttk.Entry(master, textvariable=self.hours_var)
        
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
        box = ttk.Frame(self)
        
        ttk.Button(box, text=lang['confirm'], width=10, command=self.ok).pack(
            side=tk.LEFT, padx=5, pady=5
        )
        ttk.Button(box, text=lang['cancel'], width=10, command=self.cancel).pack(
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
        ttk.Label(master, text=lang['_year'] + ":").grid(row=0, column=0, padx=5, pady=5)
        ttk.Spinbox(master, from_=2000, to=2100, textvariable=self.year_var, width=5).grid(
            row=0, column=1, padx=5, pady=5
        )
        
        ttk.Label(master, text=lang['_month'] + ":").grid(row=0, column=2, padx=5, pady=5)
        ttk.Spinbox(master, from_=1, to=12, textvariable=self.month_var, width=3).grid(
            row=0, column=3, padx=5, pady=5
        )
        
        ttk.Label(master, text=lang['_day'] + ":").grid(row=0, column=4, padx=5, pady=5)
        ttk.Spinbox(master, from_=1, to=31, textvariable=self.day_var, width=3).grid(
            row=0, column=5, padx=5, pady=5
        )
        
        ttk.Label(master, text=lang['_hour'] + ":").grid(row=1, column=0, padx=5, pady=5)
        ttk.Spinbox(master, from_=0, to=23, textvariable=self.hour_var, width=3).grid(
            row=1, column=1, padx=5, pady=5
        )
        
        ttk.Label(master, text=lang['_minute'] + ":").grid(row=1, column=2, padx=5, pady=5)
        ttk.Spinbox(master, from_=0, to=59, textvariable=self.minute_var, width=3).grid(
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
        box = ttk.Frame(self)
        
        ttk.Button(box, text=lang['confirm'], width=10, command=self.ok).pack(
            side=tk.LEFT, padx=5, pady=5
        )
        ttk.Button(box, text=lang['cancel'], width=10, command=self.cancel).pack(
            side=tk.LEFT, padx=5, pady=5
        )

        box.pack()


class AddAccountDialog(simpledialog.Dialog):
    """用于手动添加账号密码的对话框，增加导入TXT功能"""
    def __init__(self, parent, title, import_txt_callback):
        self.import_txt_callback = import_txt_callback
        self.new_accounts_data = []  # 初始化账号数据列表，解决属性不存在问题
        super().__init__(parent, title)

    def buttonbox(self):
        pass
    
    def body(self, master):
        ttk.Label(master, text=lang['enter_accounts']).pack(padx=10, pady=5)
        
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
        """调用主窗口的导入TXT功能并接收返回结果"""
        # 获取导入的账号数据，如果用户取消则返回空列表
        imported_data = self.import_txt_callback() or []
        self.new_accounts_data = imported_data
        self.destroy()

    def cancel(self):
        """取消操作时确保属性有默认值"""
        self.new_accounts_data = []
        super().cancel()

    def apply(self):
        content = self.text_widget.get("1.0", tk.END).strip()
        self.new_accounts_data = []
        
        if not content:
            return
            
        for line in content.split("\n"):
            line = line.strip()
            if "----" in line:
                parts = line.split("----", 1)
                account = parts[0].strip()
                password = parts[1].strip()
                if account and password:
                    self.new_accounts_data.append((account, password))

class CustomRemarkDialog(simpledialog.Dialog):
    """用于输入自定义备注的对话框"""
    def __init__(self, parent, title, initial_remark=""):
        self.initial_remark = initial_remark
        self.result = None  # 存储用户输入的备注
        super().__init__(parent, title)

    def body(self, master):
        # 显示提示文本
        ttk.Label(master, text=lang['enter_custom_remark']).pack(padx=10, pady=5, anchor=tk.W)
        
        # 创建输入框并设置初始值
        self.remark_var = tk.StringVar(value=self.initial_remark)
        self.remark_entry = ttk.Entry(master, textvariable=self.remark_var, width=40)
        self.remark_entry.pack(padx=10, pady=5, fill=tk.X)
        
        return self.remark_entry  # 设置初始焦点

    def apply(self):
        # 获取并处理用户输入
        self.result = self.remark_var.get().strip()

    def buttonbox(self):
        # 使用ttk按钮替换默认按钮
        box = ttk.Frame(self)
        
        # 确定按钮
        ttk.Button(box, text=lang['confirm'], width=10, command=self.ok).pack(
            side=tk.LEFT, padx=5, pady=5
        )
        
        # 取消按钮
        ttk.Button(box, text=lang['cancel'], width=10, command=self.cancel).pack(
            side=tk.LEFT, padx=5, pady=5
        )
        
        # 绑定快捷键
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        
        box.pack(padx=5, pady=10)