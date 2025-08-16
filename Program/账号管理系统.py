import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import datetime
import json
import subprocess

from dialogs import DaysHoursDialog, DateTimeDialog, AddAccountDialog, CustomRemarkDialog
from language import LANGUAGES
from utils import get_system_language, check_for_update, get_pinyin_initial_abbr

version = "1.8.1"

current_lang = get_system_language()
lang = LANGUAGES[current_lang]

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
        # 配置空白行样式
        self.tree.tag_configure('blank', background='#f0f0f0')

    def setup_ui(self):
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)
        buttons_data = [
            (lang['add_accounts'], self.add_account_dialog),
            (lang['export_selected'], self.export_txt),
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
        # 当排序的列不是"remarks"时，清除备注列的排序状态
        if column != "remarks":
            if "remarks" in self.sorting_state:
                del self.sorting_state["remarks"]
                # 同时清除备注列表头的箭头
                self.tree.heading("remarks", text=lang['columns']["remarks"])
        
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
        # 忽略空白行
        if not tree_item_id:
            return None
        # 检查当前行是否为空白行（通过values判断）
        values = self.tree.item(tree_item_id, 'values')
        if all(v == "" for v in values):
            return None
        # 原有逻辑
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
        
        # 忽略空白行交互
        if item_id:
            values = self.tree.item(item_id, 'values')
            if all(v == "" for v in values):
                return  # 空白行不响应点击
        
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
        
        # 忽略空白行
        values = self.tree.item(current_item, 'values')
        if all(v == "" for v in values):
            return
            
        all_visible_items = []
        for item in self.tree.get_children():
            # 过滤空白行
            item_values = self.tree.item(item, 'values')
            if not all(v == "" for v in item_values):
                all_visible_items.append(item)
                
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
        
        # 忽略空白行
        values = self.tree.item(item_id, 'values')
        if all(v == "" for v in values):
            return
            
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
        
        # 忽略空白行
        values = self.tree.item(item_id, 'values')
        if all(v == "" for v in values):
            return
            
        account_obj = self.get_account_by_tree_id(item_id)
        if not account_obj: return
        column_header_text = self.tree.heading(column_id_str)['text']
        
        # 正确移除排序箭头（只在有箭头时处理）
        if column_header_text.endswith(self.SORT_ASC):
            column_header_text = column_header_text[:-len(self.SORT_ASC)]
        elif column_header_text.endswith(self.SORT_DESC):
            column_header_text = column_header_text[:-len(self.SORT_DESC)]
        
        # 处理选择状态
        if column_header_text not in (lang['columns']['remarks'], lang['columns']['shortcut'], lang['columns']['available_time']) and not (event.state & 0x0004 or event.state & 0x0008):
            for acc in self.accounts_data:
                self._set_account_selection_state(acc, False)
            self._set_account_selection_state(account_obj, True)
        
        # 创建右键菜单
        menu = tk.Menu(self.root, tearoff=0)

        if column_header_text == lang['columns']['account']:
            menu.add_command(
                label=lang['login_account'], 
                command=lambda: self.login_account(account_obj)
            )
        
        # 根据点击的列添加相应选项
        if column_header_text == lang['columns']['remarks']:
            self._add_remarks_menu_items(menu, account_obj)
        elif column_header_text == lang['columns']['shortcut']:
            self._add_shortcut_menu_items(menu, account_obj)
        elif column_header_text == lang['columns']['available_time']:
            self._add_available_time_menu_items(menu, account_obj)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def login_account(self, account_obj):
        """使用指定账号和密码启动Steam"""
        steam_path = r"C:\Program Files (x86)\Steam\steam.exe"
        account = account_obj['account']
        password = account_obj['password']

        try:
            subprocess.Popen([
                steam_path,
                "-login",
                account,
                password
            ])
        except Exception as e:
            messagebox.showerror(
                "启动失败",
                f"无法启动Steam或执行登录命令：\n{str(e)}"
            )

    # 新增：辅助方法，复制内容到剪贴板
    def copy_to_clipboard(self, content):
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.root.update()

    # 重构：将各列的菜单选项拆分为单独的方法
    def _add_available_time_menu_items(self, menu, account_obj):
        menu.add_command(
            label=lang['modify_available_time'], 
            command=lambda: self._modify_available_time(account_obj)
        )

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

    def _add_shortcut_menu_items(self, menu, account_obj):
        menu.add_command(
            label=lang['immediately_available'], 
            command=lambda: self.apply_shortcut(account_obj, "reset")
        )
        menu.add_separator()
        menu.add_command(
            label=lang['shortcut_20h'], 
            command=lambda: self.apply_shortcut(account_obj, "delta", hours=20)
        )
        menu.add_command(
            label=lang['shortcut_3d'], 
            command=lambda: self.apply_shortcut(account_obj, "delta", days=3)
        )
        menu.add_command(
            label=lang['shortcut_7d'], 
            command=lambda: self.apply_shortcut(account_obj, "delta", days=7)
        )
        menu.add_command(
            label=lang['shortcut_14d'], 
            command=lambda: self.apply_shortcut(account_obj, "delta", days=14)
        )
        menu.add_command(
            label=lang['shortcut_31d'], 
            command=lambda: self.apply_shortcut(account_obj, "delta", days=31)
        )
        menu.add_command(
            label=lang['shortcut_45d'], 
            command=lambda: self.apply_shortcut(account_obj, "delta", days=45)
        )
        menu.add_command(
            label=lang['shortcut_181d'], 
            command=lambda: self.apply_shortcut(account_obj, "delta", days=181)
        )
        menu.add_separator()
        menu.add_command(
            label=lang['custom_days_hours'], 
            command=lambda: self._custom_shortcut(account_obj)
        )

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

    def _add_remarks_menu_items(self, menu, account_obj):
        menu.add_command(
            label=lang['remarks_options'][0], 
            command=lambda: self.set_remarks(account_obj, "")
        )
        menu.add_separator()
        menu.add_command(
            label=lang['remarks_options'][1], 
            command=lambda: self.set_remarks(account_obj, lang['remarks_options'][1])
        )
        menu.add_command(
            label=lang['remarks_options'][2], 
            command=lambda: self.set_remarks(account_obj, lang['remarks_options'][2])
        )
        menu.add_separator()
        menu.add_command(
            label=lang['custom_remark'], 
            command=lambda: self._custom_remarks(account_obj)
        )

    def _custom_remarks(self, account_obj):
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
        visible_items = []
        for item in self.tree.get_children():
            item_values = self.tree.item(item, 'values')
            if not all(v == "" for v in item_values):  # 排除空白行
                visible_items.append(item)
        
        for i, item in enumerate(visible_items):
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
        # 清空现有内容
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        source_data = data_to_display if data_to_display is not None else self.accounts_data
        items_to_reselect_in_ui = []
        
        # 检查是否仅对"备注"列进行排序
        is_sorting_by_remarks = self.sorting_state.get("remarks", None) is not None
        
        # 生成包含空白行的展示数据（仅在按备注排序时）
        display_data = []
        if is_sorting_by_remarks:
            prev_remark = None
            for acc_data in source_data:
                # 对比当前备注与上一条，不同则插入空白行
                current_remark = acc_data.get('remarks', '')
                if prev_remark is not None and current_remark != prev_remark:
                    display_data.append({'is_blank': True})
                display_data.append(acc_data)
                prev_remark = current_remark
        else:
            # 未按备注排序或未排序，直接使用原始数据
            display_data = source_data
        
        # 填充Treeview
        real_index = 1  # 实际数据序号（跳过空白行）
        for item_data in display_data:
            if is_sorting_by_remarks and item_data.get('is_blank', False):
                # 仅在按备注排序时插入空白行
                self.tree.insert("", tk.END, values=("", "", "", "", "", "", "", ""), tags=('blank',))
                continue
            
            # 处理实际数据行
            acc_data = item_data
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
                    
                    day_unit = lang['day'] if days == 1 else lang['days']
                    hour_unit = lang['hour'] if hours == 1 else lang['hours']
                    
                    if days > 0:
                        display_shortcut = f"{days} {day_unit} {hours} {hour_unit}" if hours > 0 else f"{days} {day_unit}"
                    elif hours > 0:
                        display_shortcut = f"{hours} {hour_unit}"
                    else:
                        display_shortcut = lang['less_than_one_hour']
            except (ValueError, TypeError):
                display_shortcut = ""
            
            # 插入实际数据行（使用连续序号）
            tree_item_id = self.tree.insert("", tk.END, values=(
                real_index,  # 序号保持连续（跳过空白行）
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
            
            real_index += 1  # 只对实际数据行递增序号
        
        # 恢复选中状态
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
        # 检查密码中是否包含"----"，如果有则移除其及后面的字符
        if "----" in password:
            password = password.split("----")[0].strip()  # 分割后取前面部分并去除首尾空格
    
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

    def add_account_dialog(self):
        dialog = AddAccountDialog(
            self.root,
            title=lang['add_accounts'],
            import_txt_callback=self.import_txt
        )
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
        visible_items = []
        for item in self.tree.get_children():
            item_values = self.tree.item(item, 'values')
            if not all(v == "" for v in item_values):  # 排除空白行
                visible_items.append(item)
                
        visible_accounts = [self.get_account_by_tree_id(item_id) for item_id in visible_items if self.get_account_by_tree_id(item_id)]
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
        # 检查是否有选中的账号
        selected_items = [item for item in self.tree.selection() if item != ""]
        if not selected_items:
            messagebox.showinfo(lang['export_no_selected'], lang['export_no_accounts'])
            return

        # 显示导出方式选择对话框
        from dialogs import ExportMethodDialog  # 导入对话框类
        dialog = ExportMethodDialog(self.root)
        export_method = dialog.result

        if not export_method:  # 用户取消选择
            return

        # 收集选中账号的数据
        selected_accounts = []
        for item in selected_items:
            values = self.tree.item(item, "values")
            account = values[self.COLUMNS.index("account")]
            password = values[self.COLUMNS.index("password")]
            selected_accounts.append(f"{account}----{password}")

        # 根据选择的导出方式执行操作
        if export_method == "txt":
            # TXT文件导出逻辑
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[(lang['txt_file'], "*.txt"), ("All Files", "*.*")]
            )
            if not file_path:
                return

            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(selected_accounts))
                messagebox.showinfo(
                    lang['export_success'],
                    lang['exported_accounts'].format(count=len(selected_accounts), path=file_path)
                )
            except Exception as e:
                messagebox.showerror(
                    lang['export_error'],
                    lang['export_failed'].format(error=str(e))
                )

        elif export_method == "clipboard":
            # 剪贴板导出逻辑
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append("\n".join(selected_accounts))
                self.root.update()  # 确保剪贴板内容被更新
                messagebox.showinfo(
                    lang['export_success'],
                    lang['exported_accounts'].format(count=len(selected_accounts), path=lang['clipboard'])
                )
            except Exception as e:
                messagebox.showerror(
                    lang['export_error'],
                    lang['export_failed'].format(error=str(e))
                )

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
    check_for_update(root, root.title(), lang, version)
    root.mainloop()