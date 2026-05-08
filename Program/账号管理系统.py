import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import datetime
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
from bs4 import BeautifulSoup

from dialogs import DaysHoursDialog, DateTimeDialog, AddAccountDialog, CustomRemarkDialog, ExportMethodDialog
from language import LANGUAGES
from utils import get_system_language, check_for_update, get_pinyin_initial_abbr

version = "2.3.5"

current_lang = get_system_language()
lang = LANGUAGES[current_lang]

class AccountManagerApp:
    # 添加"序号"列作为第一列
    COLUMNS = ("index", "select", "account", "password", "status", "remarks", "shortcut", "available_time", "others")
    COLUMN_WIDTHS = {
        "index": 25, "select": 50, "account": 100, "password": 100, "status": 70,
        "remarks": 100, "shortcut": 100, "available_time": 120, "others": 150
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
        
        # 删除按钮和查询VAC按钮先不显示
        self.delete_btn = ttk.Button(search_frame, text=lang['delete_selected'], command=self.delete_selected)
        self.vac_btn = ttk.Button(search_frame, text=lang['check_cooldown_selected'], command=self.check_cooldown_selected)
        ttk.Button(search_frame, text=lang['select_all_toggle'], command=self.select_all_toggle).pack(side=tk.RIGHT, padx=5)
        # 默认不显示删除按钮和VAC按钮
        self.delete_btn.pack_forget()
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
            self.batch_remarks_combo.pack(side=tk.RIGHT, padx=5)
            self.batch_remarks_btn.pack(side=tk.RIGHT, padx=5)
            self.batch_move_combo.pack(side=tk.RIGHT, padx=5)
            self.batch_move_btn.pack(side=tk.RIGHT, padx=5)
            self.vac_btn.pack(side=tk.RIGHT, padx=5)
            self.delete_btn.pack(side=tk.RIGHT, padx=5)
        else:
            self.batch_remarks_combo.pack_forget()
            self.batch_remarks_btn.pack_forget()
            self.batch_move_combo.pack_forget()
            self.batch_move_btn.pack_forget()
            self.vac_btn.pack_forget()
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


    # ========== 冷却/VAC查询 ==========

    BATCH_SIZE = 5
    BATCH_DELAY = 3
    RETRY_COUNT = 1  # 重试次数为1

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
    async def _check_single_cooldown(username, password, retry_callback=None):
        """查询单个账号的冷却/VAC状态，支持重试"""
        steam = None
        for attempt in range(AccountManagerApp.RETRY_COUNT + 1):
            try:
                steam = Steam(username, password)
                await steam.login_to_steam()

                # 检查VAC冷却时间
                r = await steam.request(
                    "https://help.steampowered.com/zh-cn/wizard/HelpWithGameIssue/?appid=730&issueid=131"
                )
                soup = BeautifulSoup(r, "html.parser")
                if t := soup.select_one(".help_game_cooldown_expirationtime"):
                    cooldown_text = t.text.strip()
                    cooldown_local = AccountManagerApp._parse_steam_time_to_local(r, cooldown_text)
                    return {"type": "cooldown", "time": cooldown_local}

                # 检查VAC状态
                r_vac = await steam.request("https://help.steampowered.com/zh-cn/wizard/VacBans")
                if "Counter-Strike 2" in r_vac:
                    return {"type": "vac"}
                return {"type": "no_ban"}
            except Exception as e:
                if attempt < AccountManagerApp.RETRY_COUNT:
                    if retry_callback:
                        retry_callback(username, attempt + 1)
                    # 还有重试机会，等待后重试
                    await asyncio.sleep(AccountManagerApp.BATCH_DELAY)
                else:
                    # 重试次数用尽，返回失败
                    return {"type": "fail", "error": str(e)}
            finally:
                # 确保 session 被关闭
                if steam:
                    try:
                        await steam.client_session.close()
                    except Exception:
                        pass

    @staticmethod
    async def _check_cooldown_batch(accounts, batch_size=5, batch_delay=3, progress_callback=None, retry_callback=None):
        """批量查询冷却/VAC状态"""
        results = {}
        total = len(accounts)
        done = 0
        for i in range(0, total, batch_size):
            batch = accounts[i:i + batch_size]
            tasks = [
                AccountManagerApp._check_single_cooldown(u, p, retry_callback=retry_callback)
                for u, p in batch
            ]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for (username, _), result in zip(batch, batch_results):
                if isinstance(result, BaseException):
                    result = {"type": "fail", "error": str(result)}
                results[username] = result
                done += 1
                if progress_callback:
                    progress_callback(done, total, username, result)
                # 如果查询失败，立即中断查询
                if result.get('type') == 'fail':
                    return None  # 返回None表示中断
            if i + batch_size < total:
                await asyncio.sleep(batch_delay)
        return results

    def check_cooldown_selected(self):
        """查询选中账号的冷却状态"""
        selected_accounts = [
            acc for acc in self.accounts_data if acc.get('selected_state', False)
        ]
        accounts_to_check = [(acc['account'], acc['password']) for acc in selected_accounts]

        # 创建进度窗口
        progress_win = tk.Toplevel(self.root)
        progress_win.title(lang['check_cooldown_progress'])
        progress_win.geometry("380x60")
        progress_win.resizable(False, False)
        progress_win.transient(self.root)
        progress_win.grab_set()

        # 居中到主窗口
        progress_win.update_idletasks()
        pw, ph = 380, 60
        mx = self.root.winfo_x()
        my = self.root.winfo_y()
        mw = self.root.winfo_width()
        mh = self.root.winfo_height()
        progress_win.geometry(f"{pw}x{ph}+{mx + (mw - pw)//2}+{my + (mh - ph)//2}")

        progress_bar = ttk.Progressbar(progress_win, length=350, mode='determinate', maximum=len(accounts_to_check))
        progress_bar.pack(pady=15)

        result_queue = queue.Queue()

        def run_check():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            def on_progress(done, total, username, result):
                result_queue.put(('progress', done, total, username, result))

            def on_retry(username, attempt):
                print(f"重试中: {username} 第{attempt}次")
                result_queue.put(('retry', username, attempt))

            results = loop.run_until_complete(
                AccountManagerApp._check_cooldown_batch(
                    accounts_to_check,
                    batch_size=AccountManagerApp.BATCH_SIZE,
                    batch_delay=AccountManagerApp.BATCH_DELAY,
                    progress_callback=on_progress,
                    retry_callback=on_retry
                )
            )
            result_queue.put(('done', results))
            loop.close()

        threading.Thread(target=run_check, daemon=True).start()

        def poll_queue():
            try:
                while True:
                    msg = result_queue.get_nowait()
                    if msg[0] == 'progress':
                        _, done, _total, username, result = msg
                        progress_bar['value'] = done
                        if result.get('type') == 'fail':
                            # 查询失败（重试后仍失败）立即弹窗提示并中断
                            self._remove_retry_title_suffix(progress_win)
                            progress_win.destroy()
                            messagebox.showerror(
                                lang['check_cooldown_fail'],
                                lang['check_cooldown_fail_msg'],
                                parent=self.root
                            )
                            return
                    elif msg[0] == 'retry':
                        self._append_retry_title_suffix(progress_win)
                    elif msg[0] == 'done':
                        self._remove_retry_title_suffix(progress_win)
                        progress_win.destroy()
                        if msg[1] is None:
                            # 查询被中断（已有失败账号处理）
                            return
                        self._apply_cooldown_results(msg[1], selected_accounts)
                        return
            except queue.Empty:
                pass
            except tk.TclError:
                # 窗口已被销毁，停止轮询
                return
            self.root.after(100, poll_queue)

        poll_queue()

    def _apply_cooldown_results(self, results, selected_accounts):
        """将查询结果应用到账号数据中"""
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
                dt = datetime.datetime.strptime(result['time'], "%Y-%m-%d %H:%M")
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