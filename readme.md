# 说明

用于管理CS2无额外验证登录账号, 一键登录, 批量查询VAC状态冷却时间

# 即将推出

1. 更优美的界面

2. 云存储相关

3. 批量查询/更改主页信息和头像

# 使用前安装外部库

- `pip install pypinyin`
- `pip install pysteamauth`

# 打包说明

1. 安装 PyInstaller

- `pip install pyinstaller`

2. 打包

- `pyinstaller --noconsole --onefile ./Program/账号管理系统.py`

- `dist/` 目录：存放最终生成的可执行文件