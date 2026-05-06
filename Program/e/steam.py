from pysteamauth.auth import Steam
from bs4 import BeautifulSoup
import asyncio


async def check(username, password):
    steam = Steam(username, password)
    await steam.login_to_steam()

    # 检查VAC冷却时间
    r = await steam.request(
        "https://help.steampowered.com/zh-cn/wizard/HelpWithGameIssue/?appid=730&issueid=131"
    )
    soup = BeautifulSoup(r, "html.parser")
    if t := soup.select_one(".help_game_cooldown_expirationtime"):
        print("冷却结束时间:", t.text.strip())

    elif soup.select_one("#error_description"):
        r_vac = await steam.request(
            "https://help.steampowered.com/zh-cn/wizard/HelpWithGame/?appid=730&issueid=122"
        )
        soup_vac = BeautifulSoup(r_vac, "html.parser")
        if "VAC" in soup_vac.get_text("VAC"):
            print("找到")
        else:
            print("未找到")

accounts = [
    ("dpkzi45933", "gybf85950A"),# 带冷却
    ("lnceg06150", "oous39232G"),# VAC
    ("baqfy09619", "fltf86954H"),# 新号
]


async def main():
    tasks = [check(u, p) for u, p in accounts]
    await asyncio.gather(*tasks)


asyncio.run(main())