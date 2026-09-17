import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import datetime
import html as html_lib
import json
import subprocess
import winreg
import os
import threading
import queue
import asyncio
import re

import pytz
from pysteamauth.auth import Steam

from dialogs import (DaysHoursDialog, DateTimeDialog, AddAccountDialog, CustomRemarkDialog,
                     ExportMethodDialog, ProfileEditDialog)
from language import LANGUAGES
from utils import get_system_language, check_for_update, get_pinyin_initial_abbr

version = "2.3.8"

current_lang = get_system_language()
lang = LANGUAGES[current_lang]

class AccountManagerApp:
    COLUMNS = ("index", "select", "account", "password", "status", "remarks", "shortcut", "available_time", "others")
    COLUMN_WIDTHS = {
        "index": 10, "select": 10, "account": 50, "password": 50, "status": 10,
        "remarks": 50, "shortcut": 100, "available_time": 65, "others": 100
    }
    COLUMN_ANCHORS = {
        "index": tk.CENTER, "select": tk.CENTER, "status": tk.CENTER, "remarks": tk.CENTER,
        "shortcut": tk.CENTER, "available_time": tk.CENTER, "others": tk.CENTER
    }
    REMARKS_TO_JSON = {"": 0}
    REMARKS_FROM_JSON = {0: ""}
    # 排序箭头常量
    SORT_ASC = " ↑"  # 升序箭头
    SORT_DESC = " ↓" # 降序箭头

    def __init__(self, root_window):
        self.root = root_window
        self.root.title(lang['app_title'].format(version=version))
        self._retry_title_suffix = lang['retrying']
        self.accounts_data = []
        self.original_data = []  # 保存原始数据用于恢复未排序状态
        self.data_file = "accounts_data.json"
        self._drag_start_item = None
        self._last_selected_items_in_drag = set()
        self._selection_mode_toggle = None
        self._auto_scroll_timer_job = None  # 自动滚动检测定时器
        self.remarks_sort_reverse = False
        self.sorting_state = {}  # 存放各列排序状态：None=未排序, False=升序, True=降序
        self.show_hidden_var = tk.BooleanVar(value=False)
        self._task_queue = queue.Queue()  # 后台任务队列
        self._processing = False  # 是否正在处理任务
        self._data_loaded = False  # 数据是否已加载完成
        self.setup_ui()
        self._configure_treeview_style()
        self.steam_path = self.get_steam_install_path()
        # 使用 after 在主循环启动后异步加载数据，避免 RuntimeError
        self.root.after(0, self._load_data_async)

        if self.steam_path:
            print(f"Steam安装路径: {self.steam_path}")
        else:
            print("未检测到Steam安装路径")
        # 启动后台任务处理器
        self._process_task_queue()

    def _queue_task(self, task_func, *args, **kwargs):
        """将任务添加到后台队列"""
        self._task_queue.put((task_func, args, kwargs))

    def _append_retry_title_suffix(self, window):
        current_title = window.title()
        if self._retry_title_suffix not in current_title:
            new_title = current_title + self._retry_title_suffix
            window.title(new_title)
            window.update_idletasks()

    def _remove_retry_title_suffix(self, window):
        current_title = window.title()
        if current_title.endswith(self._retry_title_suffix):
            new_title = current_title[:-len(self._retry_title_suffix)]
            window.title(new_title)
            window.update_idletasks()

    def _process_task_queue(self):
        """处理后台任务队列（在主线程中用after调用）"""
        if self._processing:
            self.root.after(50, self._process_task_queue)
            return
        try:
            task_func, args, kwargs = self._task_queue.get_nowait()
            self._processing = True
            # 执行任务
            result = task_func(*args, **kwargs)
            # 任务完成后用after更新UI
            self.root.after(10, lambda: self._on_task_complete(result))
        except queue.Empty:
            pass
        # 继续监听队列
        self.root.after(50, self._process_task_queue)

    def _on_task_complete(self, result):
        """任务完成后的回调（更新UI）"""
        self._processing = False
        if result and isinstance(result, dict):
            if result.get('type') == 'import':
                self.filter_treeview()
                self.save_data()
                messagebox.showinfo(lang['import_success'], lang['imported_new_accounts'].format(count=result.get('count', 0)), parent=self.root)
            elif result.get('type') == 'save':
                # 保存完成，不做额外操作
                pass

    def get_steam_install_path(self):
        """从Windows注册表获取Steam安装路径"""
        possible_paths = [
            # Steam客户端通常的注册表路径
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Wow6432Node\Valve\Steam", "InstallPath"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Valve\Steam", "InstallPath")
        ]
    
        for hive, subkey, value_name in possible_paths:
            try:
                # 打开注册表项
                key = winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ)
                # 读取安装路径
                install_path, _ = winreg.QueryValueEx(key, value_name)
                winreg.CloseKey(key)
            
                # 验证路径是否存在（检查steam.exe是否存在）
                if os.path.exists(os.path.join(install_path, "steam.exe")):
                    return install_path
            except (FileNotFoundError, OSError):
                continue  # 尝试下一个可能的路径
    
        return None  # 未找到Steam安装路径

    def _configure_treeview_style(self):
        style = ttk.Style()
        style.map('Treeview',
              background=[('selected', "lightgreen")],
              foreground=[('selected', 'black')])
        self.tree.tag_configure(lang['status_available'], background="#e0e0e0", foreground="black")
        self.tree.tag_configure(lang['status_unavailable'], background="salmon")
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
        
        # 添加显示隐藏复选框
        ttk.Checkbutton(search_frame, text=lang['show_hidden'], variable=self.show_hidden_var, command=self.filter_treeview).pack(side=tk.LEFT, padx=5)
        
        # 删除按钮、修改资料按钮和查询VAC按钮先不显示
        self.delete_btn = ttk.Button(search_frame, text=lang['delete_selected'], command=self.delete_selected)
        self.edit_profile_btn = ttk.Button(search_frame, text=lang['edit_profile'], command=self.edit_profile_selected)
        self.vac_btn = ttk.Button(search_frame, text=lang['check_cooldown_selected'], command=self.check_cooldown_selected)
        ttk.Button(search_frame, text=lang['select_all_toggle'], command=self.select_all_toggle).pack(side=tk.RIGHT, padx=5)
        # 默认不显示删除按钮、修改资料按钮和VAC按钮
        self.delete_btn.pack_forget()
        self.edit_profile_btn.pack_forget()
        self.vac_btn.pack_forget()

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

        # 批量移动下拉栏和按钮（默认隐藏，只读模式）
        self.batch_move_var = tk.StringVar()
        self.batch_move_combo = ttk.Combobox(
            search_frame, textvariable=self.batch_move_var, state="readonly", width=8
        )
        self.batch_move_combo['values'] = lang['move_options']
        self.batch_move_combo.set(lang['move_default'])
        self.batch_move_btn = ttk.Button(search_frame, text=lang['batch_move'], command=self.batch_move_selected)
        self.batch_move_combo.pack_forget()
        self.batch_move_btn.pack_forget()
        
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
        # 添加冷却结束时间列的排序功能
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
        # 在root窗口上绑定鼠标移动事件，用于拖动选择时检测窗口外的鼠标位置
        self.root.bind("<B1-Motion>", self.on_root_drag_motion)
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
            # 根据冷却结束时间排序，VAC封禁排最后
            def key_func(acc):
                at = acc.get("available_time", "")
                if at == "VAC":
                    return datetime.datetime.max
                try:
                    dt = datetime.datetime.strptime(at, "%Y-%m-%d %H:%M")
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
            # 按冷却结束时间排序，VAC封禁排最后
            def key_func(acc):
                at = acc.get("available_time", "")
                if at == "VAC":
                    return datetime.datetime.max
                try:
                    dt = datetime.datetime.strptime(at, "%Y-%m-%d %H:%M")
                except Exception:
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
        # 使用列索引判断第二列（"选择"列，序号列是第一列）
        if col == "#2":
            account_obj = self.get_account_by_tree_id(item_id)
            if account_obj:
                current_state = account_obj.get('selected_state', False)
                self._set_account_selection_state(account_obj, not current_state)
                self._drag_start_item = item_id
                self._selection_mode_toggle = not current_state
                self._last_selected_items_in_drag.add(item_id)
                # 启动自动滚动检测定时器
                self._start_auto_scroll_timer()
            return
        # 其它列按原有逻辑处理（例如点击"账号"或"密码"进行复制）
        header_text = self.tree.heading(col)['text']
        # 移除箭头后再比较
        if header_text.endswith(self.SORT_ASC) or header_text.endswith(self.SORT_DESC):
            header_text = header_text[:-2]
        # 只在左键点击时复制（右键用于登录菜单）
        if event.num == 1 and header_text in (lang['columns']['account'], lang['columns']['password'], lang['columns']['others']):
            self.root.after(150, lambda: self._handle_single_click_copy(item_id, header_text))

    def _handle_single_click_copy(self, item_id, column_header_text):
        if self._drag_start_item: return
        account_obj = self.get_account_by_tree_id(item_id)
        if not account_obj: return
        if column_header_text == lang['columns']['account']:
            content_to_copy = account_obj['account']
        elif column_header_text == lang['columns']['password']:
            content_to_copy = account_obj['password']
        elif column_header_text == lang['columns']['others']:  # 添加others列复制支持
            content_to_copy = account_obj.get('others', '')
        else: return
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


    def _start_auto_scroll_timer(self):
        """启动自动滚动检测定时器"""
        if self._drag_start_item and not self._auto_scroll_timer_job:
            self._auto_scroll_timer_job = self.root.after(50, self._check_mouse_position_for_scroll)

    def _check_mouse_position_for_scroll(self):
        """定时检测鼠标位置并执行自动滚动"""
        if not self._drag_start_item:
            self._auto_scroll_timer_job = None
            return
        
        # 获取鼠标当前位置
        mouse_y = self.root.winfo_pointery()
        
        # tree的y坐标范围
        tree_y = self.tree.winfo_rooty()
        tree_bottom = tree_y + self.tree.winfo_height()
        
        should_continue = False
        if mouse_y > tree_bottom:
            # 鼠标在窗口下方，向下滚动
            distance = mouse_y - tree_bottom
            scroll_amount = 1 + int(distance * 0.04)
            scroll_amount = min(scroll_amount, 4)
            self.tree.yview_scroll(scroll_amount, "units")
            should_continue = True
        elif mouse_y < tree_y:
            # 鼠标在窗口上方，向上滚动
            distance = tree_y - mouse_y
            scroll_amount = 1 + int(distance * 0.04)
            scroll_amount = min(scroll_amount, 4)
            self.tree.yview_scroll(-scroll_amount, "units")
            should_continue = True
        
        if should_continue:
            # 继续定时检测
            self._auto_scroll_timer_job = self.root.after(50, self._check_mouse_position_for_scroll)
        else:
            # 鼠标回到窗口内，停止本次定时
            self._auto_scroll_timer_job = None

    def on_root_drag_motion(self, event):
        """root窗口上的拖动移动事件，用于检测鼠标在窗口外时的位置"""
        if self._drag_start_item and not self._auto_scroll_timer_job:
            # 如果正在拖动但没有定时器在运行，启动检测
            self._start_auto_scroll_timer()

    def on_tree_button_release(self, event):
        self._drag_start_item = None
        self._last_selected_items_in_drag = set()
        self._selection_mode_toggle = None
        # 停止自动滚动定时器
        if self._auto_scroll_timer_job:
            self.root.after_cancel(self._auto_scroll_timer_job)
            self._auto_scroll_timer_job = None

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

        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "cs2.exe"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            print("CS2 已成功关闭")
        except:
            print("CS2 未运行")

        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "steam.exe"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            print("Steam 已成功关闭")
        except:
            print("Steam 未运行")

        # 使用检测到的路径，如果未检测到则使用默认路径
        steam_path = self.steam_path
        # 确保路径指向steam.exe
        if not steam_path.endswith("steam.exe"):
            steam_path = os.path.join(steam_path, "steam.exe")
        
        account = account_obj['account']
        password = account_obj['password']

        try:
            subprocess.Popen([steam_path, "-login", account, password ,"-RememberPassword"],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception as e:
            print(f"{e.stderr}")

    # 新增：辅助方法，复制内容到剪贴板
    def copy_to_clipboard(self, content):
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.root.update()

    # 重构：将各列的菜单选项拆分为单独的方法
    def _add_available_time_menu_items(self, menu, account_obj):
        # VAC封禁时不显示修改冷却结束时间选项
        if account_obj.get('available_time') == "VAC":
            return
        menu.add_command(
            label=lang['modify_available_time'],
            command=lambda acc=account_obj: self._modify_available_time(acc)
        )

    def _modify_available_time(self, account_obj):
        # VAC封禁时不允许修改
        if account_obj.get('available_time') == "VAC":
            return
        # 修改账号的冷却结束时间
        try:
            # 解析当前冷却结束时间
            current_time = datetime.datetime.strptime(account_obj['available_time'], "%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            # 如果解析失败，使用当前时间
            current_time = datetime.datetime.now()

        # 显示日期时间对话框
        dlg = DateTimeDialog(self.root, lang['modify_available_time'], current_time)
        if dlg.result:
            # 更新冷却结束时间
            self._update_account_status_and_time(account_obj, dlg.result)
            self.filter_treeview()
            self.save_data()

    def _add_shortcut_menu_items(self, menu, account_obj):
        # 判断账号是否有冷却时间（VAC封禁或有未来时间）
        has_cooldown = self._has_cooldown(account_obj)
        
        # 有冷却时间才显示"立即可用"
        if has_cooldown:
            menu.add_command(
                label=lang['immediately_available'],
                command=lambda acc=account_obj: self.apply_shortcut(acc, "reset")
            )
            menu.add_separator()
        
        menu.add_command(
            label=lang['shortcut_20h'],
            command=lambda acc=account_obj: self.apply_shortcut(acc, "delta", hours=20)
        )
        menu.add_command(
            label=lang['shortcut_7d'],
            command=lambda acc=account_obj: self.apply_shortcut(acc, "delta", days=7)
        )
        menu.add_command(
            label=lang['shortcut_31d'],
            command=lambda acc=account_obj: self.apply_shortcut(acc, "delta", days=31)
        )
        menu.add_command(
            label=lang['shortcut_181d'],
            command=lambda acc=account_obj: self.apply_shortcut(acc, "delta", days=181)
        )
        menu.add_separator()
        menu.add_command(
            label=lang['custom_days_hours'],
            command=lambda acc=account_obj: self._custom_shortcut(acc)
        )
        # 只有非VAC账号才能设置VAC封禁
        if account_obj.get('available_time') != "VAC":
            menu.add_command(
                label=lang['shortcut_vac'],
                command=lambda acc=account_obj: self.apply_shortcut(acc, "vac")
            )

    def _has_cooldown(self, account_obj):
        """判断账号是否有冷却时间（VAC封禁或有未来冷却时间）"""
        at = account_obj.get('available_time', '')
        if at == "VAC":
            return True
        try:
            available_dt = datetime.datetime.strptime(at, "%Y-%m-%d %H:%M")
            return available_dt > datetime.datetime.now()
        except (ValueError, TypeError):
            return False

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
            command=lambda acc=account_obj: self.set_remarks(acc, "")
        )
        menu.add_separator()
        menu.add_command(
            label=lang['remarks_options'][1], 
            command=lambda acc=account_obj: self._custom_remarks(acc)
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

    def apply_shortcut(self, account_obj, action_type, hours=0, days=0):
        # 处理VAC封禁
        if action_type == "vac":
            self._update_account_status_and_time(account_obj, vac_ban=True)
            self.filter_treeview()
            self.save_data()
            return
        # 处理立即可用
        if action_type == "reset":
            self._update_account_status_and_time(account_obj, datetime.datetime.now())
            self.filter_treeview()
            self.save_data()
            return
        # 处理delta时间
        if action_type == "delta":
            now = datetime.datetime.now()
            new_available_time_dt = now + datetime.timedelta(days=days, hours=hours)
            self._update_account_status_and_time(account_obj, new_available_time_dt)
            self.filter_treeview()
            self.save_data()

    def _update_account_status_and_time(self, account_obj, new_available_time_dt=None, vac_ban=False):
        # 优先处理显式设置的情况（解除VAC或设置VAC）
        if vac_ban:
            account_obj['available_time'] = "VAC"
            account_obj['status'] = lang['status_unavailable']
            self._sync_original_data(account_obj)
            return
        
        # 有具体时间值时，解除VAC并设置时间
        if new_available_time_dt is not None:
            account_obj['available_time'] = new_available_time_dt.strftime("%Y-%m-%d %H:%M")
            account_obj['status'] = lang['status_available'] if new_available_time_dt <= datetime.datetime.now() else lang['status_unavailable']
            self._sync_original_data(account_obj)
            return

        # 没有具体设置时，如果是VAC则保持不变（只确保status正确）
        if account_obj.get('available_time') == "VAC":
            account_obj['status'] = lang['status_unavailable']
            return
        
        # 正常解析时间
        try:
            available_dt = datetime.datetime.strptime(account_obj['available_time'], "%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            available_dt = datetime.datetime.min
        account_obj['available_time'] = available_dt.strftime("%Y-%m-%d %H:%M")
        account_obj['status'] = lang['status_available'] if available_dt <= datetime.datetime.now() else lang['status_unavailable']
        self._sync_original_data(account_obj)

    def _sync_original_data(self, account_obj):
        """同步更新原始数据"""
        for orig_acc in self.original_data:
            if orig_acc['account'] == account_obj['account']:
                orig_acc['available_time'] = account_obj['available_time']
                orig_acc['status'] = account_obj['status']
                break



    def update_row_in_treeview(self, tree_item_id, account_obj):
        select_char = "☑" if account_obj.get('selected_state', False) else "☐"
        self._update_account_status_and_time(account_obj)
        status_tag = account_obj['status']
        account_obj.setdefault('remarks', '')
        display_shortcut = ""
        display_available_time = account_obj['available_time']

        # 处理VAC封禁显示
        if account_obj['available_time'] == "VAC":
            display_available_time = lang['check_cooldown_vac']
            display_shortcut = lang['check_cooldown_vac']
        else:
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
            
        password = account_obj['password']
        others = account_obj.get('others', '')

        if not self.show_hidden_var.get():
            password = '*' * len(password)
            others = '*' * len(others)
            
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
            password,
            account_obj['status'],
            account_obj['remarks'],
            display_shortcut,
            display_available_time,
            others
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
                self.tree.insert("", tk.END, values=("", "", "", "", "", "", "", "", ""), tags=('blank',))
                continue
            
            # 处理实际数据行
            acc_data = item_data
            self._update_account_status_and_time(acc_data)
            select_char = "☑" if acc_data.get('selected_state', False) else "☐"
            status_tag = acc_data['status']
            acc_data.setdefault('remarks', '')
            display_shortcut = ""
            display_available_time = acc_data['available_time']
            
            password = acc_data['password']
            others = acc_data.get('others', '')

            if not self.show_hidden_var.get():
                password = '*' * len(password)
                others = '*' * len(others)
            
            # 处理VAC封禁显示
            if acc_data['available_time'] == "VAC":
                display_available_time = lang['check_cooldown_vac']
                display_shortcut = lang['check_cooldown_vac']
            else:
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
                password,
                acc_data['status'],
                acc_data['remarks'],
                display_shortcut,
                display_available_time,
                others
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
            # side=RIGHT 时先 pack 的在最右边，这里的顺序对应界面上从左到右：
            # 批量备注 / 批量移动 / 查询VAC / 修改资料 / 删除选中
            self.batch_remarks_combo.pack(side=tk.RIGHT, padx=5)
            self.batch_remarks_btn.pack(side=tk.RIGHT, padx=5)
            self.batch_move_combo.pack(side=tk.RIGHT, padx=5)
            self.batch_move_btn.pack(side=tk.RIGHT, padx=5)
            self.vac_btn.pack(side=tk.RIGHT, padx=5)
            self.edit_profile_btn.pack(side=tk.RIGHT, padx=5)
            self.delete_btn.pack(side=tk.RIGHT, padx=5)
        else:
            self.batch_remarks_combo.pack_forget()
            self.batch_remarks_btn.pack_forget()
            self.batch_move_combo.pack_forget()
            self.batch_move_btn.pack_forget()
            self.vac_btn.pack_forget()
            self.edit_profile_btn.pack_forget()
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
                remark_match = search_text in acc.get('remarks', '').lower()
                match_search = account_match or remark_match
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
        }
        self.accounts_data.sort(
            key=lambda acc: remarks_order.get(acc.get("remarks", ""), 0),
            reverse=self.remarks_sort_reverse
        )
        self.filter_treeview()

    def _add_new_account_entry(self, account, password, others=""):
        password = password.strip() # 去除首尾空格
    
        # 只检查账号是否已存在，不考虑密码
        if not any(acc['account'] == account for acc in self.accounts_data):
            default_available_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            new_acc = {
                'account': account,
                'password': password,
                'available_time': default_available_time,
                'remarks': '',
                'selected_state': False,
                'others': others
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
        # 在后台线程中执行导入
        def import_worker():
            try:
                new_accounts_count = 0
                accounts_to_add = []
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if "----" in line:
                            parts = line.split("----", 2)
                            account = parts[0].strip()
                            password = parts[1].strip() if len(parts) > 1 else ""
                            others = parts[2].strip() if len(parts) > 2 else ""
                            if account and password:
                                accounts_to_add.append((account, password, others))
                # 收集完所有账号后，一次性添加到数据中
                existing_accounts = {acc['account'] for acc in self.accounts_data}
                for account, password, others in accounts_to_add:
                    if account not in existing_accounts:
                        default_available_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                        new_acc = {
                            'account': account,
                            'password': password,
                            'available_time': default_available_time,
                            'remarks': '',
                            'selected_state': False,
                            'others': others
                        }
                        self.accounts_data.append(new_acc)
                        self.original_data.append(new_acc.copy())
                        new_accounts_count += 1
                        existing_accounts.add(account)
                return {'type': 'import', 'count': new_accounts_count}
            except Exception as e:
                return {'type': 'error', 'error': str(e)}
        # 使用结果队列获取线程返回值
        result_queue = queue.Queue()
        def run_in_thread():
            result = import_worker()
            result_queue.put(result)
            # 在主线程中更新UI
            self.root.after(10, lambda: self._finish_import(result_queue))
        threading.Thread(target=run_in_thread, daemon=True).start()

    def _finish_import(self, result_queue):
        """在主线程中完成导入并更新UI"""
        try:
            result = result_queue.get_nowait()
            if result.get('type') == 'error':
                messagebox.showerror(lang['import_error'], lang['import_failed'].format(error=result.get('error', '')), parent=self.root)
            elif result.get('count', 0) > 0:
                messagebox.showinfo(lang['import_success'], lang['imported_new_accounts'].format(count=result['count']), parent=self.root)
                self.filter_treeview()
                self.save_data()
            else:
                messagebox.showinfo(lang['import_txt'], lang['import_no_new'], parent=self.root)
                self.filter_treeview()
        except queue.Empty:
            # 如果队列为空，稍后再试
            self.root.after(50, lambda: self._finish_import(result_queue))

    def add_account_dialog(self):
        dialog = AddAccountDialog(self.root, lang['add_accounts'], self.import_txt)
        # 检查用户是否点了确定（simpledialog.Dialog 点取消时 result 为 None）
        if dialog.result is None:
            return
        if hasattr(dialog, 'new_accounts_data') and dialog.new_accounts_data:
            if dialog.new_accounts_data:
                new_accounts_count = 0
                for acc_info in dialog.new_accounts_data:
                    # 接收账号、密码和其它信息
                    account, password, others = acc_info if len(acc_info) > 2 else (*acc_info, "")
                    if self._add_new_account_entry(account, password, others):  # 传入others
                        new_accounts_count += 1
                
                # 计算已存在账号数（有效行数 - 新添加数 = 已存在数）
                valid_lines = len(dialog.new_accounts_data)
                existing_count = valid_lines - new_accounts_count
                invalid_count = dialog.invalid_count
                
                if new_accounts_count > 0:
                    self.save_data()
                    # 根据不同情况显示不同的提示
                    if invalid_count > 0 and existing_count > 0:
                        messagebox.showinfo(lang['add_success'], lang['add_partial_mixed'].format(
                            count=new_accounts_count, exists_count=existing_count, invalid_count=invalid_count), parent=self.root)
                    elif invalid_count > 0:
                        messagebox.showinfo(lang['add_success'], lang['add_partial_with_invalid'].format(
                            count=new_accounts_count, invalid_count=invalid_count), parent=self.root)
                    elif existing_count > 0:
                        messagebox.showinfo(lang['add_success'], lang['add_partial_with_exists'].format(
                            count=new_accounts_count, exists_count=existing_count), parent=self.root)
                    else:
                        messagebox.showinfo(lang['add_success'], lang['added_new_accounts'].format(count=new_accounts_count), parent=self.root)
                elif dialog.new_accounts_data:
                    messagebox.showinfo(lang['manual_add'], lang['add_no_new'], parent=self.root)
                self.filter_treeview()
        elif hasattr(dialog, 'total_lines') and dialog.total_lines == 0:
            # 输入为空
            messagebox.showinfo(lang['manual_add'], lang['add_empty_input'], parent=self.root)
        elif hasattr(dialog, 'invalid_count') and dialog.invalid_count > 0 and (not hasattr(dialog, 'new_accounts_data') or not dialog.new_accounts_data):
            # 全是无效行
            messagebox.showinfo(lang['manual_add'], lang['add_invalid_lines'].format(count=dialog.invalid_count), parent=self.root)

    def save_data(self, on_complete=None):
        """保存数据到文件，使用后台线程避免UI卡顿"""
        # 准备数据（在主线程快速完成）
        data_to_save = []
        for acc in self.original_data:
            acc_copy = acc.copy()
            acc_copy.pop('tree_id', None)
            acc_copy.pop('selected_state', None)
            acc_copy.pop('status', None)
            if acc_copy['remarks'] in self.REMARKS_TO_JSON:
                acc_copy['remarks'] = self.REMARKS_TO_JSON[acc_copy['remarks']]
            data_to_save.append(acc_copy)
        # 在后台线程中执行文件写入
        def save_worker():
            try:
                with open(self.data_file, 'w', encoding='utf-8') as f:
                    json.dump(data_to_save, f, ensure_ascii=False, indent=4)
                return {'type': 'save', 'success': True}
            except Exception as e:
                return {'type': 'save', 'success': False, 'error': str(e)}
        result_queue = queue.Queue()
        def run_in_thread():
            result = save_worker()
            result_queue.put(result)
            self.root.after(10, lambda: self._finish_save(result_queue, on_complete))
        threading.Thread(target=run_in_thread, daemon=True).start()

    def _finish_save(self, result_queue, on_complete=None):
        """在主线程中处理保存结果"""
        try:
            result = result_queue.get_nowait()
            if not result.get('success'):
                messagebox.showerror(lang['save_failed'], lang['save_error'].format(error=result.get('error', '')), parent=self.root)
            elif on_complete:
                on_complete()
        except queue.Empty:
            self.root.after(50, lambda: self._finish_save(result_queue, on_complete))

    def load_data(self):
        try:
            # 需要设置的默认值
            default_available_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            
            # 读取JSON数据
            with open(self.data_file, 'r', encoding='utf-8') as f:
                loaded_entries = json.load(f)
            
            # 预处理所有数据，减少循环中的重复操作
            self.accounts_data = []
            self.original_data = []
            
            for entry in loaded_entries:
                # 设置默认值
                entry.setdefault('selected_state', False)
                entry.setdefault('available_time', default_available_time)
                entry.setdefault('others', '')
                
                # 兼容数字和字符串备注
                remarks = entry.get('remarks', "")
                if isinstance(remarks, int):
                    entry['remarks'] = self.REMARKS_FROM_JSON.get(remarks, '')
                else:
                    entry['remarks'] = remarks or ''
                
                # 直接引用，避免重复copy
                self.accounts_data.append(entry)
                self.original_data.append(entry)
                
        except FileNotFoundError:
            self.accounts_data = []
            self.original_data = []
        except Exception as e:
            messagebox.showerror(lang['load_error'], lang['load_failed'].format(error=e), parent=self.root)
            self.accounts_data = []
            self.original_data = []
        self.filter_treeview()

    def _load_data_async(self):
        """异步加载数据，在后台线程执行，不阻塞UI"""
        def load_worker():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    loaded_entries = json.load(f)
                default_available_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                
                processed_data = []
                for entry in loaded_entries:
                    entry.setdefault('selected_state', False)
                    entry.setdefault('available_time', default_available_time)
                    entry.setdefault('others', '')
                    remarks = entry.get('remarks', "")
                    if isinstance(remarks, int):
                        entry['remarks'] = self.REMARKS_FROM_JSON.get(remarks, '')
                    else:
                        entry['remarks'] = remarks or ''
                    processed_data.append(entry)
                
                return processed_data
            except Exception:
                return []
        
        def on_load_complete(processed_data):
            self.accounts_data = processed_data
            self.original_data = [acc.copy() for acc in processed_data]
            self._data_loaded = True
            self.filter_treeview()
        
        def run_in_thread():
            processed_data = load_worker()
            self.root.after(0, lambda: on_load_complete(processed_data))
        threading.Thread(target=run_in_thread, daemon=True).start()

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
        # 检查是否有选中的账号（使用数据中的selected_state）
        selected_accounts = [
            acc for acc in self.accounts_data 
            if acc.get('selected_state', False)
        ]
    
        if not selected_accounts:
            messagebox.showinfo(lang['export_no_selected'], lang['export_no_accounts'])
            return

        # 显示导出方式选择对话框
        dialog = ExportMethodDialog(self.root)
        export_method = dialog.result

        if not export_method: return

        # 收集选中账号的原始数据（使用真实密码）
        export_data = []
        for acc in selected_accounts:
            # 有其它信息则导出三部分，否则只导出账号密码
            if acc.get('others'):
                export_data.append(f"{acc['account']}----{acc['password']}----{acc['others']}")
            else:
                export_data.append(f"{acc['account']}----{acc['password']}")

        # 根据选择的导出方式执行操作
        if export_method == "txt":
            # TXT文件导出逻辑
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[(lang['txt_file'], "*.txt"), ("All Files", "*.*")]
            )
            if not file_path: return

            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(export_data))
                messagebox.showinfo(
                    lang['export_success'],
                    lang['exported_accounts'].format(count=len(export_data), path=file_path)
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
                self.root.clipboard_append("\n".join(export_data))
                self.root.update()  # 确保剪贴板内容被更新
                messagebox.showinfo(
                    lang['export_success'],
                    lang['exported_accounts'].format(count=len(export_data), path=lang['clipboard'])
                )
            except Exception as e:
                messagebox.showerror(
                    lang['export_error'],
                    lang['export_failed'].format(error=str(e))
                )


    # ========== 批量任务调度（分批并发 + 失败的挪到下一批重试） ==========

    BATCH_SIZE = 5            # 查询VAC/冷却时每批并发数
    BATCH_DELAY = 3           # 查询时批与批之间的等待秒数
    PROFILE_BATCH_SIZE = 3    # 改资料时每批并发数（改资料比查询娇气，并发数取小一点）
    PROFILE_BATCH_DELAY = 10  # 改资料时批与批之间的等待秒数
    RETRY_COUNT = 1           # 失败的账号挪到下一批重试的次数
    RATE_LIMIT_DELAY = 30     # 被Steam限流(HTTP 429)后的等待秒数

    # 失败后值得重试（重新登录再整体跑一遍）的结果类型，其余的失败重试也没有意义
    COOLDOWN_RETRYABLE_RESULTS = ('fail',)
    COOLDOWN_OK_RESULTS = ('cooldown', 'vac', 'no_ban')
    PROFILE_RETRYABLE_RESULTS = ('login_failed', 'read_failed', 'no_id', 'no_session', 'rate_limited')

    @staticmethod
    async def _run_batches(accounts, worker, batch_size, batch_delay,
                           retry_count=1, rate_limit_delay=30,
                           retryable_results=(), error_result_type='fail',
                           progress_callback=None, retry_callback=None):
        """
        分批并发执行 worker：成功的账号到此为止，失败的账号收集起来作为下一批重试

        :param accounts:       [(账号, 密码), ...]，第一批要处理的全部账号
        :param worker:         async (账号, 密码) -> 结果字典，内部只尝试一次
        :param batch_size:     每批并发数
        :param batch_delay:    批与批之间的等待秒数
        :param retry_count:    失败账号额外重试的批次数
        :param rate_limit_delay: 本批出现限流(HTTP 429)时，下一批之前的等待秒数
        :param retryable_results: 值得重试的结果类型，其余类型直接算最终结果
        :param error_result_type: worker 抛出异常时使用的失败类型
        :param progress_callback: (done, total, 账号, 结果) -> None，账号有最终结果时回调
        :param retry_callback:  (账号, 第几次重试) -> None，账号被挪进重试批时回调
        :return: (results, failed)
                 results: {账号: 结果字典}，成功和重试后仍失败的账号都在里面
                 failed:  {账号: 结果字典}，重试次数用尽后仍然失败的账号
        """
        results = {}
        pending = list(accounts)
        total = len(accounts)
        done = 0
        failed = {}

        for attempt in range(retry_count + 1):
            if not pending:
                break
            if attempt > 0:
                # 上一批失败的账号进入重试批，已经成功的账号不再处理
                for username, _password in pending:
                    if retry_callback:
                        retry_callback(username, attempt)

            next_pending = []
            wave_rate_limited = False
            for index in range(0, len(pending), batch_size):
                chunk = pending[index:index + batch_size]
                chunk_results = await asyncio.gather(
                    *(worker(username, password) for username, password in chunk),
                    return_exceptions=True
                )
                chunk_rate_limited = False
                for (username, password), result in zip(chunk, chunk_results):
                    if not isinstance(result, dict):
                        result = {"type": error_result_type, "error": str(result)}
                    if result.get('rate_limited') or result.get('type') == 'rate_limited':
                        chunk_rate_limited = True
                    results[username] = result
                    if result.get('type') in retryable_results:
                        # 这一批失败的账号留到下一批再试
                        next_pending.append((username, password))
                    else:
                        done += 1
                        if progress_callback:
                            progress_callback(done, total, username, result)
                wave_rate_limited = wave_rate_limited or chunk_rate_limited
                # 本批被限流就多等一会儿，避免后面的批次接着撞限流
                if index + batch_size < len(pending):
                    await asyncio.sleep(rate_limit_delay if chunk_rate_limited else batch_delay)

            if next_pending and attempt < retry_count:
                # 重试批之前等一会儿，给Steam的限流留出恢复时间
                await asyncio.sleep(rate_limit_delay if wave_rate_limited else batch_delay)
                pending = next_pending
                continue

            # 没有重试机会了，这些账号就是最终失败
            for username, _password in next_pending:
                failed[username] = results[username]
                done += 1
                if progress_callback:
                    progress_callback(done, total, username, results[username])
            break

        return results, failed

    # ========== 冷却/VAC查询 ==========

    @staticmethod
    def _parse_steam_time_to_local(html, cooldown_text):
        """将Steam页面显示的冷却时间（太平洋时间）转换为本地时区"""
        match = re.search(r'g_ServerTime\s*=\s*(\d+)', html)
        if not match:
            return cooldown_text

        server_timestamp = int(match.group(1))
        server_time = datetime.datetime.fromtimestamp(server_timestamp, tz=datetime.timezone.utc)

        pacific = pytz.timezone('US/Pacific')

        try:
            server_pacific = server_time.astimezone(pacific)
            _ = bool(server_pacific.dst())  # 验证夏令时状态可用
        except Exception:
            server_pacific = server_time.astimezone(pacific)

        steam_match = re.match(r'(\d+)\s*月\s*(\d+)\s*日\s*(上午|下午)\s*(\d+):(\d+)', cooldown_text)
        if not steam_match:
            return cooldown_text

        month = int(steam_match.group(1))
        day = int(steam_match.group(2))
        period = steam_match.group(3)
        hour = int(steam_match.group(4))
        minute = int(steam_match.group(5))

        if period == '下午' and hour != 12:
            hour += 12
        elif period == '上午' and hour == 12:
            hour = 0

        year = server_pacific.year

        try:
            pacific_dt = pacific.localize(datetime.datetime(year, month, day, hour, minute))
        except Exception:
            return cooldown_text

        local_dt = pacific_dt.astimezone(None)

        return local_dt.strftime("%Y-%m-%d %H:%M")

    @staticmethod
    async def _close_steam_session(steam):
        """
        关闭 pysteamauth 底层的 aiohttp 会话，避免 Unclosed client session 警告
        关闭后把 _session 置空，否则对象回收时 BaseRequestStrategy.__del__ 会访问
        已为 None 的 session.connector 而抛出 Exception ignored
        """
        if not steam:
            return
        try:
            strategy = getattr(steam, '_requests', None)
            session = getattr(strategy, '_session', None)
            if session is not None:
                await session.close()
            if strategy is not None:
                strategy._session = None
        except Exception:
            pass

    @staticmethod
    async def _check_single_cooldown(username, password):
        """查询单个账号的冷却/VAC状态

        只尝试一次：失败时返回 type='fail'，由 _run_batches 把账号挪到下一批重试
        """
        steam = None
        try:
            steam = Steam(username, password)
            await steam.login_to_steam()

            # 检查VAC冷却时间
            r = await steam.request(
                "https://help.steampowered.com/zh-cn/wizard/HelpWithGameIssue/?appid=730&issueid=131"
            )
            # 请求过密时拿到的是限流错误页，不是账号页面，标记出来让下一批多等一会儿
            if AccountManagerApp._is_rate_limited(r):
                return {"type": "fail", "rate_limited": True,
                        "error": lang['edit_profile_rate_limited']}

            # 仅使用字符串查找，不依赖 BeautifulSoup
            marker = 'help_game_cooldown_expirationtime">'
            start_index = r.find(marker)
            if start_index != -1:
                start_index += len(marker)
                end_index = r.find('</span>', start_index)
                if end_index != -1:
                    cooldown_text = r[start_index:end_index].strip()
                    if cooldown_text:
                        cooldown_local = AccountManagerApp._parse_steam_time_to_local(r, cooldown_text)
                        return {"type": "cooldown", "time": cooldown_local}

            # 检查VAC状态
            r_vac = await steam.request("https://help.steampowered.com/zh-cn/wizard/VacBans")
            if AccountManagerApp._is_rate_limited(r_vac):
                return {"type": "fail", "rate_limited": True,
                        "error": lang['edit_profile_rate_limited']}
            if "Counter-Strike 2" in r_vac:
                return {"type": "vac"}
            return {"type": "no_ban"}
        except Exception as e:
            return {"type": "fail", "error": str(e)}
        finally:
            # 确保 session 被关闭
            await AccountManagerApp._close_steam_session(steam)

    @staticmethod
    async def _check_cooldown_batch(accounts, batch_size=5, batch_delay=3,
                                    progress_callback=None, retry_callback=None):
        """批量查询冷却/VAC状态

        每批并发 batch_size 个账号，失败的账号作为下一批重试，成功的账号不再处理。
        单个账号失败不影响其它账号。

        :return: (results, failed)
                 failed 是重试后仍然查询失败的账号（调用方据此决定要不要写入冷却状态）
        """
        async def worker(username, password):
            return await AccountManagerApp._check_single_cooldown(username, password)

        results, failed = await AccountManagerApp._run_batches(
            accounts,
            worker,
            batch_size=batch_size,
            batch_delay=batch_delay,
            retry_count=AccountManagerApp.RETRY_COUNT,
            rate_limit_delay=AccountManagerApp.RATE_LIMIT_DELAY,
            retryable_results=AccountManagerApp.COOLDOWN_RETRYABLE_RESULTS,
            error_result_type='fail',
            progress_callback=progress_callback,
            retry_callback=retry_callback
        )
        # 兜底：结果不是已知的正常态就按失败处理，交给调用方取消整批查询
        for username, result in results.items():
            if result.get('type') not in AccountManagerApp.COOLDOWN_OK_RESULTS and username not in failed:
                failed[username] = result
        return results, failed

    def check_cooldown_selected(self):
        """批量查询选中账号的冷却/VAC状态"""
        selected_accounts = [
            acc for acc in self.accounts_data if acc.get('selected_state', False)
        ]
        # 没有选中账号时不执行
        if not selected_accounts:
            messagebox.showinfo(
                lang['check_cooldown_selected'],
                lang['check_cooldown_no_accounts'],
                parent=self.root
            )
            return
        # 上一次查询还在进行中时不再重复发起，避免请求过密被Steam限流
        if getattr(self, '_checking_vac', False):
            return
        self._checking_vac = True

        accounts_to_check = [(acc['account'], acc['password']) for acc in selected_accounts]
        total = len(accounts_to_check)

        # 创建进度窗口
        progress_win, progress_bar, progress_label = self._create_progress_window(
            lang['check_cooldown_progress'])
        progress_bar['maximum'] = total

        result_queue = queue.Queue()

        def run_check():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                def on_progress(done, total_count, username, result):
                    result_queue.put(('progress', done, total_count, username, result))

                def on_retry(username, attempt):
                    print(f"重试中: {username} 第{attempt}次")
                    result_queue.put(('retry', username, attempt))

                results, failed = loop.run_until_complete(
                    AccountManagerApp._check_cooldown_batch(
                        accounts_to_check,
                        batch_size=AccountManagerApp.BATCH_SIZE,
                        batch_delay=AccountManagerApp.BATCH_DELAY,
                        progress_callback=on_progress,
                        retry_callback=on_retry
                    )
                )
                result_queue.put(('done', results, failed))
            except Exception as e:
                result_queue.put(('error', str(e)))
            finally:
                loop.close()

        threading.Thread(target=run_check, daemon=True).start()

        def poll_queue():
            try:
                while True:
                    msg = result_queue.get_nowait()
                    if msg[0] == 'progress':
                        _, done, total_count, _username, result = msg
                        progress_bar['value'] = done
                        progress_label.config(text=lang['check_cooldown_progress_text'].format(
                            done=done, total=total_count))
                        if result.get('type') == 'fail':
                            # 走到这里说明重试之后仍然失败，整批查询会被取消
                            print(f"查询失败: {_username} {result.get('error', '')}")
                    elif msg[0] == 'retry':
                        self._append_retry_title_suffix(progress_win)
                    elif msg[0] == 'done':
                        self._checking_vac = False
                        self._remove_retry_title_suffix(progress_win)
                        progress_win.destroy()
                        results, failed = msg[1], msg[2]
                        if failed:
                            # 重试之后仍然失败：整批任务取消，不写入任何冷却状态
                            self._on_cooldown_aborted(failed)
                        elif results:
                            self._apply_cooldown_results(results, selected_accounts)
                        return
                    elif msg[0] == 'error':
                        self._checking_vac = False
                        self._remove_retry_title_suffix(progress_win)
                        progress_win.destroy()
                        messagebox.showerror(
                            lang['check_cooldown_fail'],
                            lang['check_cooldown_fail_msg'],
                            parent=self.root
                        )
                        return
            except queue.Empty:
                pass
            except tk.TclError:
                # 窗口已被销毁，停止轮询
                return
            self.root.after(100, poll_queue)

        poll_queue()

    def _apply_cooldown_results(self, results, selected_accounts):
        """将查询结果应用到账号数据中

        只在整批查询全部成功时才会被调用：有任何账号重试后仍失败，调用方会直接取消整批任务，
        一个字段都不写
        """
        for acc in selected_accounts:
            username = acc['account']
            result = results.get(username)
            if not result:
                continue

            if result['type'] == 'vac':
                # VAC封禁：available_time设为"VAC"
                acc['available_time'] = "VAC"
                acc['status'] = lang['status_unavailable']
                for orig_acc in self.original_data:
                    if orig_acc['account'] == username:
                        orig_acc['available_time'] = "VAC"
                        orig_acc['status'] = lang['status_unavailable']
                        break
            elif result['type'] == 'cooldown':
                try:
                    dt = datetime.datetime.strptime(result['time'], "%Y-%m-%d %H:%M")
                except (KeyError, TypeError, ValueError):
                    # 时间没能解析成"年-月-日 时:分"（页面结构变化/服务器时间缺失），宁可不写也不写错
                    print(f"[{username}] 提示: 冷却时间无法解析 {result.get('time')!r}，已跳过该账号")
                    continue
                if dt <= datetime.datetime.now():
                    # 冷却到期，设为可用
                    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    acc['available_time'] = now_str
                    acc['status'] = lang['status_available']
                    for orig_acc in self.original_data:
                        if orig_acc['account'] == username:
                            orig_acc['available_time'] = now_str
                            orig_acc['status'] = lang['status_available']
                            break
                else:
                    # 冷却中
                    acc['available_time'] = result['time']
                    acc['status'] = lang['status_unavailable']
                    for orig_acc in self.original_data:
                        if orig_acc['account'] == username:
                            orig_acc['available_time'] = result['time']
                            orig_acc['status'] = lang['status_unavailable']
                            break
            elif result['type'] == 'no_ban':
                # 无封禁：设为当前时间（立即可用）
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                acc['available_time'] = now_str
                acc['status'] = lang['status_available']
                for orig_acc in self.original_data:
                    if orig_acc['account'] == username:
                        orig_acc['available_time'] = now_str
                        orig_acc['status'] = lang['status_available']
                        break

        self.filter_treeview()
        self.save_data()

        # 生成结果摘要
        vac_count = sum(1 for r in results.values() if r['type'] == 'vac')
        cooldown_count = sum(1 for r in results.values() if r['type'] == 'cooldown')
        no_ban_count = sum(1 for r in results.values() if r['type'] == 'no_ban')
        expired_cooldown_count = sum(1 for acc in selected_accounts if acc['status'] == lang['status_available'] and acc['account'] in [k for k, v in results.items() if v['type'] == 'cooldown'])

        summary_lines = []
        if vac_count > 0:
            summary_lines.append(f"{lang['check_cooldown_vac']}: {vac_count}")
        if cooldown_count > 0:
            active = cooldown_count - expired_cooldown_count
            if active > 0:
                summary_lines.append(f"{lang['check_cooldown_cooldown']}: {active}")
        if no_ban_count > 0 or expired_cooldown_count > 0:
            summary_lines.append(f"{lang['check_cooldown_no_ban']}: {no_ban_count + expired_cooldown_count}")

        messagebox.showinfo(
            lang['check_cooldown_result'],
            "\n".join(summary_lines),
            parent=self.root
        )

    def _on_cooldown_aborted(self, failed):
        """有账号重试之后仍然查询失败：整批任务取消，不写入任何冷却状态，只提示失败的账号"""
        messagebox.showwarning(
            lang['check_cooldown_result'],
            "\n".join([
                lang['check_cooldown_aborted'],
                lang['check_cooldown_fail_accounts'].format(accounts=", ".join(failed)),
            ]),
            parent=self.root
        )

    def _center_window_on_root(self, window, width, height):
        """把子窗口居中到主窗口上"""
        window.update_idletasks()
        mx = self.root.winfo_x()
        my = self.root.winfo_y()
        mw = self.root.winfo_width()
        mh = self.root.winfo_height()
        window.geometry(f"{width}x{height}+{mx + (mw - width)//2}+{my + (mh - height)//2}")

    def _create_progress_window(self, title):
        """
        创建读条进度窗口（禁止关闭，避免后台任务还在跑时窗口消失）
        返回 (窗口, 进度条, 提示标签)
        """
        progress_win = tk.Toplevel(self.root)
        progress_win.title(title)
        progress_win.geometry("380x80")
        progress_win.resizable(False, False)
        progress_win.transient(self.root)
        progress_win.grab_set()
        progress_win.protocol("WM_DELETE_WINDOW", lambda: None)

        progress_bar = ttk.Progressbar(progress_win, length=350, mode='determinate')
        progress_bar.pack(pady=(15, 5))
        progress_label = ttk.Label(progress_win, text=title)
        progress_label.pack(pady=(0, 10))

        self._center_window_on_root(progress_win, 380, 80)
        return progress_win, progress_bar, progress_label

    def _allow_progress_window_close(self, progress_win):
        """读条结束后允许关闭窗口"""
        try:
            progress_win.protocol("WM_DELETE_WINDOW", progress_win.destroy)
        except tk.TclError:
            pass

    # ========== 修改个人资料（名称/真实姓名/概要） ==========

    # 各项长度上限：按 UTF-8 字节算（中文一个字 3 字节），超长会被 Steam 静默截断
    PROFILE_LIMITS = {
        'personaName': 32,
        'real_name': 64,
        'summary': 4096,
    }

    # 个人资料相关地址
    PROFILE_ACCOUNT_URL = "https://store.steampowered.com/account/"
    PROFILE_EDIT_INFO_URL = "https://steamcommunity.com/profiles/{steam_id}/edit/info"
    PROFILE_EDIT_URL = "https://steamcommunity.com/profiles/{steam_id}/edit"
    PROFILE_URL = "https://steamcommunity.com/profiles/{steam_id}/"

    # 请求过于频繁时 Steam 返回 HTTP 429 错误页，页面是错误页而不是正常资料页
    RATE_LIMIT_MARKERS = ('Steam Community :: Error', 'too many requests')

    @staticmethod
    def _brief_text(value, limit=40):
        """输出用：过长的内容截断显示，空值显示为 (空)"""
        if value is None:
            return lang['edit_profile_empty']
        if value == '':
            return lang['edit_profile_empty']
        return value if len(value) <= limit else value[:limit] + '…'

    @staticmethod
    def _is_rate_limited(html_content):
        """判断返回的内容是不是 Steam 的限流错误页（HTTP 429）"""
        text = (html_content or '').lower()
        return any(marker.lower() in text for marker in AccountManagerApp.RATE_LIMIT_MARKERS)

    @staticmethod
    def _extract_steam_id_from_account_page(html_content):
        """
        从账户页面提取Steam ID（64位）
        支持两种格式：
        1. 中文格式："Steam ID："（中文冒号，后面没有任何空格）
        2. 英文格式："Steam ID: "（英文冒号+空格）
        """
        match = re.search(r'Steam ID：(\d+)', html_content)
        if match:
            return match.group(1)
        match = re.search(r'Steam ID:\s+(\d+)', html_content)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _extract_profile_edit_config(html_content):
        """
        从 edit/info 页面提取 data-profile-edit 属性中的资料原值 JSON
        属性值里的引号是 &quot;，需要先 HTML 反转义再解析
        """
        # 优先按 id="profile_edit_config" 定位，避免匹配到其它 data-profile-edit
        match = re.search(r'id="profile_edit_config"[^>]*?data-profile-edit="(.*?)"', html_content, re.S)
        if not match:
            # 属性顺序不固定，退化为直接查找 data-profile-edit
            match = re.search(r'data-profile-edit="(.*?)"', html_content, re.S)
        if not match:
            return None
        try:
            return json.loads(html_lib.unescape(match.group(1)))
        except Exception:
            return None

    @staticmethod
    def _extract_public_persona_name(html_content):
        """从个人资料页提取当前昵称（公开页面效果）"""
        match = re.search(r'class="actual_persona_name">(.*?)</span>', html_content, re.S)
        if match:
            return html_lib.unescape(match.group(1)).strip()
        # 备用：页面标题 "Steam Community :: 昵称"
        match = re.search(r'<title>Steam Community :: (.*?)</title>', html_content, re.S)
        if match:
            return html_lib.unescape(match.group(1)).strip()
        return None

    @staticmethod
    async def _edit_profile_single(username, password, persona_name=None, real_name=None, summary=None,
                                   force=False):
        """
        修改（或只读取）单个账号的个人资料

        :param persona_name: 新昵称
        :param real_name:    新真实姓名
        :param summary:      新概要
        三个参数：None=保持原值不动，""=清空该项，其它=改成该内容
        :param force: 内容和原资料相同时，True=仍然提交（用户明确点了确定）
        :return: 结果字典，type 取值：
                 no_id / login_failed / read_failed / rate_limited / no_change /
                 no_session / failed / success / verify_failed

        只尝试一次：login_failed / read_failed / no_id / no_session / rate_limited 都属于
        「还没真正提交」的失败，由 _edit_profile_batch 把账号挪到下一批重试；
        提交成功之后（包括提交成功但回读确认失败）一律不再重试，避免同一个账号被反复改。
        """
        changes = {
            'personaName': persona_name,
            'real_name': real_name,
            'summary': summary,
        }
        changes = {key: value for key, value in changes.items() if value is not None}

        steam = None
        submitted = False  # 表单是否已经提交成功（提交成功后的失败不再重试）
        current = {}
        try:
            steam = Steam(username, password)
            await steam.login_to_steam()

            # 1. 取 Steam ID（64位）
            account_page = await steam.request(AccountManagerApp.PROFILE_ACCOUNT_URL)
            steam_id = AccountManagerApp._extract_steam_id_from_account_page(account_page)
            if not steam_id:
                # 账户页面解析失败时，使用登录过程中拿到的 steamid
                try:
                    steam_id = str(steam.steamid)
                except Exception:
                    steam_id = None
            if not steam_id:
                return {"type": "no_id"}

            # 2. 读取资料原值（提交表单时必须原样回填其它字段）
            edit_info_html = await steam.request(
                AccountManagerApp.PROFILE_EDIT_INFO_URL.format(steam_id=steam_id))
            config = AccountManagerApp._extract_profile_edit_config(edit_info_html) or {}
            current = {
                'personaName': config.get('strPersonaName', ''),
                'real_name': config.get('strRealName', ''),
                'summary': config.get('strSummary', ''),
            }

            if not config:
                # 被限流时 edit/info 返回的是 HTTP 429 错误页（没有 profile_edit_config），
                # 这时绝不能提交表单，否则真实姓名/概要/位置/自定义URL 会被空值覆盖
                if AccountManagerApp._is_rate_limited(edit_info_html):
                    return {"type": "rate_limited", "rate_limited": True}
                # 未读到资料原值，宁可不改也不能提交空表单
                return {"type": "read_failed"}

            # 内容没有变化就不用提交（用户明确点确定时仍然提交）
            if not force and all(current[key] == value for key, value in changes.items()):
                return {"type": "no_change", "current": current}

            # 超长内容会被 Steam 静默截断，这里提前提示
            for key, value in changes.items():
                size = len(value.encode('utf-8'))
                if size > AccountManagerApp.PROFILE_LIMITS[key]:
                    print(f"[{username}] 提示: {lang['edit_profile_field_labels'][key]} {size} 字节, "
                          f"超过 {AccountManagerApp.PROFILE_LIMITS[key]} 字节, 可能会被Steam截断")

            # 3. 组装表单：除要改的字段外全部回填原值
            cookies = await steam.cookies('steamcommunity.com')
            session_id = cookies.get('sessionid') or cookies.get('sessionID')
            if not session_id:
                return {"type": "no_session"}

            location = config.get('LocationData') or {}
            form = {
                'sessionID': session_id,
                'type': 'profileSave',
                'personaName': current['personaName'],
                'real_name': current['real_name'],
                'summary': current['summary'],
                # ↓↓↓ 以下字段保持原值，缺失会被 Steam 当成"清空"
                'country': location.get('locCountryCode', ''),
                'state': location.get('locStateCode', ''),
                'city': location.get('locCityCode', ''),
                'customURL': config.get('strCustomURL', ''),
                'weblink_1_title': '',
                'weblink_1_url': '',
                'weblink_2_title': '',
                'weblink_2_url': '',
                'weblink_3_title': '',
                'weblink_3_url': '',
                'json': 1,
            }
            # 只覆盖本次要改的字段，其余仍是原值
            form.update(changes)

            resp_text = await steam.request(
                AccountManagerApp.PROFILE_EDIT_URL.format(steam_id=steam_id),
                method='POST',
                data=form,
                headers={
                    # 模拟网页表单提交（非必需，但更贴近浏览器行为）
                    'Referer': AccountManagerApp.PROFILE_EDIT_INFO_URL.format(steam_id=steam_id),
                    'Origin': 'https://steamcommunity.com',
                },
            )

            # 4. 解析返回的 JSON
            try:
                result = json.loads(resp_text)
            except Exception:
                if AccountManagerApp._is_rate_limited(resp_text):
                    # 被限流时提交没有生效，可以让下一批重试
                    return {"type": "rate_limited", "rate_limited": True}
                return {"type": "failed", "error": f"返回内容无法解析 {resp_text[:120]!r}"}

            if result.get('success') != 1:
                reason = result.get('errmsg') or result.get('error') or result
                return {"type": "failed", "error": str(reason)}

            # 提交已经成功：后面无论回读成不成功都不再重试（改动已经生效了）
            submitted = True

            # 5. 回读 edit/info 验证实际生效的内容
            verify_html = await steam.request(
                AccountManagerApp.PROFILE_EDIT_INFO_URL.format(steam_id=steam_id))
            verify_config = AccountManagerApp._extract_profile_edit_config(verify_html) or {}
            if not verify_config:
                # 提交已经成功，但回读被限流/失败，无法确认实际生效内容，只能提示手动确认
                reason = lang['edit_profile_rate_limited'] if AccountManagerApp._is_rate_limited(verify_html) else ''
                return {"type": "verify_failed", "error": reason, "changes": changes,
                        "current": current, "submitted": True}

            now = {
                'personaName': verify_config.get('strPersonaName', ''),
                'real_name': verify_config.get('strRealName', ''),
                'summary': verify_config.get('strSummary', ''),
            }

            truncated, mismatched = [], []
            for key, want in changes.items():
                got = now[key]
                if got == want:
                    continue
                # 超长时 Steam 会按字节截断，返回仍是 success，只能靠回读发现
                if got and want.startswith(got):
                    truncated.append(key)
                else:
                    mismatched.append((key, want, got))

            # 改了昵称的话，顺手确认一下公开资料页也生效（该页有缓存，只在控制台提示）
            if 'personaName' in changes:
                profile_html = await steam.request(
                    AccountManagerApp.PROFILE_URL.format(steam_id=steam_id))
                public_name = AccountManagerApp._extract_public_persona_name(profile_html)
                if public_name and public_name != now['personaName']:
                    print(f"[{username}] 提示: 公开资料页显示 {public_name}(可能有缓存)")

            if mismatched:
                return {"type": "failed", "changes": changes, "current": current,
                        "mismatched": mismatched}
            return {"type": "success", "changes": changes, "current": current, "now": now,
                    "truncated": truncated}

        except Exception as e:
            if submitted:
                # 提交已经成功，只是后面的回读/确认请求出错：改动其实已经生效，不再重试
                return {"type": "verify_failed", "error": str(e), "changes": changes,
                        "current": current, "submitted": True}
            return {"type": "login_failed", "error": str(e)}
        finally:
            await AccountManagerApp._close_steam_session(steam)

    @staticmethod
    async def _edit_profile_batch(accounts, persona_name=None, real_name=None, summary=None,
                                  force=False, progress_callback=None, retry_callback=None):
        """
        分批并发修改多个账号的个人资料

        每批并发 PROFILE_BATCH_SIZE 个账号，失败（登录/读取/限流）的账号挪到下一批重试，
        提交成功的账号不再处理；被 Steam 限流(HTTP 429)时等 RATE_LIMIT_DELAY 秒再做下一批。
        单个账号失败不影响后续账号，结果按账号名收集后由调用方统一汇总。

        :param accounts: [(账号, 密码), ...]
        :return: {账号: _edit_profile_single 返回的结果字典}
        """
        async def worker(username, password):
            return await AccountManagerApp._edit_profile_single(
                username=username,
                password=password,
                persona_name=persona_name,
                real_name=real_name,
                summary=summary,
                force=force
            )

        results, _failed = await AccountManagerApp._run_batches(
            accounts,
            worker,
            batch_size=AccountManagerApp.PROFILE_BATCH_SIZE,
            batch_delay=AccountManagerApp.PROFILE_BATCH_DELAY,
            retry_count=AccountManagerApp.RETRY_COUNT,
            rate_limit_delay=AccountManagerApp.RATE_LIMIT_DELAY,
            retryable_results=AccountManagerApp.PROFILE_RETRYABLE_RESULTS,
            error_result_type='login_failed',
            progress_callback=progress_callback,
            retry_callback=retry_callback
        )
        return results

    def edit_profile_selected(self):
        """修改所有选中账号的个人资料（名称/真实姓名/概要）"""
        selected_accounts = [
            acc for acc in self.accounts_data if acc.get('selected_state', False)
        ]
        if not selected_accounts:
            messagebox.showinfo(lang['edit_profile'], lang['check_cooldown_no_accounts'], parent=self.root)
            return
        if getattr(self, '_editing_profile', False):
            # 上一次修改还在读条中，不重复打开
            return

        total = len(selected_accounts)
        # 弹窗里预填的是第一个账号的当前资料，标题里写明会应用到多少个账号
        account_obj = selected_accounts[0]
        self._editing_profile = True
        try:
            dlg = ProfileEditDialog(
                self.root,
                lang['edit_profile_title'].format(count=total),
                limits=AccountManagerApp.PROFILE_LIMITS
            )
        finally:
            self._editing_profile = False

        # 点取消或直接关闭窗口 => result 为 None，不执行任何修改
        if dlg.result is None:
            return
        # 上一次批量修改还在读条时不再重复发起，避免请求过密被Steam限流
        if getattr(self, '_profile_editing', False):
            return
        self._profile_editing = True

        # 三个字段作为一个整体应用到全部选中账号（None 表示不改该项，这里由弹窗保证是具体值）
        persona_name, real_name, summary = dlg.result
        accounts_to_edit = [(acc['account'], acc['password']) for acc in selected_accounts]

        # 读条窗口：账号数是确定的，用确定进度条比来回滚动的读条更能说明进度
        progress_win, progress_bar, progress_label = self._create_progress_window(
            lang['edit_profile_progress'])
        progress_bar['maximum'] = total
        progress_bar['value'] = 0
        progress_label.config(text=lang['edit_profile_progress_text'].format(done=0, total=total))

        result_queue = queue.Queue()

        def run_edit():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                def on_progress(done, total_count, username, result):
                    result_queue.put(('progress', done, total_count, username, result))

                def on_retry(username, attempt):
                    print(f"重试中: {username} 第{attempt}次")
                    result_queue.put(('retry', username, attempt))

                results = loop.run_until_complete(
                    AccountManagerApp._edit_profile_batch(
                        accounts_to_edit,
                        persona_name=persona_name,
                        real_name=real_name,
                        summary=summary,
                        force=True,
                        progress_callback=on_progress,
                        retry_callback=on_retry
                    )
                )
                result_queue.put(('done', results))
            except Exception as e:
                result_queue.put(('error', str(e)))
            finally:
                loop.close()

        threading.Thread(target=run_edit, daemon=True).start()

        def poll_queue():
            try:
                while True:
                    msg = result_queue.get_nowait()
                    if msg[0] == 'progress':
                        _, done, total_count, _username, _result = msg
                        progress_bar['value'] = done
                        progress_label.config(text=lang['edit_profile_progress_text'].format(
                            done=done, total=total_count))
                    elif msg[0] == 'retry':
                        self._append_retry_title_suffix(progress_win)
                    elif msg[0] == 'done':
                        self._profile_editing = False
                        self._remove_retry_title_suffix(progress_win)
                        self._allow_progress_window_close(progress_win)
                        progress_win.destroy()
                        self._on_profile_edit_done(accounts_to_edit, msg[1])
                        return
                    elif msg[0] == 'error':
                        self._profile_editing = False
                        self._remove_retry_title_suffix(progress_win)
                        self._allow_progress_window_close(progress_win)
                        progress_win.destroy()
                        messagebox.showerror(
                            lang['edit_profile_result'],
                            lang['edit_profile_batch_error'].format(error=msg[1]),
                            parent=self.root
                        )
                        return
            except queue.Empty:
                pass
            except tk.TclError:
                # 窗口已被销毁，停止轮询
                return
            self.root.after(100, poll_queue)

        poll_queue()

    def _on_profile_edit_done(self, accounts_to_edit, results):
        """批量修改完成后的提示（成功数量 + 各失败账号的具体原因）"""
        title = lang['edit_profile_result']
        total = len(accounts_to_edit)

        success_accounts = [name for name, _pwd in accounts_to_edit
                            if (results.get(name) or {}).get('type') == 'success']
        # 内容本来就一样，属于正常情况，不计入失败
        unchanged_accounts = [name for name, _pwd in accounts_to_edit
                              if (results.get(name) or {}).get('type') == 'no_change']
        # 已经提交成功、只是回读确认失败：改动其实已经生效，算成功但单独提示一句
        unverified_accounts = [name for name, _pwd in accounts_to_edit
                               if (results.get(name) or {}).get('type') == 'verify_failed']
        failed = [(name, results.get(name) or {}) for name, _pwd in accounts_to_edit
                  if (results.get(name) or {}).get('type')
                  not in ('success', 'no_change', 'verify_failed')]

        lines = []
        done_count = len(success_accounts) + len(unchanged_accounts) + len(unverified_accounts)
        if success_accounts or unverified_accounts:
            lines.append(lang['edit_profile_success'].format(count=done_count))
            # Steam 会按字节静默截断超长内容，回读不一致时补一句提示
            truncated_fields = []
            for name in success_accounts:
                for key in (results[name].get('truncated') or []):
                    if key not in truncated_fields:
                        truncated_fields.append(key)
            if truncated_fields:
                lines.append(lang['edit_profile_truncated'].format(
                    fields="、".join(lang['edit_profile_field_labels'][key]
                                     for key in truncated_fields)).strip())

        if unverified_accounts:
            lines.append(lang['edit_profile_unverified'].format(
                accounts=", ".join(unverified_accounts)))

        if unchanged_accounts:
            if total == 1:
                lines.append(lang['edit_profile_no_change'].format(account=unchanged_accounts[0]))
            else:
                lines.append(lang['edit_profile_no_change_multi'].format(
                    accounts=", ".join(unchanged_accounts)))

        if failed:
            # 单个账号失败时直接给原因（和一次只改一个账号时的提示一致）；
            # 批量时先给一句总数，再逐条列出失败原因
            if total > 1:
                if done_count:
                    lines.append(lang['edit_profile_partial'].format(
                        success=done_count, failed=len(failed)))
                else:
                    lines.append(lang['edit_profile_all_failed'].format(count=len(failed)))
                lines.append(lang['edit_profile_failed_accounts'])
            for name, result in failed:
                lines.append(AccountManagerApp._describe_profile_edit_failure(name, result))

        # 全部账号都没改动时按普通提示展示，其余情况用警告/错误提示
        if not lines:
            lines.append(lang['edit_profile_empty'])

        message = "\n".join(lines)
        parent = self.root
        if failed:
            # 有账号失败：单个账号失败时沿用原来的错误弹窗，批量失败时用警告框列出明细
            if total == 1:
                messagebox.showerror(title, message, parent=parent)
            else:
                messagebox.showwarning(title, message, parent=parent)
        else:
            messagebox.showinfo(title, message, parent=parent)

    @staticmethod
    def _describe_profile_edit_failure(account, result):
        """把一个账号的失败结果翻译成一行说明文字"""
        result_type = result.get('type')
        if result_type == 'rate_limited':
            return lang['edit_profile_failed'].format(
                account=account, details=lang['edit_profile_rate_limited'])
        if result_type == 'read_failed':
            return f"[{account}] {lang['edit_profile_read_failed']}"
        if result_type == 'no_session':
            return f"[{account}] {lang['edit_profile_no_session']}"
        if result_type == 'no_id':
            return lang['edit_profile_failed'].format(
                account=account, details=lang['edit_profile_no_id'])
        if result_type == 'login_failed':
            return lang['edit_profile_failed'].format(
                account=account,
                details=lang['edit_profile_login_failed'].format(error=result.get('error', '')))
        if result_type == 'verify_failed':
            return lang['edit_profile_failed'].format(
                account=account,
                details=lang['edit_profile_verify_failed'].format(
                    error=result.get('error') or lang['edit_profile_empty']))
        if result_type == 'failed':
            if result.get('mismatched'):
                # 提交成功但回读不一致（例如自定义URL被占用等）
                details = "; ".join(
                    f"{lang['edit_profile_field_labels'][key]} -> "
                    f"{AccountManagerApp._brief_text(got)}"
                    for key, _want, got in result['mismatched']
                )
            else:
                details = result.get('error') or ''
            return lang['edit_profile_failed'].format(account=account, details=details)
        return lang['edit_profile_failed'].format(account=account, details=str(result))

    # ========== 原有方法 ==========

    def batch_set_remarks(self):
        selected_accounts = [
            acc for acc in self.accounts_data if acc.get('selected_state', False)
        ]
        if not selected_accounts:
            return

        remark_text = self.batch_remarks_var.get()
        if remark_text == lang['remarks_options'][0]:
            remark_text = ""

        # 批量设置备注，只更新UI和保存一次
        account_set = {acc['account'] for acc in selected_accounts}
        for acc in self.accounts_data:
            if acc['account'] in account_set:
                acc['remarks'] = remark_text
        for orig_acc in self.original_data:
            if orig_acc['account'] in account_set:
                orig_acc['remarks'] = remark_text

        self.batch_remarks_var.set("")
        self.filter_treeview()
        self.save_data()
        messagebox.showinfo(lang['batch_remark_success'], lang['batch_remark_msg'].format(count=len(selected_accounts), remark=remark_text), parent=self.root)

    def batch_move_selected(self):
        """批量移动选中的账号"""
        selected_accounts = [
            acc for acc in self.accounts_data if acc.get('selected_state', False)
        ]
        if not selected_accounts:
            return

        move_option = self.batch_move_var.get()
        move_options = lang['move_options']

        if move_option not in move_options:
            return

        # 保存选中账号的原始顺序
        selected_accounts_ordered = [acc for acc in self.accounts_data if acc.get('selected_state', False)]

        if move_option == move_options[1]:  # 上移一位
            for i, acc in enumerate(self.accounts_data):
                if acc.get('selected_state', False) and i > 0:
                    # 找到前一个非选中账号，与之交换
                    for j in range(i - 1, -1, -1):
                        if not self.accounts_data[j].get('selected_state', False):
                            self.accounts_data[i], self.accounts_data[j] = self.accounts_data[j], self.accounts_data[i]
                            break
            direction = lang['move_up']
        elif move_option == move_options[2]:  # 下移一位
            for i in range(len(self.accounts_data) - 1, -1, -1):
                if self.accounts_data[i].get('selected_state', False) and i < len(self.accounts_data) - 1:
                    # 找到后一个非选中账号，与之交换
                    for j in range(i + 1, len(self.accounts_data)):
                        if not self.accounts_data[j].get('selected_state', False):
                            self.accounts_data[i], self.accounts_data[j] = self.accounts_data[j], self.accounts_data[i]
                            break
            direction = lang['move_down']
        elif move_option == move_options[3]:  # 置顶
            # 将选中的账号移到前面，保持相对顺序
            unselected = [acc for acc in self.accounts_data if not acc.get('selected_state', False)]
            self.accounts_data = selected_accounts_ordered + unselected
            direction = lang['move_top']
        elif move_option == move_options[4]:  # 置底
            # 将选中的账号移到最后，保持相对顺序
            unselected = [acc for acc in self.accounts_data if not acc.get('selected_state', False)]
            self.accounts_data = unselected + selected_accounts_ordered
            direction = lang['move_bottom']
        else:
            return  # 不操作

        # 同步更新original_data的顺序
        original_dict = {acc['account']: acc for acc in self.original_data}
        self.original_data = [original_dict[acc['account']].copy() for acc in self.accounts_data]
        for i, acc in enumerate(self.original_data):
            acc['account'] = self.accounts_data[i]['account']
            acc['password'] = self.accounts_data[i]['password']
            acc['available_time'] = self.accounts_data[i]['available_time']
            acc['remarks'] = self.accounts_data[i]['remarks']
            acc['others'] = self.accounts_data[i].get('others', '')
            acc['selected_state'] = self.accounts_data[i].get('selected_state', False)

        self.batch_move_var.set("")
        self.filter_treeview()
        self.save_data()
        messagebox.showinfo(lang['move_success'], lang['move_msg'].format(count=len(selected_accounts), direction=direction), parent=self.root)


if __name__ == '__main__':
    root = tk.Tk()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    window_width = 1200
    window_height = 600
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    AccountManagerApp(root)
    check_for_update(root, root.title(), lang, version)
    root.mainloop()