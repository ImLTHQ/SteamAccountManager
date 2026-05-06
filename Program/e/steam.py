from pysteamauth.auth import Steam
from bs4 import BeautifulSoup
import asyncio

BATCH_SIZE = 5  # 每批并发数
BATCH_DELAY = 3  # 批次间等待秒数
RETRY_COUNT = 3  # 超时重试次数

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
                return f"[{username}] 冷却结束时间 {t.text.strip()}"

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
                return f"[{username}] 重试{RETRY_COUNT}次仍失败"

accounts = [
    ("rpifk19283", "chdw43041O"),# 带冷却
    ("vnhba91594", "VF1911148"),# VAC
    ("baqfy09619", "fltf86954H"),# 新号
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