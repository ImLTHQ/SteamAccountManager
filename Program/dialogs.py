import tkinter as tk
from tkinter import simpledialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
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
            messagebox.showerror(lang['input_error'], lang['invalid_datetime'])
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
        self.new_accounts_data = []
        self.invalid_count = 0  # 统计无效行数
        self.total_lines = 0  # 统计总行数
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
        self.import_txt_callback()

    def apply(self):
        content = self.text_widget.get("1.0", tk.END).strip()
        self.new_accounts_data = []
        self.invalid_count = 0
        self.total_lines = 0
        self.result = True  # 标记为点了确定
    
        if not content: 
            self.invalid_count = 0
            return
        
        for line in content.split("\n"):
            line = line.strip()
            self.total_lines += 1
            if "----" in line:
                # 分割成三部分：账号、密码、其它（最多分割两次）
                parts = line.split("----", 2)
                account = parts[0].strip()
                password = parts[1].strip() if len(parts) > 1 else ""
                others = parts[2].strip() if len(parts) > 2 else ""  # 处理第二个----后的内容
                if account and password:
                    self.new_accounts_data.append((account, password, others))
                else:
                    self.invalid_count += 1
            else:
                self.invalid_count += 1

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

class ProfileEditDialog(simpledialog.Dialog):
    """用于修改Steam个人资料的对话框（昵称 / 真实姓名 / 概要）

    result 为 (昵称, 真实姓名, 概要) 元组；点取消或关闭窗口时 result 为 None
    长度上限按 UTF-8 字节计算，超长会被 Steam 静默截断，所以在提交前就拦下来：
    超长时点确定不会关闭窗口，而是在对话框底部用红字提示并禁用确定按钮
    """
    def __init__(self, parent, title, current_name="", current_real_name="", current_summary="",
                 limits=None):
        self.current_name = current_name or ""
        self.current_real_name = current_real_name or ""
        self.current_summary = current_summary or ""
        self.limits = limits or {}
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text=lang['edit_profile_persona_name'] + ":").grid(
            row=0, column=0, padx=5, pady=5, sticky=tk.E)
        self.name_var = tk.StringVar(value=self.current_name)
        self.name_entry = ttk.Entry(master, textvariable=self.name_var, width=50)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Label(master, text=lang['edit_profile_real_name'] + ":").grid(
            row=1, column=0, padx=5, pady=5, sticky=tk.E)
        self.real_name_var = tk.StringVar(value=self.current_real_name)
        self.real_name_entry = ttk.Entry(master, textvariable=self.real_name_var, width=50)
        self.real_name_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Label(master, text=lang['edit_profile_summary'] + ":").grid(
            row=2, column=0, padx=5, pady=5, sticky=tk.NE)
        self.summary_text = ScrolledText(master, width=50, height=8, wrap=tk.WORD)
        self.summary_text.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)

        # 底部提示：正常情况下显示各项长度上限，超长时变成红色的错误提示
        self.status_label = ttk.Label(master, text=self._limits_hint(), foreground="gray")
        self.status_label.grid(row=3, column=0, columnspan=2, padx=5, pady=(0, 5), sticky=tk.W)

        # 输入变化时实时校验（Text 控件没有 textvariable，用 <<Modified>> 事件）
        for var in (self.name_var, self.real_name_var):
            var.trace_add("write", lambda *_: self._on_input_changed())
        self.summary_text.bind("<<Modified>>", self._on_summary_modified)
        # 输入框失去焦点时再校验一次，避免实时提示闪烁
        for widget in (self.name_entry, self.real_name_entry, self.summary_text):
            widget.bind("<FocusOut>", lambda event: self._on_input_changed())

        # 回填当前资料：预填会触发事件，这里放在最后
        self.summary_text.insert("1.0", self.current_summary)
        self.summary_text.edit_modified(False)

        return self.name_entry  # 设置初始焦点

    # ---------- 长度校验与提示 ----------

    def _limits_hint(self):
        """正常情况下显示各项长度上限（按 UTF-8 字节计算，中文一个字 3 字节）"""
        return " / ".join(
            f"{label}: {self.limits[key]}{lang['edit_profile_bytes']}"
            for key, label in (
                ('personaName', lang['edit_profile_persona_name']),
                ('real_name', lang['edit_profile_real_name']),
                ('summary', lang['edit_profile_summary']),
            )
            if self.limits.get(key)
        )

    def _on_summary_modified(self, event=None):
        # ScrolledText 的 <<Modified>> 只会触发一次，处理完要复位标志
        self.summary_text.edit_modified(False)
        self._on_input_changed()

    def _on_input_changed(self):
        """输入变化时检查长度：超长就红字提示并禁用确定按钮"""
        ok_button = getattr(self, 'ok_button', None)
        if ok_button is None:
            # buttonbox 还没建好（body 阶段），等确定按钮创建后再统一刷新
            return
        error = self._find_too_long()
        if error is None:
            self.status_label.config(text=self._limits_hint(), foreground="gray")
            ok_button.state(["!disabled"])
        else:
            self.status_label.config(text=error, foreground="red")
            ok_button.state(["disabled"])

    def _find_too_long(self):
        """返回第一条超长提示文字；全部合法时返回 None"""
        for key, value in (
            ('personaName', self.name_var.get().strip()),
            ('real_name', self.real_name_var.get().strip()),
            ('summary', self.summary_text.get("1.0", tk.END).strip()),
        ):
            limit = self.limits.get(key)
            size = len(value.encode('utf-8'))
            if limit and size > limit:
                return lang['edit_profile_too_long'].format(
                    field=lang['edit_profile_field_labels'][key],
                    bytes=size,
                    limit=limit)
        return None

    def _read_values(self):
        return (
            self.name_var.get().strip(),
            self.real_name_var.get().strip(),
            self.summary_text.get("1.0", tk.END).strip(),
        )

    def ok(self, event=None):
        # 超长时保持对话框打开，把提示显示在对话框里（避免弹出的提示窗被挡住看不见）
        error = self._find_too_long()
        if error is not None:
            self._on_input_changed()
            self.status_label.config(text=error, foreground="red")
            self.lift()
            self.focus_force()
            return
        super().ok()

    def apply(self):
        self.result = self._read_values()

    def buttonbox(self):
        box = ttk.Frame(self)

        self.ok_button = ttk.Button(box, text=lang['confirm'], width=10, command=self.ok)
        self.ok_button.pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text=lang['cancel'], width=10, command=self.cancel).pack(
            side=tk.LEFT, padx=5, pady=5
        )

        # 绑定快捷键（概要是多行文本，Enter 不触发确定）
        self.bind("<Escape>", self.cancel)

        box.pack(padx=5, pady=10)
        # 确定按钮已就绪，按当前输入刷新一次提示/可用状态
        self._on_input_changed()


class ExportMethodDialog(simpledialog.Dialog):
    """用于选择导出方式的对话框（TXT文件或剪贴板）"""
    def __init__(self, parent):
        self.result = None  # 存储用户选择的导出方式："txt" 或 "clipboard"
        super().__init__(parent, title=lang['select_export_method'])

    def body(self, master):
        # 不添加说明文本，只保留标题
        return master

    def buttonbox(self):
        box = ttk.Frame(self)
        
        # TXT文件按钮
        ttk.Button(
            box, 
            text=lang['txt_file'], 
            width=15, 
            command=lambda: self.set_result("txt")
        ).pack(side=tk.LEFT, padx=10, pady=10)
        
        # 剪贴板按钮
        ttk.Button(
            box, 
            text=lang['clipboard'], 
            width=15, 
            command=lambda: self.set_result("clipboard")
        ).pack(side=tk.LEFT, padx=10, pady=10)
        
        box.pack(padx=10, pady=10)

    def set_result(self, method):
        """设置导出方式并关闭对话框"""
        self.result = method
        self.ok()