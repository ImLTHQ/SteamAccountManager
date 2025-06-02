import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import datetime
import json
import uuid

class AccountManagerApp:
    # Class-level constants for UI configuration
    COLUMNS = ("select", "account", "password", "status", "available_time", "remarks", "shortcut")
    HEADINGS_MAP = {
        "select": "选择", "account": "账号", "password": "密码",
        "status": "状态", "available_time": "可用时间", "remarks": "备注",
        "shortcut": "快捷"
    }
    COLUMN_WIDTHS = {
        "select": 50, "account": 150, "password": 150, "status": 80,
        "available_time": 160, "remarks": 100, "shortcut": 100 # Increased width for time display
    }
    COLUMN_ANCHORS = {
        "select": tk.CENTER, "status": tk.CENTER, "available_time": tk.CENTER,
        "remarks": tk.CENTER, "shortcut": tk.CENTER
    }

    def __init__(self, root_window):
        self.root = root_window
        self.root.title("账号管理系统")
        self.root.geometry("1050x600")

        self.accounts_data = []
        self.data_file = "accounts_data.json"

        # Variables for drag selection
        self._drag_start_item = None
        self._last_selected_items_in_drag = set()
        self._selection_mode_toggle = None

        self.setup_ui() # This method now creates self.tree
        self._configure_treeview_style() # Now self.tree exists

        self.load_data()

    def _configure_treeview_style(self):
        """Configures custom style for Treeview row tags."""
        style = ttk.Style()
        
        # Configure how the background and foreground colors change when selected
        # Set background to 'white' and foreground to 'black' for selected rows
        style.map('Treeview',
                  background=[('selected', 'white')],
                  foreground=[('selected', 'black')]) 

        # Configure custom tags for row backgrounds (these will apply when not selected)
        self.tree.tag_configure("可用", background="lightgreen")
        self.tree.tag_configure("不可用", background="salmon")

    def setup_ui(self):
        """Sets up the main user interface elements."""
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)

        # Consolidated button creation
        buttons_data = [
            ("导入TXT", self.import_txt),
            ("导出TXT", self.export_txt),
            ("手动添加", self.manual_add_account_dialog),
            ("保存", self.save_data),
            ("刷新", self.refresh_treeview),
        ]
        for text, command in buttons_data:
            ttk.Button(top_frame, text=text, command=command).pack(side=tk.LEFT, padx=5)

        search_frame = ttk.Frame(self.root, padding="10")
        search_frame.pack(fill=tk.X)

        self.show_available_only_var = tk.BooleanVar()
        ttk.Checkbutton(search_frame, text="只显示可用", variable=self.show_available_only_var, command=self.filter_treeview).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="删除选中", command=self.delete_selected).pack(side=tk.RIGHT, padx=5)
        ttk.Button(search_frame, text="全选/取消全选", command=self.select_all_toggle).pack(side=tk.RIGHT, padx=5)

        tree_frame = ttk.Frame(self.root, padding="10")
        tree_frame.pack(expand=True, fill=tk.BOTH)

        self.tree = ttk.Treeview(tree_frame, columns=self.COLUMNS, show="headings")

        for col_id in self.COLUMNS:
            self.tree.heading(col_id, text=self.HEADINGS_MAP[col_id])
            self.tree.column(col_id, width=self.COLUMN_WIDTHS[col_id], anchor=self.COLUMN_ANCHORS.get(col_id, tk.W))

        self.tree.pack(expand=True, fill=tk.BOTH, side=tk.LEFT)
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Event bindings
        self.tree.bind("<ButtonPress-1>", self.on_tree_button_press)
        self.tree.bind("<B1-Motion>", self.on_tree_drag_motion)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_button_release)
        self.tree.bind("<Button-3>", self.on_tree_right_click)
        self.tree.bind("<Double-1>", self.on_tree_double_click)

    def get_account_by_tree_id(self, tree_item_id):
        """Retrieves an account object from accounts_data by its tree_id."""
        return next((acc for acc in self.accounts_data if acc.get('tree_id') == tree_item_id), None)

    def _set_account_selection_state(self, account_obj, state):
        """Helper to set the selected state of an account and update its Treeview row."""
        if account_obj.get('selected_state', False) != state:
            account_obj['selected_state'] = state
            if account_obj.get('tree_id'):
                # When programmatically setting selected_state, also update the Treeview's selection
                if state:
                    self.tree.selection_add(account_obj['tree_id'])
                else:
                    self.tree.selection_remove(account_obj['tree_id'])
                # However, we still need to update the checkbox character.
                self.update_row_checkbox_only(account_obj['tree_id'], account_obj)

    def update_row_checkbox_only(self, tree_item_id, account_obj):
        """Updates only the 'select' column character in the Treeview row."""
        select_char = "☑" if account_obj.get('selected_state', False) else "☐"
        current_values = list(self.tree.item(tree_item_id, 'values'))
        current_values[0] = select_char
        self.tree.item(tree_item_id, values=current_values)

    def on_tree_button_press(self, event):
        """Handles mouse button press for drag selection initiation and single clicks on '选择' column."""
        item_id = self.tree.identify_row(event.y)
        column_id_str = self.tree.identify_column(event.x)
        
        # Determine the column header text if a valid column is identified
        column_header_text = ""
        if column_id_str:
            column_header_text = self.tree.heading(column_id_str)['text']

        # Reset drag state at the beginning of a new click/drag
        self._drag_start_item = None
        self._last_selected_items_in_drag = set()
        self._selection_mode_toggle = None # Will determine if we're selecting or deselecting during drag

        if not item_id: # Clicked on empty space
            # If Ctrl/Cmd not pressed, clear all UI selections
            if not (event.state & 0x0004 or event.state & 0x0008):
                for acc in self.accounts_data:
                    self._set_account_selection_state(acc, False) # This will also clear UI selection
            return

        # Handle '选择' column click for direct toggle and initiate drag selection
        if column_header_text == "选择":
            account_obj = self.get_account_by_tree_id(item_id)
            if account_obj:
                # Toggle internal state AND update UI selection
                current_state = account_obj.get('selected_state', False)
                self._set_account_selection_state(account_obj, not current_state)
                
                # IMPORTANT: Only initiate drag if click is in the "选择" column
                self._drag_start_item = item_id
                self._selection_mode_toggle = not current_state # Determine mode for drag
                self._last_selected_items_in_drag.add(item_id)
            return # Exit after handling '选择' column click

        # Handle single left-click for copying on "账号" or "密码" columns
        # This part will now only execute if the click is NOT in the "选择" column
        if column_header_text in ("账号", "密码"):
            # A small delay to ensure it's not the start of a drag from the same spot,
            # though for account/password columns, drag selection isn't intended.
            # This is more robust against accidental double-clicks or very fast clicks.
            self.root.after(150, lambda: self._handle_single_click_copy(item_id, column_header_text))
            
            # Allow default Treeview selection behavior for these columns
            # The default selection behavior for the row where the click occurred should proceed.
            pass # No specific action needed here beyond what the Treeview handles by default

    def _handle_single_click_copy(self, item_id, column_header_text):
        """Helper to handle single-click copy after a small delay to differentiate from drag."""
        # Check if a drag has started from this item. If so, do not copy.
        # This check is crucial to prevent copy on a drag initiation, though for account/password
        # columns, we don't *initiate* drag selection for checkboxes. This is more of a safeguard.
        if self._drag_start_item: 
            return 

        account_obj = self.get_account_by_tree_id(item_id)
        if not account_obj: return

        if column_header_text == "账号":
            content_to_copy = account_obj['account']
        elif column_header_text == "密码":
            content_to_copy = account_obj['password']
        else:
            return # Not an account or password column

        self.root.clipboard_clear()
        self.root.clipboard_append(content_to_copy)
        self.root.update()
        # Optional: Add a visual feedback like a temporary tooltip "已复制"

    def on_tree_drag_motion(self, event):
        """Handles mouse drag motion for selecting/deselecting items."""
        if not self._drag_start_item: return # No drag initiated from "选择" column

        current_item = self.tree.identify_row(event.y)
        if not current_item: return # Not over a valid row

        all_visible_items = list(self.tree.get_children())
        if not all_visible_items: return

        try:
            start_index = all_visible_items.index(self._drag_start_item)
            current_index = all_visible_items.index(current_item)
        except ValueError:
            return

        min_index, max_index = sorted((start_index, current_index))
        items_in_current_drag_range = set(all_visible_items[min_index : max_index + 1])

        # Deselect items that were previously in drag but are no longer
        items_to_deselect_from_prev_drag = self._last_selected_items_in_drag - items_in_current_drag_range
        for prev_item_id in items_to_deselect_from_prev_drag:
            acc = self.get_account_by_tree_id(prev_item_id)
            if acc:
                self._set_account_selection_state(acc, not self._selection_mode_toggle)
        
        # Apply selection mode to items within the current drag range
        for item_id in items_in_current_drag_range:
            acc = self.get_account_by_tree_id(item_id)
            if acc:
                self._set_account_selection_state(acc, self._selection_mode_toggle)
        
        self._last_selected_items_in_drag = items_in_current_drag_range

    def on_tree_button_release(self, _event):
        """Resets drag selection state on mouse button release."""
        self._drag_start_item = None
        self._last_selected_items_in_drag = set()
        self._selection_mode_toggle = None

    def on_tree_double_click(self, event):
        """Handles double-click events on Treeview cells."""
        item_id = self.tree.identify_row(event.y)
        column_id_str = self.tree.identify_column(event.x)
        column_header_text = self.tree.heading(column_id_str)['text']
        
        if not item_id: return
        account_obj = self.get_account_by_tree_id(item_id)
        if not account_obj: return
        
        if column_header_text == "备注":
            current_remarks = account_obj.get('remarks', '')
            new_remarks = simpledialog.askstring("编辑备注", "请输入新备注:", initialvalue=current_remarks, parent=self.root)
            if new_remarks is not None:
                self.set_remarks(account_obj, new_remarks)
        elif column_header_text == "快捷":
            self.apply_shortcut(account_obj, "reset")

    def on_tree_right_click(self, event):
        """Handles right-click events on Treeview cells, showing context menus."""
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell": return

        column_id_str = self.tree.identify_column(event.x)
        item_id = self.tree.identify_row(event.y)
        if not item_id: return

        account_obj = self.get_account_by_tree_id(item_id)
        if not account_obj: return

        column_header_text = self.tree.heading(column_id_str)['text']
        
        # *** MODIFICATION START ***
        # Remove automatic selection for "备注" and "快捷" right-clicks
        # The line below ensures that a right-click will select the row IF it's not remarks/shortcut,
        # or if Ctrl/Cmd is pressed (for multi-selection).
        if column_header_text not in ("备注", "快捷") and not (event.state & 0x0004 or event.state & 0x0008):
            for acc in self.accounts_data: # Deselect others in data and UI
                self._set_account_selection_state(acc, False)
            self._set_account_selection_state(account_obj, True) # Select clicked item in data and UI
        # *** MODIFICATION END ***

        if column_header_text == "备注":
            self._show_remarks_menu(event, account_obj)
        elif column_header_text == "快捷":
            self._show_shortcut_menu(event, account_obj)
        elif column_header_text == "账号":
            self.root.clipboard_clear()
            self.root.clipboard_append(account_obj['account'])
            self.root.update()
        elif column_header_text == "密码":
            self.root.clipboard_clear()
            self.root.clipboard_append(account_obj['password'])
            self.root.update()

    def _show_shortcut_menu(self, event, account_obj):
        """Displays the right-click context menu for the '快捷' column."""
        shortcut_menu = tk.Menu(self.root, tearoff=0)
        shortcut_menu.add_command(label="立即可用", command=lambda: self.apply_shortcut(account_obj, "reset"))
        shortcut_menu.add_separator()
        shortcut_menu.add_command(label="20小时后", command=lambda: self.apply_shortcut(account_obj, "delta", hours=20))
        shortcut_menu.add_command(label="3天后", command=lambda: self.apply_shortcut(account_obj, "delta", days=3))
        shortcut_menu.add_command(label="7天后", command=lambda: self.apply_shortcut(account_obj, "delta", days=7))
        shortcut_menu.add_command(label="14天后", command=lambda: self.apply_shortcut(account_obj, "delta", days=14))
        shortcut_menu.add_command(label="30天后", command=lambda: self.apply_shortcut(account_obj, "delta", days=30))
        
        try:
            shortcut_menu.tk_popup(event.x_root, event.y_root)
        finally:
            shortcut_menu.grab_release()

    def _show_remarks_menu(self, event, account_obj):
        """Displays the right-click context menu for the '备注' column."""
        remarks_menu = tk.Menu(self.root, tearoff=0)
        remarks_menu.add_command(label="一级", command=lambda: self.set_remarks(account_obj, "一级"))
        remarks_menu.add_command(label="二级", command=lambda: self.set_remarks(account_obj, "二级"))
        remarks_menu.add_command(label="十级", command=lambda: self.set_remarks(account_obj, "十级"))
        remarks_menu.add_command(label="清空", command=lambda: self.set_remarks(account_obj, ""))
        try:
            remarks_menu.tk_popup(event.x_root, event.y_root)
        finally:
            remarks_menu.grab_release()

    def set_remarks(self, account_obj, remark_text):
        """Sets the remarks for an account and updates the Treeview."""
        account_obj['remarks'] = remark_text
        self.filter_treeview() # Re-filter and re-populate to reflect remarks change

    def _update_account_status_and_time(self, account_obj, new_available_time_dt=None):
        """Updates an account's status and available time."""
        if new_available_time_dt is None:
            try:
                available_dt = datetime.datetime.strptime(account_obj['available_time'], "%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                available_dt = datetime.datetime.min # Treat as very old if format is bad
        else:
            available_dt = new_available_time_dt

        account_obj['available_time'] = available_dt.strftime("%Y-%m-%d %H:%M")
        account_obj['status'] = "可用" if available_dt <= datetime.datetime.now() else "不可用"

    def apply_shortcut(self, account_obj, action_type, hours=0, days=0):
        """Applies a shortcut action (reset, add time) to an account."""
        now = datetime.datetime.now()
        new_available_time_dt = None

        if action_type == "reset":
            new_available_time_dt = now
        elif action_type == "delta":
            new_available_time_dt = now + datetime.timedelta(days=days, hours=hours)
        
        if new_available_time_dt:
            self._update_account_status_and_time(account_obj, new_available_time_dt)
            
            # Move the account to the top of the accounts_data list
            original_index = -1
            for i, acc in enumerate(self.accounts_data):
                if acc['id'] == account_obj['id']:
                    original_index = i
                    break
            
            if original_index != -1:
                moved_account = self.accounts_data.pop(original_index)
                self.accounts_data.insert(0, moved_account)

            self.filter_treeview() # Re-filter and re-populate to reflect status change and new order

    def update_row_in_treeview(self, tree_item_id, account_obj):
        """Updates a single row in the Treeview based on the account object's data.
            The selection highlight is handled by the Treeview itself."""
        select_char = "☑" if account_obj.get('selected_state', False) else "☐"
        
        status_tag = account_obj['status']
        
        account_obj.setdefault('remarks', '')
        
        # Calculate and display remaining available time for the 'shortcut' column
        display_shortcut = ""
        try:
            available_dt = datetime.datetime.strptime(account_obj['available_time'], "%Y-%m-%d %H:%M")
            now = datetime.datetime.now()
            if available_dt > now:
                time_left = available_dt - now
                days = time_left.days
                seconds_in_hour = 3600
                hours = time_left.seconds // seconds_in_hour
                
                # Format the display string
                if days > 0:
                    display_shortcut = f"{days}天{hours}小时"
                elif hours > 0:
                    display_shortcut = f"{hours}小时"
                else:
                    display_shortcut = "不足1小时"
        except (ValueError, TypeError):
            display_shortcut = "" # If time format is bad, display blank
            
        self.tree.item(tree_item_id, values=(
            select_char,
            account_obj['account'],
            account_obj['password'],
            account_obj['status'],
            account_obj['available_time'],
            account_obj['remarks'],
            display_shortcut # Use the calculated display_shortcut
        ), tags=(status_tag,))


    def populate_treeview(self, data_to_display=None):
        """Populates the Treeview with account data."""
        # Saving current selections for reapplication is more complex with dynamic content.
        # For simplicity in this example, we'll clear and repopulate without re-selecting.
        # If preserving selections is critical, you'd need to store the unique IDs
        # of selected accounts and re-select them by ID after repopulating.
        
        for item in self.tree.get_children():
            self.tree.delete(item)

        source_data = data_to_display if data_to_display is not None else self.accounts_data

        items_to_reselect_in_ui = [] # To reapply UI selection after population

        for acc_data in source_data:
            self._update_account_status_and_time(acc_data) # Update status before displaying
            
            select_char = "☑" if acc_data.get('selected_state', False) else "☐"
            status_tag = acc_data['status']
            
            # Ensure default values for display
            acc_data.setdefault('remarks', '')

            # Calculate and display remaining available time for the 'shortcut' column
            display_shortcut = ""
            try:
                available_dt = datetime.datetime.strptime(acc_data['available_time'], "%Y-%m-%d %H:%M")
                now = datetime.datetime.now()
                if available_dt > now:
                    time_left = available_dt - now
                    days = time_left.days
                    seconds_in_hour = 3600
                    hours = time_left.seconds // seconds_in_hour
                    
                    if days > 0:
                        display_shortcut = f"{days}天{hours}小时"
                    elif hours > 0:
                        display_shortcut = f"{hours}小时"
                    else:
                        display_shortcut = "不足1小时"
            except (ValueError, TypeError):
                display_shortcut = "" # If time format is bad, display blank
            
            tree_item_id = self.tree.insert("", tk.END, values=(
                select_char,
                acc_data['account'],
                acc_data['password'],
                acc_data['status'],
                acc_data['available_time'],
                acc_data['remarks'],
                display_shortcut # Use the calculated display_shortcut
            ), tags=(status_tag,))
            acc_data['tree_id'] = tree_item_id

            if acc_data.get('selected_state', False):
                items_to_reselect_in_ui.append(tree_item_id)
        
        # Reapply UI selection based on stored selected_state
        self.tree.selection_set(*items_to_reselect_in_ui)


    def filter_treeview(self, _event=None):
        """Filters the Treeview based on the 'show available only' checkbox."""
        show_available = self.show_available_only_var.get()
        filtered_data = []
        for acc in self.accounts_data:
            self._update_account_status_and_time(acc) # Update status before filtering
            match_status = (not show_available or (show_available and acc['status'] == "可用"))
            if match_status:
                filtered_data.append(acc)
        self.populate_treeview(filtered_data)


    def _add_new_account_entry(self, account, password):
        """Helper to add a new account entry if it's not a duplicate."""
        if not any(acc['account'] == account for acc in self.accounts_data):
            default_available_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            new_acc = {
                'id': str(uuid.uuid4()), 'selected_state': False,
                'account': account, 'password': password, 'status': "可用",
                'available_time': default_available_time,
                'shortcut': None, # Default to None (blank display) for shortcut
                'remarks': ''
            }
            self.accounts_data.append(new_acc)
            return True
        return False


    def import_txt(self):
        """Imports account data from a selected TXT file."""
        filepath = filedialog.askopenfilename(
            title="导入TXT文件",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*")),
            parent=self.root
        )
        if not filepath: return
        try:
            new_accounts_count = 0
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if "---" in line:
                        account, password = line.split("---", 1)
                        if self._add_new_account_entry(account.strip(), password.strip()):
                            new_accounts_count += 1

            if new_accounts_count > 0:
                messagebox.showinfo("导入成功", f"成功导入 {new_accounts_count} 个新账号。", parent=self.root)
            else:
                messagebox.showinfo("导入提示", "没有新的账号被导入（可能已存在或文件格式不正确）。", parent=self.root)
            self.filter_treeview()
        except Exception as e:
            messagebox.showerror("导入错误", f"导入文件失败: {e}", parent=self.root)

    def manual_add_account_dialog(self):
        """Opens a dialog for manual account entry."""
        dialog = ManualAddAccountDialog(self.root)
        if dialog.new_accounts_data:
            new_accounts_count = 0
            for acc_info in dialog.new_accounts_data:
                account, password = acc_info
                if self._add_new_account_entry(account, password):
                    new_accounts_count += 1

            if new_accounts_count > 0:
                messagebox.showinfo("添加成功", f"成功添加 {new_accounts_count} 个新账号。", parent=self.root)
            elif dialog.new_accounts_data: # Only show if some input was provided but no new accounts added
                messagebox.showinfo("添加提示", "没有新的账号被添加（可能已存在）。", parent=self.root)
            self.filter_treeview()


    def save_data(self):
        """Saves the current account data to a JSON file."""
        data_to_save = []
        for acc in self.accounts_data:
            acc_copy = acc.copy()
            acc_copy.pop('tree_id', None) # Remove temporary tree_id before saving
            data_to_save.append(acc_copy)
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=4)
            messagebox.showinfo("保存成功", f"数据已保存到 {self.data_file}", parent=self.root)
        except Exception as e:
            messagebox.showerror("保存失败", f"保存数据失败: {e}", parent=self.root)

    def load_data(self):
        """Loads account data from the JSON file."""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                loaded_entries = json.load(f)
                self.accounts_data = []
                for entry in loaded_entries:
                    entry.setdefault('id', str(uuid.uuid4()))
                    entry.setdefault('selected_state', False)
                    entry.setdefault('status', '可用')
                    entry.setdefault('available_time', datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
                    entry.setdefault('shortcut', None) # Set default shortcut to None for blank display
                    entry.setdefault('remarks', '')
                    # Remove old/deprecated keys if they exist
                    entry.pop('delay_days', None)
                    entry.pop('delay_hours', None)
                    self.accounts_data.append(entry)
        except FileNotFoundError:
            self.accounts_data = []
        except Exception as e:
            messagebox.showerror("加载错误", f"加载数据失败: {e}", parent=self.root)
            self.accounts_data = []
        self.filter_treeview() # Populate treeview after loading

    def refresh_treeview(self):
        """Refreshes the Treeview display."""
        self.filter_treeview()

    def select_all_toggle(self):
        """Toggles selection for all visible accounts."""
        visible_item_ids = self.tree.get_children()
        if not visible_item_ids: return

        visible_accounts = [self.get_account_by_tree_id(item_id) for item_id in visible_item_ids if self.get_account_by_tree_id(item_id)]
        if not visible_accounts: return
        
        # Determine if all visible are currently selected
        all_currently_selected = all(acc.get('selected_state', False) for acc in visible_accounts)
        new_state = not all_currently_selected

        for acc_obj in visible_accounts:
            self._set_account_selection_state(acc_obj, new_state)


    def delete_selected(self):
        """Deletes all currently selected accounts."""
        selected_accounts_to_delete_ids = {
            acc['id'] for acc in self.accounts_data if acc.get('selected_state', False)
        }
        if not selected_accounts_to_delete_ids:
            messagebox.showinfo("删除选中", "没有选中的账号可删除。", parent=self.root)
            return

        if messagebox.askyesno("确认删除", f"确定要删除选中的 {len(selected_accounts_to_delete_ids)} 个账号吗?", parent=self.root):
            # Efficiently filter out deleted accounts
            self.accounts_data = [
                acc for acc in self.accounts_data if acc['id'] not in selected_accounts_to_delete_ids
            ]
            self.filter_treeview()
            messagebox.showinfo("删除成功", f"{len(selected_accounts_to_delete_ids)} 个账号已删除。", parent=self.root)

    def export_txt(self):
        """Exports all account data to a TXT file."""
        if not self.accounts_data:
            messagebox.showinfo("导出提示", "没有数据可导出。", parent=self.root)
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*")),
            title="导出账号密码到TXT文件",
            parent=self.root
        )
        
        if not filepath: return # User cancelled

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                for acc in self.accounts_data:
                    account = str(acc.get('account', ''))
                    password = str(acc.get('password', ''))
                    f.write(f"{account}---{password}\n")
            messagebox.showinfo("导出成功", f"账号和密码已成功导出到:\n{filepath}", parent=self.root)
        except Exception as e:
            messagebox.showerror("导出失败", f"导出文件失败: {e}", parent=self.root)
            
class ManualAddAccountDialog:
    def __init__(self, parent):
        self.top = tk.Toplevel(parent)
        self.top.title("手动添加账号")
        self.top.geometry("450x350")
        self.top.transient(parent)
        self.top.grab_set()

        self.top.update_idletasks()
        w = self.top.winfo_width()
        h = self.top.winfo_height()
        ws = self.top.winfo_screenwidth()
        hs = self.top.winfo_screenheight()
        x = (ws // 2) - (w // 2)
        y = (hs // 2) - (h // 2)
        self.top.geometry(f"{w}x{h}+{x}+{y}")

        self.new_accounts_data = []

        ttk.Label(self.top, text="请输入账号信息，每行一个账号，格式为：账号---密码", wraplength=430).pack(pady=(10,5))
        example_text = "例如:\nusername1---password1\nusername2---password2"
        ttk.Label(self.top, text=example_text, justify=tk.LEFT).pack(pady=5)

        self.text_area_frame = ttk.Frame(self.top)
        self.text_area_frame.pack(pady=10, padx=10, expand=True, fill=tk.BOTH)
        self.text_area = tk.Text(self.text_area_frame, height=10, width=50)
        
        text_scrollbar = ttk.Scrollbar(self.text_area_frame, orient=tk.VERTICAL, command=self.text_area.yview)
        self.text_area.configure(yscrollcommand=text_scrollbar.set)
        
        self.text_area.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        button_frame = ttk.Frame(self.top)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="添加", command=self.add_accounts).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=self.top.destroy).pack(side=tk.LEFT, padx=10)
        
        self.top.wait_window()

    def add_accounts(self):
        content = self.text_area.get("1.0", tk.END).strip()
        lines = content.split("\n")
        parsed_something = False
        for line in lines:
            line = line.strip()
            if "---" in line:
                account, password = line.split("---", 1)
                if account.strip() and password.strip():
                    self.new_accounts_data.append((account.strip(), password.strip()))
                    parsed_something = True
        
        if not parsed_something and content:
            messagebox.showwarning("格式错误", "请输入正确格式的账号信息 (账号---密码)，且账号和密码不能为空。", parent=self.top)
            self.new_accounts_data = [] # Clear any partially parsed data if format is wrong
            return
        self.top.destroy()

if __name__ == '__main__':
    main_root = tk.Tk()
    app = AccountManagerApp(main_root)
    main_root.mainloop()
