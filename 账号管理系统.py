import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import datetime
import json
import urllib.request
import pypinyin
from pypinyin import Style
import locale

# 版本和GitHub信息
version = "1.5.1"
github_url = "https://raw.githubusercontent.com/ImLTHQ/SteamAccountManager/main/version"

# 国际化支持
LANGUAGES = {
    'zh': {
        'app_title': "账号管理系统 - v{version}",
        'new_version': " [有新版本]",
        'import_txt': "导入TXT",
        'export_selected': "导出选中",
        'manual_add': "手动添加",
        'refresh': "刷新",
        'search': "搜索:",
        'show_available_only': "只显示可用",
        'show_remarked_only': "只显示已备注",
        'delete_selected': "删除选中",
        'select_all_toggle': "全选/取消全选",
        'batch_remark': "批量备注",
        'github_label': "GitHub: ImLTHQ/SteamAccountManager",
        'columns': {
            'index': "序号",
            'select': "选择",
            'account': "账号",
            'password': "密码",
            'status': "状态",
            'available_time': "可用时间",
            'remarks': "备注",
            'shortcut': "冷却时间"
        },
        'status_available': "可用",
        'status_unavailable': "不可用",
        'remarks_options': ["清空", "一级", "二级"],
        'days': "天数:",
        'hours': "小时:",
        'confirm': "确定",
        'cancel': "取消",
        'input_error': "输入错误",
        'invalid_datetime': "无效的日期时间: {error}",
        'enter_accounts': "请输入账号和密码（每行一个，格式：账号----密码）:",
        'modify_available_time': "修改可用时间",
        'immediately_available': "立即可用",
        'custom_days_hours': "自定义天数/小时",
        'custom_remark': "自定义备注",
        'enter_custom_remark': "请输入自定义备注:",
        'import_success': "导入成功",
        'imported_new_accounts': "成功导入 {count} 个新账号",
        'import_no_new': "没有新的账号被导入（可能已存在或格式不正确）",
        'import_error': "导入错误",
        'import_failed': "导入文件失败: {error}",
        'add_success': "添加成功",
        'added_new_accounts': "成功添加 {count} 个新账号",
        'add_no_new': "没有新的账号被添加（可能已存在）",
        'save_failed': "保存失败",
        'save_error': "保存数据失败: {error}",
        'load_error': "加载错误",
        'load_failed': "加载数据失败: {error}",
        'delete_no_selected': "删除选中",
        'delete_no_accounts': "没有选中的账号可删除",
        'confirm_delete': "确认删除",
        'confirm_delete_msg': "确定要删除选中的 {count} 个账号吗?",
        'delete_success': "删除成功",
        'deleted_accounts': "{count} 个账号已删除",
        'export_no_selected': "导出选中",
        'export_no_accounts': "没有选中的账号可导出",
        'export_success': "导出成功",
        'exported_accounts': "成功导出 {count} 个账号到 {path}",
        'export_error': "导出错误",
        'export_failed': "导出文件失败: {error}",
        'batch_remark_success': "批量备注",
        'batch_remark_msg': "已为 {count} 个账号设置备注为: {remark}",
        # 时间单位（中文单复数相同）
        'day': "天",
        'days': "天",
        'hour': "小时",
        'hours': "小时",
        'less_than_one_hour': "不足1小时",
        # 快捷菜单时间选项
        'shortcut_20h': "20小时",
        'shortcut_3d': "3天",
        'shortcut_7d': "7天",
        'shortcut_14d': "14天",
        'shortcut_31d': "31天",
        'shortcut_45d': "45天",
        'shortcut_181d': "181天"
    },
    'en': {
        'app_title': "Account Management System - v{version}",
        'new_version': " [New Version Available]",
        'import_txt': "Import TXT",
        'export_selected': "Export Selected",
        'manual_add': "Add Manually",
        'refresh': "Refresh",
        'search': "Search:",
        'show_available_only': "Show Available Only",
        'show_remarked_only': "Show Remarked Only",
        'delete_selected': "Delete Selected",
        'select_all_toggle': "Select All/None",
        'batch_remark': "Batch Remark",
        'github_label': "GitHub: ImLTHQ/SteamAccountManager",
        'columns': {
            'index': "No.",
            'select': "Select",
            'account': "Account",
            'password': "Password",
            'status': "Status",
            'available_time': "Available Time",
            'remarks': "Remarks",
            'shortcut': "Cooldown"
        },
        'status_available': "Available",
        'status_unavailable': "Unavailable",
        'remarks_options': ["Clear", "Level 1", "Level 2"],
        'days': "Days:",
        'hours': "Hours:",
        'confirm': "OK",
        'cancel': "Cancel",
        'input_error': "Input Error",
        'invalid_datetime': "Invalid date/time: {error}",
        'enter_accounts': "Please enter accounts and passwords (one per line, format: account----password):",
        'modify_available_time': "Modify Available Time",
        'immediately_available': "Immediately Available",
        'custom_days_hours': "Custom Days/Hours",
        'custom_remark': "Custom Remark",
        'enter_custom_remark': "Please enter custom remark:",
        'import_success': "Import Successful",
        'imported_new_accounts': "Successfully imported {count} new accounts",
        'import_no_new': "No new accounts imported (may already exist or incorrect format)",
        'import_error': "Import Error",
        'import_failed': "Failed to import file: {error}",
        'add_success': "Add Successful",
        'added_new_accounts': "Successfully added {count} new accounts",
        'add_no_new': "No new accounts added (may already exist)",
        'save_failed': "Save Failed",
        'save_error': "Failed to save data: {error}",
        'load_error': "Load Error",
        'load_failed': "Failed to load data: {error}",
        'delete_no_selected': "Delete Selected",
        'delete_no_accounts': "No selected accounts to delete",
        'confirm_delete': "Confirm Delete",
        'confirm_delete_msg': "Are you sure you want to delete {count} selected accounts?",
        'delete_success': "Delete Successful",
        'deleted_accounts': "{count} accounts have been deleted",
        'export_no_selected': "Export Selected",
        'export_no_accounts': "No selected accounts to export",
        'export_success': "Export Successful",
        'exported_accounts': "Successfully exported {count} accounts to {path}",
        'export_error': "Export Error",
        'export_failed': "Failed to export file: {error}",
        'batch_remark_success': "Batch Remark",
        'batch_remark_msg': "Set remark for {count} accounts to: {remark}",
        # 时间单位（英文区分单复数）
        'day': "day",
        'days': "days",
        'hour': "hour",
        'hours': "hours",
        'less_than_one_hour': "Less than 1 hour",
        # 快捷菜单时间选项
        'shortcut_20h': "20 hours",
        'shortcut_3d': "3 days",
        'shortcut_7d': "7 days",
        'shortcut_14d': "14 days",
        'shortcut_31d': "31 days",
        'shortcut_45d': "45 days",
        'shortcut_181d': "181 days"
    }
}

# 检测系统语言
def get_system_language():
    try:
        lang, _ = locale.getdefaultlocale()
        if lang:
            if lang.startswith('zh'):
                return 'zh'
            elif lang.startswith('en'):
                return 'en'
    except Exception:
        pass
    return 'en'  # 默认英语

# 获取当前语言
current_lang = get_system_language()
lang = LANGUAGES[current_lang]

def check_for_update():
    try:
        with urllib.request.urlopen(github_url, timeout=3) as response:
            remote_version = response.read().decode('utf-8-sig').strip()
            if remote_version != version:
                current_title = root.title()
                if lang['new_version'] not in current_title:
                    root.title(current_title + lang['new_version'])
    except Exception:
        pass

def get_pinyin_initial_abbr(text):
    # 获取中文文本每个字的拼音首字母大写缩写
    if not text:
        return ""
    # 处理每个字符的拼音首字母
    initials = []
    for char in text:
        # 获取拼音首字母（忽略声调）
        pinyin_list = pypinyin.pinyin(char, style=Style.FIRST_LETTER, strict=False)
        if pinyin_list and pinyin_list[0]:
            initial = pinyin_list[0][0].upper()  # 转为大写
            initials.append(initial)
        else:
            # 非中文字符直接保留（转为大写）
            initials.append(str(char).upper())
    return ''.join(initials)


class DaysHoursDialog(simpledialog.Dialog):
    def body(self, master):
        tk.Label(master, text=lang['days']).grid(row=0, column=0, padx=5, pady=5)
        tk.Label(master, text=lang['hours']).grid(row=1, column=0, padx=5, pady=5)
        # 使用 StringVar 来允许空输入
        self.days_var = tk.StringVar(value="")
        self.hours_var = tk.StringVar(value="")
        self.days_entry = tk.Entry(master, textvariable=self.days_var)
        self.hours_entry = tk.Entry(master, textvariable=self.hours_var)
        self.days_entry.grid(row=0, column=1, padx=5, pady=5)
        self.hours_entry.grid(row=1, column=1, padx=5, pady=5)
        return self.days_entry

    def apply(self):
        days_str = self.days_var.get().strip()
        hours_str = self.hours_var.get().strip()
        # 当输入非数字时不执行任何操作，仅关闭对话框
        if (days_str and not days_str.isdigit()) or (hours_str and not hours_str.isdigit()):
            self.result = None
            return
        custom_days = int(days_str) if days_str else 0
        custom_hours = int(hours_str) if hours_str else 0
        self.result = (custom_days, custom_hours)

    def buttonbox(self):
        box = tk.Frame(self)
        w = tk.Button(box, text=lang['confirm'], width=10, command=self.ok, default=tk.ACTIVE)
        w.pack(side=tk.LEFT, padx=5, pady=5)
        w = tk.Button(box, text=lang['cancel'], width=10, command=self.cancel)
        w.pack(side=tk.LEFT, padx=5, pady=5)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack()


class DateTimeDialog(simpledialog.Dialog):
    # 用于修改日期时间的对话框
    def __init__(self, parent, title, initial_datetime):
        self.initial_datetime = initial_datetime
        super().__init__(parent, title)
    
    def body(self, master):
        # 获取当前日期时间的各个部分
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
        
        # 创建输入框
        tk.Label(master, text="Year:").grid(row=0, column=0, padx=5, pady=5)
        tk.Spinbox(master, from_=2000, to=2100, textvariable=self.year_var, width=5).grid(row=0, column=1, padx=5, pady=5)
        
        tk.Label(master, text="Month:").grid(row=0, column=2, padx=5, pady=5)
        tk.Spinbox(master, from_=1, to=12, textvariable=self.month_var, width=3).grid(row=0, column=3, padx=5, pady=5)
        
        tk.Label(master, text="Day:").grid(row=0, column=4, padx=5, pady=5)
        tk.Spinbox(master, from_=1, to=31, textvariable=self.day_var, width=3).grid(row=0, column=5, padx=5, pady=5)
        
        tk.Label(master, text="Hour:").grid(row=1, column=0, padx=5, pady=5)
        tk.Spinbox(master, from_=0, to=23, textvariable=self.hour_var, width=3).grid(row=1, column=1, padx=5, pady=5)
        
        tk.Label(master, text="Minute:").grid(row=1, column=2, padx=5, pady=5)
        tk.Spinbox(master, from_=0, to=59, textvariable=self.minute_var, width=3).grid(row=1, column=3, padx=5, pady=5)
        
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
        # 创建按钮框
        box = tk.Frame(self)
        
        # 确定按钮
        w = tk.Button(box, text=lang['confirm'], width=10, command=self.ok, default=tk.ACTIVE)
        w.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 取消按钮
        w = tk.Button(box, text=lang['cancel'], width=10, command=self.cancel)
        w.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 绑定回车键和ESC键
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        
        box.pack()

class ManualAddAccountDialog(simpledialog.Dialog):
    def body(self, master):
        tk.Label(master, text=lang['enter_accounts']).pack(padx=10, pady=5)
        self.text_widget = tk.Text(master, width=50, height=10)
        self.text_widget.pack(padx=10, pady=5)
        return self.text_widget

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

    def buttonbox(self):
        # 重写buttonbox方法，移除回车键绑定
        box = tk.Frame(self)
        w = tk.Button(box, text=lang['confirm'], width=10, command=self.ok, default=tk.ACTIVE)
        w.pack(side=tk.LEFT, padx=5, pady=5)
        w = tk.Button(box, text=lang['cancel'], width=10, command=self.cancel)
        w.pack(side=tk.LEFT, padx=5, pady=5)
        # 只保留ESC键绑定，移除回车键绑定
        self.bind("<Escape>", self.cancel)
        box.pack()

class AccountManagerApp:
    # 添加"序号"列作为第一列
    COLUMNS = ("index", "select", "account", "password", "status", "available_time", "remarks", "shortcut")
    COLUMN_WIDTHS = {
        "index": 25, "select": 50, "account": 100, "password": 100, "status": 70,
        "available_time": 130, "remarks": 100, "shortcut": 100
    }
    COLUMN_ANCHORS = {
        "index": tk.CENTER, "select": tk.CENTER, "status": tk.CENTER, "available_time": tk.CENTER,
        "remarks": tk.CENTER, "shortcut": tk.CENTER
    }
    REMARKS_TO_JSON = {"": 0, "一级": 1, "二级": 2, "Level 1": 1, "Level 2": 2}
    REMARKS_FROM_JSON = {0: "", 1: lang['remarks_options'][1], 2: lang['remarks_options'][2]}
    # 排序箭头常量
    SORT_ASC = " ↑"  # 升序箭头
    SORT_DESC = " ↓" # 降序箭头

    def __init__(self, root_window):
        self.root = root_window
        self.root.title(lang['app_title'].format(version=version))
        self.root.geometry("1000x600")
        self.accounts_data = []
        self.original_data = []  # 保存原始数据用于恢复未排序状态
        self.data_file = "accounts_data.json"
        self._drag_start_item = None
        self._last_selected_items_in_drag = set()
        self._selection_mode_toggle = None
        self.remarks_sort_reverse = False
        self.sorting_state = {}  # 存放各列排序状态：None=未排序, False=升序, True=降序
        self.setup_ui()
        self._configure_treeview_style()
        self.load_data()

    def _configure_treeview_style(self):
        style = ttk.Style()
        style.map('Treeview',
                  background=[('selected', 'lightgreen')],
                  foreground=[('selected', 'black')])
        self.tree.tag_configure(lang['status_available'], background="#e0e0e0", foreground="black")
        self.tree.tag_configure(lang['status_unavailable'], background="salmon")

    def setup_ui(self):
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)
        buttons_data = [
            (lang['import_txt'], self.import_txt),
            (lang['export_selected'], self.export_txt),
            (lang['manual_add'], self.manual_add_account_dialog),
            (lang['refresh'], self.refresh_treeview),
        ]
        for text, command in buttons_data:
            ttk.Button(top_frame, text=text, command=command).pack(side=tk.LEFT, padx=5)
        # 在 top_frame 的右侧添加搜索框
        search_box_frame = ttk.Frame(top_frame)
        search_box_frame.pack(side=tk.RIGHT, padx=5)
        ttk.Label(search_box_frame, text=lang['search']).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_box_frame, textvariable=self.search_var, width=20)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind("<KeyRelease>", lambda event: self.filter_treeview())
        
        search_frame = ttk.Frame(self.root, padding="10")
        search_frame.pack(fill=tk.X)
        self.show_available_only_var = tk.BooleanVar()
        ttk.Checkbutton(search_frame, text=lang['show_available_only'], variable=self.show_available_only_var, command=self.filter_treeview).pack(side=tk.LEFT, padx=5)
        
        # 只显示已备注
        self.show_remarked_only_var = tk.BooleanVar()
        ttk.Checkbutton(search_frame, text=lang['show_remarked_only'], variable=self.show_remarked_only_var, command=self.filter_treeview).pack(side=tk.LEFT, padx=5)
        
        # 删除按钮先不显示
        self.delete_btn = ttk.Button(search_frame, text=lang['delete_selected'], command=self.delete_selected)
        ttk.Button(search_frame, text=lang['select_all_toggle'], command=self.select_all_toggle).pack(side=tk.RIGHT, padx=5)
        # 默认不显示删除按钮
        self.delete_btn.pack_forget()

        # 批量备注下拉栏和按钮（默认隐藏）
        self.batch_remarks_var = tk.StringVar()
        self.batch_remarks_combo = ttk.Combobox(
            search_frame, textvariable=self.batch_remarks_var, state="normal", width=8
        )
        self.batch_remarks_combo['values'] = lang['remarks_options']
        self.batch_remarks_combo.set("")
        self.batch_remarks_btn = ttk.Button(search_frame, text=lang['batch_remark'], command=self.batch_set_remarks)
        self.batch_remarks_combo.pack_forget()
        self.batch_remarks_btn.pack_forget()
        
        tree_frame = ttk.Frame(self.root, padding="10")
        tree_frame.pack(expand=True, fill=tk.BOTH)
        self.tree = ttk.Treeview(tree_frame, columns=self.COLUMNS, show="headings")
        for col_id in self.COLUMNS:
            self.tree.heading(col_id, text=lang['columns'][col_id])
            self.tree.column(col_id, width=self.COLUMN_WIDTHS[col_id], anchor=self.COLUMN_ANCHORS.get(col_id, tk.W))
        # 为下列列增加点击排序功能
        self.tree.heading("remarks", text=lang['columns']["remarks"], command=lambda: self.sort_by_column("remarks"))
        self.tree.heading("shortcut", text=lang['columns']["shortcut"], command=lambda: self.sort_by_column("shortcut"))
        self.tree.heading("account", text=lang['columns']["account"], command=lambda: self.sort_by_column("account"))
        self.tree.heading("status", text=lang['columns']["status"], command=lambda: self.sort_by_column("status"))
        # 添加可用时间列的排序功能
        self.tree.heading("available_time", text=lang['columns']["available_time"], command=lambda: self.sort_by_column("available_time"))
        self.tree.pack(expand=True, fill=tk.BOTH, side=tk.LEFT)
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<ButtonPress-1>", self.on_tree_button_press)
        self.tree.bind("<B1-Motion>", self.on_tree_drag_motion)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_button_release)
        self.tree.bind("<Button-3>", self.on_tree_right_click)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        # 添加Github信息标签
        github_label = ttk.Label(self.root, text=lang['github_label'], font=("Arial", 10))
        github_label.pack(side=tk.RIGHT)

    def sort_by_column(self, column):
        # 获取当前排序状态
        current_state = self.sorting_state.get(column, None)
        
        # 清除所有表头的箭头
        for col_id in self.COLUMNS:
            original_text = lang['columns'][col_id]
            current_text = self.tree.heading(col_id, "text")
            # 如果当前文本包含箭头，则移除
            if current_text.endswith(self.SORT_ASC) or current_text.endswith(self.SORT_DESC):
                self.tree.heading(col_id, text=original_text)
        
        # 状态循环：None(未排序) → False(升序) → True(降序) → None(未排序)
        if current_state is None:
            # 从未排序切换到升序
            new_state = False
            arrow = self.SORT_ASC
            self.sorting_state[column] = new_state
            self.tree.heading(column, text=lang['columns'][column] + arrow)
            self._sort_data(column, new_state)
        elif current_state is False:
            # 从升序切换到降序
            new_state = True
            arrow = self.SORT_DESC
            self.sorting_state[column] = new_state
            self.tree.heading(column, text=lang['columns'][column] + arrow)
            self._sort_data(column, new_state)
        else:
            # 从降序切换到未排序（恢复原始顺序）
            self.sorting_state[column] = None
            # 恢复原始数据顺序
            self.accounts_data = [acc.copy() for acc in self.original_data]
            self.filter_treeview()

    def _sort_data(self, column, reverse):
        # 实际执行排序的方法
        if column == "remarks":
            # 只按拼音首字母排序
            def key_func(acc):
                remark = acc.get("remarks", "")
                # 直接返回拼音首字母排序
                return get_pinyin_initial_abbr(remark)
        elif column == "shortcut":
            # 根据可用时间排序
            def key_func(acc):
                try:
                    dt = datetime.datetime.strptime(acc.get("available_time", ""), "%Y-%m-%d %H:%M")
                except Exception:
                    dt = datetime.datetime.min
                return dt
        elif column == "account":
            key_func = lambda acc: acc.get("account", "").lower()
        elif column == "status":
            # 可用排在前面
            def key_func(acc):
                status = acc.get("status", "")
                return 0 if status == lang['status_available'] else 1
        elif column == "available_time":
            # 按可用时间排序
            def key_func(acc):
                try:
                    # 将时间字符串转换为datetime对象进行比较
                    dt = datetime.datetime.strptime(acc.get("available_time", ""), "%Y-%m-%d %H:%M")
                except Exception:
                    # 转换失败的时间视为最小时间
                    dt = datetime.datetime.min
                return dt
        else:
            key_func = lambda acc: acc.get(column)
        
        self.accounts_data.sort(key=key_func, reverse=reverse)
        self.filter_treeview()

    def reset_sorting(self):
        # 重置所有排序状态
        # 清除所有表头的箭头
        for col_id in self.COLUMNS:
            original_text = lang['columns'][col_id]
            current_text = self.tree.heading(col_id, "text")
            if current_text.endswith(self.SORT_ASC) or current_text.endswith(self.SORT_DESC):
                self.tree.heading(col_id, text=original_text)
        
        # 重置排序状态
        self.sorting_state = {}
        # 恢复原始数据顺序
        self.accounts_data = [acc.copy() for acc in self.original_data]

    def get_account_by_tree_id(self, tree_item_id):
        return next((acc for acc in self.accounts_data if acc.get('tree_id') == tree_item_id), None)

    def _set_account_selection_state(self, account_obj, state):
        if account_obj.get('selected_state', False) != state:
            account_obj['selected_state'] = state
            if account_obj.get('tree_id'):
                if state:
                    self.tree.selection_add(account_obj['tree_id'])
                else:
                    self.tree.selection_remove(account_obj['tree_id'])
                self.update_row_checkbox_only(account_obj['tree_id'], account_obj)
        # 选中状态变化时，更新批量备注控件显示
        self.update_batch_remarks_visibility()

    def update_row_checkbox_only(self, tree_item_id, account_obj):
        select_char = "☑" if account_obj.get('selected_state', False) else "☐"
        current_values = list(self.tree.item(tree_item_id, 'values'))
        # 序号列索引为0，选择列索引为1
        current_values[1] = select_char
        self.tree.item(tree_item_id, values=current_values)

    def on_tree_button_press(self, event):
        item_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        # 重置拖拽相关状态
        self._drag_start_item = None
        self._last_selected_items_in_drag = set()
        self._selection_mode_toggle = None
        if not item_id:
            if not (event.state & 0x0004 or event.state & 0x0008):
                for acc in self.accounts_data:
                    self._set_account_selection_state(acc, False)
            return
        # 使用列索引判断第二列（“选择”列，序号列是第一列）
        if col == "#2":
            account_obj = self.get_account_by_tree_id(item_id)
            if account_obj:
                current_state = account_obj.get('selected_state', False)
                self._set_account_selection_state(account_obj, not current_state)
                self._drag_start_item = item_id
                self._selection_mode_toggle = not current_state
                self._last_selected_items_in_drag.add(item_id)
            return
        # 其它列按原有逻辑处理（例如点击“账号”或“密码”进行复制）
        header_text = self.tree.heading(col)['text']
        # 移除箭头后再比较
        if header_text.endswith(self.SORT_ASC) or header_text.endswith(self.SORT_DESC):
            header_text = header_text[:-2]
        if header_text in (lang['columns']['account'], lang['columns']['password']):
            self.root.after(150, lambda: self._handle_single_click_copy(item_id, header_text))

    def _handle_single_click_copy(self, item_id, column_header_text):
        if self._drag_start_item:
            return
        account_obj = self.get_account_by_tree_id(item_id)
        if not account_obj: return
        if column_header_text == lang['columns']['account']:
            content_to_copy = account_obj['account']
        elif column_header_text == lang['columns']['password']:
            content_to_copy = account_obj['password']
        else:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(content_to_copy)
        self.root.update()

    def on_tree_drag_motion(self, event):
        if not self._drag_start_item: return
        current_item = self.tree.identify_row(event.y)
        if not current_item: return
        all_visible_items = list(self.tree.get_children())
        if not all_visible_items: return
        try:
            start_index = all_visible_items.index(self._drag_start_item)
            current_index = all_visible_items.index(current_item)
        except ValueError:
            return
        min_index, max_index = sorted((start_index, current_index))
        items_in_current_drag_range = set(all_visible_items[min_index : max_index + 1])
        items_to_deselect_from_prev_drag = self._last_selected_items_in_drag - items_in_current_drag_range
        for prev_item_id in items_to_deselect_from_prev_drag:
            acc = self.get_account_by_tree_id(prev_item_id)
            if acc:
                self._set_account_selection_state(acc, not self._selection_mode_toggle)
        for item_id in items_in_current_drag_range:
            acc = self.get_account_by_tree_id(item_id)
            if acc:
                self._set_account_selection_state(acc, self._selection_mode_toggle)
        self._last_selected_items_in_drag = items_in_current_drag_range

    def on_tree_button_release(self, _event):
        self._drag_start_item = None
        self._last_selected_items_in_drag = set()
        self._selection_mode_toggle = None

    def on_tree_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        column_id_str = self.tree.identify_column(event.x)
        column_header_text = self.tree.heading(column_id_str)['text']
        # 移除箭头后再比较
        if column_header_text.endswith(self.SORT_ASC) or column_header_text.endswith(self.SORT_DESC):
            column_header_text = column_header_text[:-2]
        if not item_id: return
        account_obj = self.get_account_by_tree_id(item_id)
        if not account_obj: return
        if column_header_text == lang['columns']['shortcut']:
            pass

    def on_tree_right_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell": return
        column_id_str = self.tree.identify_column(event.x)
        item_id = self.tree.identify_row(event.y)
        if not item_id: return
        account_obj = self.get_account_by_tree_id(item_id)
        if not account_obj: return
        column_header_text = self.tree.heading(column_id_str)['text']
        # 移除箭头后再比较
        if column_header_text.endswith(self.SORT_ASC) or column_header_text.endswith(self.SORT_DESC):
            column_header_text = column_header_text[:-2]
        if column_header_text not in (lang['columns']['remarks'], lang['columns']['shortcut'], lang['columns']['available_time']) and not (event.state & 0x0004 or event.state & 0x0008):
            for acc in self.accounts_data:
                self._set_account_selection_state(acc, False)
            self._set_account_selection_state(account_obj, True)
        if column_header_text == lang['columns']['remarks']:
            self._show_remarks_menu(event, account_obj)
        elif column_header_text == lang['columns']['shortcut']:
            self._show_shortcut_menu(event, account_obj)
        elif column_header_text == lang['columns']['available_time']:
            self._show_available_time_menu(event, account_obj)
        elif column_header_text == lang['columns']['account']:
            self.root.clipboard_clear()
            self.root.clipboard_append(account_obj['account'])
            self.root.update()
        elif column_header_text == lang['columns']['password']:
            self.root.clipboard_clear()
            self.root.clipboard_append(account_obj['password'])
            self.root.update()

    def _show_available_time_menu(self, event, account_obj):
        # 显示修改可用时间的菜单
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=lang['modify_available_time'], command=lambda: self._modify_available_time(account_obj))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _modify_available_time(self, account_obj):
        # 修改账号的可用时间
        try:
            # 解析当前可用时间
            current_time = datetime.datetime.strptime(account_obj['available_time'], "%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            # 如果解析失败，使用当前时间
            current_time = datetime.datetime.now()
        
        # 显示日期时间对话框
        dlg = DateTimeDialog(self.root, lang['modify_available_time'], current_time)
        if dlg.result:
            # 更新可用时间
            self._update_account_status_and_time(account_obj, dlg.result)
            self.filter_treeview()
            self.save_data()

    def _show_shortcut_menu(self, event, account_obj):
        shortcut_menu = tk.Menu(self.root, tearoff=0)
        shortcut_menu.add_command(label=lang['immediately_available'], command=lambda: self.apply_shortcut(account_obj, "reset"))
        shortcut_menu.add_separator()
        shortcut_menu.add_command(label=lang['shortcut_20h'], command=lambda: self.apply_shortcut(account_obj, "delta", hours=20))
        shortcut_menu.add_command(label=lang['shortcut_3d'], command=lambda: self.apply_shortcut(account_obj, "delta", days=3))
        shortcut_menu.add_command(label=lang['shortcut_7d'], command=lambda: self.apply_shortcut(account_obj, "delta", days=7))
        shortcut_menu.add_command(label=lang['shortcut_14d'], command=lambda: self.apply_shortcut(account_obj, "delta", days=14))
        shortcut_menu.add_command(label=lang['shortcut_31d'], command=lambda: self.apply_shortcut(account_obj, "delta", days=31))
        shortcut_menu.add_command(label=lang['shortcut_45d'], command=lambda: self.apply_shortcut(account_obj, "delta", days=45))
        shortcut_menu.add_command(label=lang['shortcut_181d'], command=lambda: self.apply_shortcut(account_obj, "delta", days=181))
        shortcut_menu.add_separator()
        shortcut_menu.add_command(label=lang['custom_days_hours'], command=lambda: self._custom_shortcut(account_obj))
        try:
            shortcut_menu.tk_popup(event.x_root, event.y_root)
        finally:
            shortcut_menu.grab_release()

    def _custom_shortcut(self, account_obj):
        # 使用自定义对话框输入天数和小时
        dlg = DaysHoursDialog(self.root, title=lang['custom_days_hours'])
        if dlg.result is None:
            return
        custom_days, custom_hours = dlg.result
        if custom_days == 0 and custom_hours == 0:
            self.apply_shortcut(account_obj, "reset")
        else:
            self.apply_shortcut(account_obj, "delta", days=custom_days, hours=custom_hours)

    def _show_remarks_menu(self, event, account_obj):
        remarks_menu = tk.Menu(self.root, tearoff=0)

        remarks_menu.add_command(label=lang['remarks_options'][0], command=lambda: self.set_remarks(account_obj, ""))
        remarks_menu.add_separator()
        remarks_menu.add_command(label=lang['remarks_options'][1], command=lambda: self.set_remarks(account_obj, lang['remarks_options'][1]))
        remarks_menu.add_command(label=lang['remarks_options'][2], command=lambda: self.set_remarks(account_obj, lang['remarks_options'][2]))
        remarks_menu.add_separator()
        remarks_menu.add_command(label=lang['custom_remark'], command=lambda: self._custom_remarks(account_obj))
        try:
            remarks_menu.tk_popup(event.x_root, event.y_root)
        finally:
            remarks_menu.grab_release()

    def _custom_remarks(self, account_obj):
        # 自定义弹窗输入备注
        class CustomRemarkDialog(simpledialog.Dialog):
            def body(self, master):
                tk.Label(master, text=lang['enter_custom_remark']).pack(padx=10, pady=10)
                self.remark_var = tk.StringVar()
                self.remark_entry = tk.Entry(master, textvariable=self.remark_var, width=30, font=("Arial", 10))
                self.remark_entry.pack(padx=10, pady=5)
                return self.remark_entry

            def apply(self):
                self.result = self.remark_var.get()

            def buttonbox(self):
                box = tk.Frame(self)
                tk.Button(box, text=lang['confirm'], width=10, command=self.ok, default=tk.ACTIVE, font=("Arial", 10)).pack(side=tk.LEFT, padx=5, pady=5)
                tk.Button(box, text=lang['cancel'], width=10, command=self.cancel, font=("Arial", 10)).pack(side=tk.LEFT, padx=5, pady=5)
                self.bind("<Return>", self.ok)
                self.bind("<Escape>", self.cancel)
                box.pack()

        dlg = CustomRemarkDialog(self.root, title=lang['custom_remark'])
        if dlg.result:
            self.set_remarks(account_obj, dlg.result)

    def set_remarks(self, account_obj, remark_text):
        account_obj['remarks'] = remark_text
        # 更新原始数据中的备注信息
        for orig_acc in self.original_data:
            if orig_acc['account'] == account_obj['account']:  # 只比较账号
                orig_acc['remarks'] = remark_text
                break
        self.filter_treeview()
        self.save_data()

    def _update_account_status_and_time(self, account_obj, new_available_time_dt=None):
        if new_available_time_dt is None:
            try:
                available_dt = datetime.datetime.strptime(account_obj['available_time'], "%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                available_dt = datetime.datetime.min
        else:
            available_dt = new_available_time_dt
        account_obj['available_time'] = available_dt.strftime("%Y-%m-%d %H:%M")
        account_obj['status'] = lang['status_available'] if available_dt <= datetime.datetime.now() else lang['status_unavailable']
        
        # 更新原始数据中的时间和状态
        for orig_acc in self.original_data:
            if orig_acc['account'] == account_obj['account']:  # 只比较账号
                orig_acc['available_time'] = account_obj['available_time']
                orig_acc['status'] = account_obj['status']
                break

    def apply_shortcut(self, account_obj, action_type, hours=0, days=0):
        now = datetime.datetime.now()
        new_available_time_dt = None
        if action_type == "reset":
            new_available_time_dt = now
        elif action_type == "delta":
            new_available_time_dt = now + datetime.timedelta(days=days, hours=hours)
        if new_available_time_dt:
            self._update_account_status_and_time(account_obj, new_available_time_dt)
            # 快捷操作后保持当前排序状态
            self.filter_treeview()
            self.save_data()

    def update_row_in_treeview(self, tree_item_id, account_obj):
        select_char = "☑" if account_obj.get('selected_state', False) else "☐"
        self._update_account_status_and_time(account_obj)
        status_tag = account_obj['status']
        account_obj.setdefault('remarks', '')
        display_shortcut = ""
        try:
            available_dt = datetime.datetime.strptime(account_obj['available_time'], "%Y-%m-%d %H:%M")
            now = datetime.datetime.now()
            if available_dt > now:
                time_left = available_dt - now
                days = time_left.days
                seconds_in_hour = 3600
                hours = time_left.seconds // seconds_in_hour
                
                # 根据语言和数量选择正确的单复数形式
                day_unit = lang['day'] if days == 1 else lang['days']
                hour_unit = lang['hour'] if hours == 1 else lang['hours']
                
                if days > 0:
                    if hours > 0:
                        display_shortcut = f"{days} {day_unit} {hours} {hour_unit}"
                    else:
                        display_shortcut = f"{days} {day_unit}"
                elif hours > 0:
                    display_shortcut = f"{hours} {hour_unit}"
                else:
                    display_shortcut = lang['less_than_one_hour']
        except (ValueError, TypeError):
            display_shortcut = ""
            
        # 找到当前项的索引
        index = 1  # 默认序号为1
        for i, item in enumerate(self.tree.get_children()):
            if item == tree_item_id:
                index = i + 1  # 序号从1开始
                break
                
        self.tree.item(tree_item_id, values=(
            index,  # 序号
            select_char,
            account_obj['account'],
            account_obj['password'],
            account_obj['status'],
            account_obj['available_time'],
            account_obj['remarks'],
            display_shortcut
        ), tags=(status_tag,))

    def populate_treeview(self, data_to_display=None):
        for item in self.tree.get_children():
            self.tree.delete(item)
        source_data = data_to_display if data_to_display is not None else self.accounts_data
        items_to_reselect_in_ui = []
        for index, acc_data in enumerate(source_data, 1):  # 从1开始计数
            self._update_account_status_and_time(acc_data)
            select_char = "☑" if acc_data.get('selected_state', False) else "☐"
            status_tag = acc_data['status']
            acc_data.setdefault('remarks', '')
            display_shortcut = ""
            try:
                available_dt = datetime.datetime.strptime(acc_data['available_time'], "%Y-%m-%d %H:%M")
                now = datetime.datetime.now()
                if available_dt > now:
                    time_left = available_dt - now
                    days = time_left.days
                    seconds_in_hour = 3600
                    hours = time_left.seconds // seconds_in_hour
                    
                    # 根据语言和数量选择正确的单复数形式
                    day_unit = lang['day'] if days == 1 else lang['days']
                    hour_unit = lang['hour'] if hours == 1 else lang['hours']
                    
                    if days > 0:
                        if hours > 0:
                            display_shortcut = f"{days} {day_unit} {hours} {hour_unit}"
                        else:
                            display_shortcut = f"{days} {day_unit}"
                    elif hours > 0:
                        display_shortcut = f"{hours} {hour_unit}"
                    else:
                        display_shortcut = lang['less_than_one_hour']
            except (ValueError, TypeError):
                display_shortcut = ""
            tree_item_id = self.tree.insert("", tk.END, values=(
                index,  # 序号
                select_char,
                acc_data['account'],
                acc_data['password'],
                acc_data['status'],
                acc_data['available_time'],
                acc_data['remarks'],
                display_shortcut
            ), tags=(status_tag,))
            acc_data['tree_id'] = tree_item_id
            if acc_data.get('selected_state', False):
                items_to_reselect_in_ui.append(tree_item_id)
        self.tree.selection_set(*items_to_reselect_in_ui)

    def update_batch_remarks_visibility(self):
        selected_accounts = [acc for acc in self.accounts_data if acc.get('selected_state', False)]
        if selected_accounts:
            self.batch_remarks_combo.pack(side=tk.RIGHT, padx=5)
            self.batch_remarks_btn.pack(side=tk.RIGHT, padx=5)
            self.delete_btn.pack(side=tk.RIGHT, padx=5)
        else:
            self.batch_remarks_combo.pack_forget()
            self.batch_remarks_btn.pack_forget()
            self.delete_btn.pack_forget()
        # 更新"选择"列的表头，显示选中的数量
        count = len(selected_accounts)
        header_text = f"{lang['columns']['select']}:{count}" if count > 0 else lang['columns']['select']
        self.tree.heading("select", text=header_text)

    def filter_treeview(self):
        show_available = self.show_available_only_var.get()
        show_remarked = getattr(self, "show_remarked_only_var", None)
        show_remarked = show_remarked.get() if show_remarked else False
        search_text = self.search_var.get().strip().lower() if hasattr(self, "search_var") else ""
        filtered_data = []
        for acc in self.accounts_data:
            self._update_account_status_and_time(acc)
            match_status = (not show_available or (show_available and acc['status'] == lang['status_available']))
            match_remark = (not show_remarked or (show_remarked and acc.get('remarks', '').strip()))
        
            # 修改搜索匹配逻辑：同时检查账号、密码和备注
            if search_text:
                account_match = search_text in acc.get('account', '').lower()
                password_match = search_text in acc.get('password', '').lower()
                remark_match = search_text in acc.get('remarks', '').lower()
                match_search = account_match or password_match or remark_match
            else:
                match_search = True  # 无搜索内容时全部匹配
            
            if match_status and match_remark and match_search:
                filtered_data.append(acc)
        self.populate_treeview(filtered_data)
        self.update_batch_remarks_visibility()

    def sort_by_remarks(self):
        self.remarks_sort_reverse = not getattr(self, "remarks_sort_reverse", False)
        remarks_order = {
            "": 0, 
            lang['remarks_options'][1]: 1, 
            lang['remarks_options'][2]: 2
        }
        self.accounts_data.sort(
            key=lambda acc: remarks_order.get(acc.get("remarks", ""), 0),
            reverse=self.remarks_sort_reverse
        )
        self.filter_treeview()

    def _add_new_account_entry(self, account, password):
        # 只检查账号是否已存在，不考虑密码
        if not any(acc['account'] == account for acc in self.accounts_data):
            default_available_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            new_acc = {
                'account': account,
                'password': password,
                'available_time': default_available_time,
                'remarks': '',
                'selected_state': False
            }
            self.accounts_data.append(new_acc)
            self.original_data.append(new_acc.copy())  # 添加到原始数据
            return True
        return False

    def import_txt(self):
        filepath = filedialog.askopenfilename(
            title=lang['import_txt'],
            filetypes=(("Text files", "*.txt"), ("All files", "*.*")),
            parent=self.root
        )
        if not filepath: return
        try:
            new_accounts_count = 0
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if "----" in line:
                        parts = line.split("----")
                        if len(parts) >= 2:
                            account = parts[0].strip()
                            password = parts[1].strip()
                            if account and password:
                                if self._add_new_account_entry(account, password):
                                    new_accounts_count += 1
            if new_accounts_count > 0:
                messagebox.showinfo(lang['import_success'], lang['imported_new_accounts'].format(count=new_accounts_count), parent=self.root)
                self.filter_treeview()
                self.save_data()
            else:
                messagebox.showinfo(lang['import_txt'], lang['import_no_new'], parent=self.root)
                self.filter_treeview()
        except Exception as e:
            messagebox.showerror(lang['import_error'], lang['import_failed'].format(error=e), parent=self.root)

    def manual_add_account_dialog(self):
        dialog = ManualAddAccountDialog(self.root)
        if dialog.new_accounts_data:
            new_accounts_count = 0
            for acc_info in dialog.new_accounts_data:
                account, password = acc_info
                if self._add_new_account_entry(account, password):
                    new_accounts_count += 1
            if new_accounts_count > 0:
                messagebox.showinfo(lang['add_success'], lang['added_new_accounts'].format(count=new_accounts_count), parent=self.root)
                self.save_data()
            elif dialog.new_accounts_data:
                messagebox.showinfo(lang['manual_add'], lang['add_no_new'], parent=self.root)
            self.filter_treeview()

    def save_data(self):
        data_to_save = []
        for acc in self.original_data:  # 保存原始数据
            acc_copy = acc.copy()
            acc_copy.pop('tree_id', None)
            acc_copy.pop('selected_state', None)
            acc_copy.pop('status', None)
            # 判断备注内容
            if acc_copy['remarks'] in self.REMARKS_TO_JSON:
                acc_copy['remarks'] = self.REMARKS_TO_JSON[acc_copy['remarks']]
            else:
                acc_copy['remarks'] = acc_copy['remarks']  # 其它内容直接存字符串
            data_to_save.append(acc_copy)
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        except Exception as e:
            messagebox.showerror(lang['save_failed'], lang['save_error'].format(error=e), parent=self.root)

    def load_data(self):
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                loaded_entries = json.load(f)
                self.accounts_data = []
                self.original_data = []  # 重置原始数据
                for entry in loaded_entries:
                    entry.setdefault('selected_state', False)
                    entry.setdefault('available_time', datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
                    # 兼容数字和字符串
                    if isinstance(entry.get('remarks', ""), int):
                        entry['remarks'] = self.REMARKS_FROM_JSON.get(entry.get('remarks', 0), '')
                    else:
                        entry['remarks'] = entry.get('remarks', '')
                    entry.pop('id', None)
                    entry.pop('shortcut', None)
                    entry.pop('delay_days', None)
                    entry.pop('delay_hours', None)
                    entry.pop('status', None)
                    self.accounts_data.append(entry.copy())
                    self.original_data.append(entry.copy())  # 同时添加到原始数据
        except FileNotFoundError:
            self.accounts_data = []
            self.original_data = []
        except Exception as e:
            messagebox.showerror(lang['load_error'], lang['load_failed'].format(error=e), parent=self.root)
            self.accounts_data = []
            self.original_data = []
        self.filter_treeview()

    def refresh_treeview(self):
        # 刷新时重置排序状态
        self.reset_sorting()
        self.load_data()
        self.filter_treeview()

    def select_all_toggle(self):
        visible_item_ids = self.tree.get_children()
        if not visible_item_ids: return
        visible_accounts = [self.get_account_by_tree_id(item_id) for item_id in visible_item_ids if self.get_account_by_tree_id(item_id)]
        if not visible_accounts: return
        all_currently_selected = all(acc.get('selected_state', False) for acc in visible_accounts)
        new_state = not all_currently_selected
        for acc_obj in visible_accounts:
            self._set_account_selection_state(acc_obj, new_state)
        # 选中状态变化时，更新批量备注控件显示
        self.update_batch_remarks_visibility()

    def delete_selected(self):
        selected_accounts_to_delete = [
            acc['account'] for acc in self.accounts_data if acc.get('selected_state', False)
        ]
        if not selected_accounts_to_delete:
            messagebox.showinfo(lang['delete_no_selected'], lang['delete_no_accounts'], parent=self.root)
            return
        if messagebox.askyesno(lang['confirm_delete'], lang['confirm_delete_msg'].format(count=len(selected_accounts_to_delete)), parent=self.root):
            # 从当前数据和原始数据中都删除
            self.accounts_data = [
                acc for acc in self.accounts_data
                if acc['account'] not in selected_accounts_to_delete
            ]
            self.original_data = [
                acc for acc in self.original_data
                if acc['account'] not in selected_accounts_to_delete
            ]
            self.filter_treeview()
            self.save_data()
            messagebox.showinfo(lang['delete_success'], lang['deleted_accounts'].format(count=len(selected_accounts_to_delete)), parent=self.root)

    def export_txt(self):
        selected_accounts = [
            acc for acc in self.accounts_data if acc.get('selected_state', False)
        ]
        if not selected_accounts:
            messagebox.showinfo(lang['export_no_selected'], lang['export_no_accounts'], parent=self.root)
            return
        
        filepath = filedialog.asksaveasfilename(
            title=lang['export_selected'],
            defaultextension=".txt",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*")),
            parent=self.root
        )
        if not filepath:
            return
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                for acc in selected_accounts:
                    line = f"{acc['account']}----{acc['password']}\n"
                    f.write(line)
            messagebox.showinfo(lang['export_success'], lang['exported_accounts'].format(count=len(selected_accounts), path=filepath), parent=self.root)
        except Exception as e:
            messagebox.showerror(lang['export_error'], lang['export_failed'].format(error=e), parent=self.root)

    def batch_set_remarks(self):
        selected_accounts = [
            acc for acc in self.accounts_data if acc.get('selected_state', False)
        ]
        if not selected_accounts:
            return
            
        remark_text = self.batch_remarks_var.get()
        if remark_text == lang['remarks_options'][0]:
            remark_text = ""
            
        for acc in selected_accounts:
            self.set_remarks(acc, remark_text)
        
        self.batch_remarks_var.set("")
        messagebox.showinfo(lang['batch_remark_success'], lang['batch_remark_msg'].format(count=len(selected_accounts), remark=remark_text), parent=self.root)

if __name__ == '__main__':
    root = tk.Tk()
    app = AccountManagerApp(root)
    root.after(1000, check_for_update)  # 启动后延迟1秒检查更新
    root.mainloop()