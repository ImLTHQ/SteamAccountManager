from pysteamauth.auth import Steam
from bs4 import BeautifulSoup
import asyncio

BATCH_SIZE = 5  # 每批并发数
BATCH_DELAY = 3  # 批次间等待秒数

async def check(username, password):
    steam = Steam(username, password)
    await steam.login_to_steam()

    # 检查VAC冷却时间
    r = await steam.request(
        "https://help.steampowered.com/zh-cn/wizard/HelpWithGameIssue/?appid=730&issueid=131"
    )
    soup = BeautifulSoup(r, "html.parser")
    if t := soup.select_one(".help_game_cooldown_expirationtime"):
        return f"{username}: 冷却结束时间: {t.text.strip()}"

    # 检查VAC状态
    r_vac = await steam.request("https://help.steampowered.com/zh-cn/wizard/VacBans")

    if "Counter-Strike 2" in r_vac:
        return f"{username}: VAC封禁"
    return f"{username}: 无封禁"

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