# 说明

用于管理CS2无额外验证登录账号, 一键登录, 批量查询VAC状态冷却时间

[程序下载点我](https://github.com/ImLTHQ/SteamAccountManager/blob/main/dist/%E8%B4%A6%E5%8F%B7%E7%AE%A1%E7%90%86%E7%B3%BB%E7%BB%9F.exe)

## 即将推出

### 1. 更优美的界面

### 2. 在线存储/备份(CF KV)

### 3. 批量查询/更改支持项
- Steam ID
- CS等级
- 升级所需经验
- 优先状态
- 接入国服
- 个人资料名称
- 头像
- 真实姓名
- 自定义URL
- 位置

## 开发者请看

- `pip install pypinyin`
- `pip install pysteamauth`

1. 安装 PyInstaller

- `pip install pyinstaller`

2. 打包

- `pyinstaller --noconsole --onefile ./Program/账号管理系统.py`

- `dist/` 目录：存放最终生成的可执行文件