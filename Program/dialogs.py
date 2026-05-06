import tkinter as tk
from tkinter import simpledialog, ttk

from language import LANGUAGES
from utils import get_system_language

# 初始化语言设置
current_lang = get_system_language()
lang = LANGUAGES[current_lang]


class AddAccountDialog(simpledialog.Dialog):
    """用于手动添加账号密码的对话框，增加导入TXT功能"""
    def __init__(self, parent, title, import_txt_callback):
        self.import_txt_callback = import_txt_callback
        self.new_accounts_data = []
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
    
        if not content: return
        
        for line in content.split("\n"):
            line = line.strip()
            if "----" in line:
                # 分割成三部分：账号、密码、其它（最多分割两次）
                parts = line.split("----", 2)
                account = parts[0].strip()
                password = parts[1].strip() if len(parts) > 1 else ""
                others = parts[2].strip() if len(parts) > 2 else ""  # 处理第二个----后的内容
                if account and password:
                    self.new_accounts_data.append((account, password, others))

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