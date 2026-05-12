from pysteamauth.auth import Steam
from bs4 import BeautifulSoup
import asyncio
import re
import datetime
import pytz

BATCH_SIZE = 5  # 每批并发数
BATCH_DELAY = 3  # 批次间等待秒数
RETRY_COUNT = 1  # 超时重试次数

def parse_steam_time_to_local(html, cooldown_text):
    """将Steam页面显示的冷却时间（太平洋时间）转换为本地时区"""
    # 提取服务器时间戳来判断是PST还是PDT
    match = re.search(r'g_ServerTime\s*=\s*(\d+)', html)
    if not match:
        return cooldown_text
    
    server_timestamp = int(match.group(1))
    server_time = datetime.datetime.fromtimestamp(server_timestamp, tz=datetime.timezone.utc)
    
    # Steam使用太平洋时间 (PST: UTC-8, PDT: UTC-7)
    # PDT时间: 3月第二个周日 2:00 AM 到 11月第一个周日 2:00 AM
    pacific = pytz.timezone('US/Pacific')
    
    # 判断服务器时间在太平洋时区的夏令时状态
    try:
        server_pacific = server_time.astimezone(pacific)
        is_dst = bool(server_pacific.dst())
        utc_offset = -8 if not is_dst else -7
    except:
        utc_offset = -8  # 默认PST
    
    # 解析冷却时间 "6 月 1 日 上午 8:27" -> 太平洋时间
    # 注意：Steam不显示年份，需要根据服务器时间推断
    steam_match = re.match(r'(\d+)\s*月\s*(\d+)\s*日\s*(上午|下午)\s*(\d+):(\d+)', cooldown_text)
    if not steam_match:
        return cooldown_text
    
    month = int(steam_match.group(1))
    day = int(steam_match.group(2))
    period = steam_match.group(3)
    hour = int(steam_match.group(4))
    minute = int(steam_match.group(5))
    
    # 转换为24小时制
    if period == '下午' and hour != 12:
        hour += 12
    elif period == '上午' and hour == 12:
        hour = 0
    
    # 使用服务器时间的年份
    year = server_pacific.year
    
    # 构建太平洋时间的datetime
    pacific_dt = pacific.localize(datetime.datetime(year, month, day, hour, minute))
    
    # 转换为本地时区
    local_tz = datetime.timezone(datetime.timedelta(hours=8))  # 中国时区 UTC+8
    # 实际使用系统本地时区
    local_dt = pacific_dt.astimezone(None)
    
    # 格式化为友好格式
    # 判断是否跨年
    if month < server_pacific.month or (month == server_pacific.month and day < server_pacific.day):
        year += 1
    
    return local_dt.strftime(f"%Y年%m月%d日 %H:%M")

async def check(username, password):
    for attempt in range(RETRY_COUNT):
        try:
            steam = Steam(username, password)
            await steam.login_to_steam()

            async def get_with_retry(url):
                try:
                    return await steam.request(url)
                except:
                    raise

            # 检查VAC冷却时间
            r = await get_with_retry(
                "https://help.steampowered.com/zh-cn/wizard/HelpWithGameIssue/?appid=730&issueid=131"
            )
            soup = BeautifulSoup(r, "html.parser")
            if t := soup.select_one(".help_game_cooldown_expirationtime"):
                cooldown_text = t.text.strip()
                cooldown_local = parse_steam_time_to_local(r, cooldown_text)
                return f"[{username}] 冷却结束时间 {cooldown_local}"

            # 检查VAC状态
            r_vac = await get_with_retry("https://help.steampowered.com/zh-cn/wizard/VacBans")

            if "Counter-Strike 2" in r_vac:
                return f"[{username}] VAC封禁"
            return f"[{username}] 无封禁"
        except:
            if attempt < RETRY_COUNT - 1:
                print(f"[{username}] 第 {attempt + 1}/{RETRY_COUNT} 次失败，{BATCH_DELAY}秒后重试")
                await asyncio.sleep(BATCH_DELAY)
            else:
                return f"[{username}] 重试{RETRY_COUNT}次仍失败(请尝试VPN/TUN代理/路由模式游戏加速器)"

accounts = [
    #("rpifk19283", "chdw43041O"),# 带冷却
    #("vnhba91594", "VF1911148"),# VAC
    #("dpkzi45933", "gybf85950A")# 新号
]


async def main():
    batch_size = 5
    for i in range(0, len(accounts), BATCH_SIZE):
        batch = accounts[i : i + BATCH_SIZE]
        tasks = [check(u, p) for u, p in batch]
        results = await asyncio.gather(*tasks)
        for r in results:
            print(r)
        if i + batch_size < len(accounts):
            await asyncio.sleep(BATCH_DELAY)

asyncio.run(main())