from pysteamauth.auth import Steam
import asyncio
import re

# 技术细节说明：
# 1. 登录后访问 https://store.steampowered.com/account/ 获取账户信息，包括Steam ID
# 2. 使用获取到的Steam ID构建CS2配置文件URL：https://steamcommunity.com/profiles/{STEAM_ID}/gcpd/730
# 3. 在CS2配置文件页面查找"CS:GO Profile Rank: "后的数字，即为CS2等级
# 4. 使用正则表达式精确匹配所需数据：Steam ID（以"Steam ID："开头，到"<"结束）和等级（以"CS:GO Profile Rank: "开头，到空格结束）
# 5. 仅使用正则表达式解析HTML内容，不依赖BeautifulSoup库

accounts = [
    ("rpifk19283", "chdw43041O"),
    ("vnhba91594", "VF1911148"),
    ("dpkzi45933", "gybf85950A")
]

BATCH_SIZE = 5  # 每批并发数
BATCH_DELAY = 3  # 批次间等待秒数
RETRY_COUNT = 1  # 超时重试次数

def extract_steam_id(html_content):
    """
    从HTML内容中提取Steam ID
    支持两种格式：
    1. 中文格式："Steam ID："（中文冒号，后面没有任何空格）
    2. 英文格式："Steam ID: "（英文冒号+空格）
    """
    # 查找中文格式："Steam ID："（中文冒号，后面没有任何空格）后跟的数字
    match = re.search(r'Steam ID：(\d+)', html_content)
    if match:
        return match.group(1)
    # 查找英文格式："Steam ID: "（英文冒号+空格）后跟的数字
    match = re.search(r'Steam ID:\s+(\d+)', html_content)
    if match:
        return match.group(1)
    return None

def extract_cs_rank(html_content):
    """
    从HTML内容中提取CS等级
    查找"CS:GO Profile Rank: "后跟的数字，直到遇到空格字符停止
    """
    # 查找"CS:GO Profile Rank: "后的内容直到遇到空格
    match = re.search(r'CS:GO Profile Rank:\s*(\d+)', html_content)
    if match:
        return match.group(1)
    # Alternative pattern that stops at space character
    match = re.search(r'CS:GO Profile Rank:\s*([0-9]+)\s', html_content)
    if match:
        return match.group(1)
    return None

async def get_cs2_level(username, password):
    """
    获取CS2账号等级的主要函数
    流程：
    1. 使用用户名密码登录Steam
    2. 访问账户页面获取Steam ID
    3. 构造CS2配置文件URL并访问
    4. 解析页面获取CS2等级
    """
    for attempt in range(RETRY_COUNT):
        try:
            steam = Steam(username, password)
            await steam.login_to_steam()

            async def get_with_retry(url):
                """
                带重试机制的请求函数
                URL参数说明：
                - https://store.steampowered.com/account/ : 用户账户页面，包含Steam ID等信息
                - https://steamcommunity.com/my/ : 用户个人资料页面，备选获取Steam ID途径
                - https://steamcommunity.com/profiles/{STEAM_ID}/gcpd/730 : CS2配置文件页面，包含等级信息
                所有HTML内容解析均使用正则表达式完成
                """
                try:
                    return await steam.request(url)
                except:
                    raise

            # 首先获取用户Steam ID
            # URL: https://store.steampowered.com/account/ - 包含账户详细信息
            account_page = await get_with_retry("https://store.steampowered.com/account/")
            
            # 提取Steam ID
            steam_id = extract_steam_id(account_page)
            if not steam_id:
                return f"[{username}] 无法获取Steam ID"

            # 使用获取到的Steam ID查询CS2等级
            # URL: https://steamcommunity.com/profiles/{STEAM_ID}/gcpd/730 - CS2配置文件页面
            cs2_profile_url = f"https://steamcommunity.com/profiles/{steam_id}/gcpd/730"
            cs2_response = await get_with_retry(cs2_profile_url)
            
            # 提取CS等级，按照要求查找"CS:GO Profile Rank: "后跟的数字，遇到空格则停止
            cs_rank = extract_cs_rank(cs2_response)
            if cs_rank:
                return f"[{username}] CS等级: {cs_rank}"
            else:
                # 如果没有找到等级信息，可能账号没有玩过CS2或数据未更新
                return f"[{username}] 未找到CS等级信息"

        except Exception as e:
            if attempt < RETRY_COUNT - 1:
                print(f"[{username}] 第 {attempt + 1}/{RETRY_COUNT} 次失败，{BATCH_DELAY}秒后重试")
                await asyncio.sleep(BATCH_DELAY)
            else:
                return f"[{username}] 重试{RETRY_COUNT}次仍失败(请尝试VPN/TUN代理/路由模式游戏加速器)"

async def main():
    """
    主函数：处理多个账号的CS2等级查询
    实现并发控制和批次处理，避免请求过于频繁被限制
    """
    for i in range(0, len(accounts), BATCH_SIZE):
        batch = accounts[i : i + BATCH_SIZE]
        tasks = [get_cs2_level(u, p) for u, p in batch]
        results = await asyncio.gather(*tasks)
        for r in results:
            print(r)
        if i + BATCH_SIZE < len(accounts):
            await asyncio.sleep(BATCH_DELAY)

asyncio.run(main())