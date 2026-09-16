# -*- coding: utf-8 -*-
"""
Steam 个人资料修改参考（昵称 / 真实姓名 / 概要）
================================================

技术细节说明：
1. 使用 pysteamauth 登录 Steam，登录后 pysteamauth 会把各站点的 Cookie
   （steamcommunity.com / store.steampowered.com / help.steampowered.com）都取回来，
   改资料需要的是 steamcommunity.com 的 sessionid。
2. 先访问 https://store.steampowered.com/account/ 解析出 Steam ID（64位）；
   若页面解析失败，则退回使用登录过程中拿到的 steam.steamid。
3. 再访问 https://steamcommunity.com/profiles/{STEAM_ID}/edit/info 读取「编辑个人资料」页面，
   页面中 <div id="profile_edit_config" data-profile-edit="{...}"> 里的 JSON 保存着
   当前资料原值：strPersonaName(昵称) / strRealName(真实姓名) / strSummary(概要) /
   LocationData(位置) / strCustomURL(自定义URL)。
   注意属性里的引号是 &quot; 形式，需要先 HTML 反转义再 json.loads。
4. 昵称、真实姓名、概要用的是同一个表单，都提交到
   https://steamcommunity.com/profiles/{STEAM_ID}/edit，POST 字段（与网页版一致）：
       sessionID=<会话ID>
       type=profileSave
       personaName=<昵称>        ← 改昵称就填新昵称
       real_name=<真实姓名>      ← 改真实姓名就填新真实姓名
       summary=<概要>            ← 改概要就填新概要
       country / state / city / customURL       ← 必须原样回填
       weblink_1~3_title / weblink_1~3_url      ← 网页版表单固定带的空字段
       json=1
   重点：表单是"整份资料覆盖提交"，没带上的字段会被 Steam 当成清空。
   所以必须先把原值读出来，只把要改的字段换成新值，其它原样回填
   （node-steamcommunity 的 editProfile 也是这么做的）。
5. 返回内容是 JSON：
       成功 {"success":1,"errmsg":""}
       失败 {"success":2,"errmsg":"..."}（例如内容非法、自定义URL被占用等）
   注意：内容超长时返回依然是 success，但 Steam 会按 UTF-8 字节把内容静默截断，
   所以改完必须回读确认实际生效的值。
5.1 限流：改资料相关页面请求过密时，Steam 直接返回 HTTP 429 错误页
   （<title>Steam Community :: Error</title>，正文含 too many requests），
   这时 edit/info 里没有 profile_edit_config。
   绝对不能在这种情况下继续提交表单，否则没读到的字段（真实姓名/概要/位置/自定义URL）
   会被当成空值覆盖掉；脚本里对 429 的处理是等待 RATE_LIMIT_DELAY 秒后重试。
6. 回读验证：再次请求 edit/info，比对 strPersonaName / strRealName / strSummary，
   这才是资料的权威值（改动后立即可见，基本没有缓存问题）。
7. 解析 HTML 全部使用字符串查找 / 正则表达式，不依赖 BeautifulSoup。
8. 提醒：Steam 对频繁改昵称/改资料有风控，短时间内多次修改可能触发交易限制，
   批量修改时建议拉大批次间隔（BATCH_DELAY）。
9. 运行环境：请使用 Python 3.13 运行。本机默认的 Python 3.14 下 pysteamauth 依赖的
   pydantic 1.9.0 解析最终登录结果会失败，报
   "'FinalizeLoginStatus' object has no attribute 'transfer_info'"
   （登录请求本身是成功的，只是解析崩了，换 3.13 即可正常登录）。

运行方式：python Steam个人资料名称修改参考.py

实测结论（已用示例账号跑通）：
- 读取资料 / 改昵称 / 改真实姓名 / 改概要 / 回读验证 全部可用；
- 成功时返回 {"success":1,"errmsg":""}，紧接着回读 edit/info 就能看到新内容，基本没有延迟；
- 真实姓名和概要就是同一份表单里的另外两个字段，改昵称时顺带把它们的原值提交即可保持不变；
- 内容超长不会报错（返回仍是 success），但会被 Steam 按 UTF-8 字节静默截断，
  截断点按字符边界，中文不会被截成半个字。实测上限（见下方 LIMITS）：
      昵称 personaName : 32  字节
      真实姓名 real_name: 64  字节
      概要 summary      : 4096 字节
  实测数据：60 个中文（180 字节）的真实姓名只存下 21 个字（63 字节）；
  60 个 ASCII 字符（60 字节）的真实姓名则完整存下；
  2000 个中文（6000 字节）的概要只存下 1365 个字（4095 字节）。
- 单个账号连续修改（改完立刻改回原值）没有遇到冷却；
- 改资料比查询接口娇气：短时间内大量 edit/info + profileSave 请求会被 Steam 限流，
  实测 3 个账号并发、每个账号十来次请求就会开始返回 HTTP 429 错误页。
  所以修改资料的默认参数取 BATCH_SIZE=1 / BATCH_DELAY=10，宁可慢也别被限流。
- 被限流时脚本会等待后重试，并且宁可不改也不提交空表单（ALLOW_EMPTY_FALLBACK 默认关闭）。
"""

from pysteamauth.auth import Steam
import asyncio
import html as html_lib
import json
import re

# (账号, 密码, 新昵称, 新真实姓名, 新概要)
# 每一项写 None  => 保持原值不动（也不会被清空）
# 每一项写 ""    => 清空该项
# 三项全是 None  => 只读取当前资料，不做任何修改（安全自检模式）
accounts = [
    ("vnhba91594", "VF1911148", "赵波1337", "赵波1337", "赵波1337"),
    ("vowng68945", "jrek60883I", "赵波1337", "赵波1337", "赵波1337"),
    ("vrjao98598", "hmnt06422O", "赵波1337", "赵波1337", "赵波1337"),
]

BATCH_SIZE = 2  # 每批并发数（改资料比查询娇气，建议 1；实测并发 3 个账号就会触发限流）
BATCH_DELAY = 3  # 批次间等待秒数（改资料建议 10 秒以上）
RETRY_COUNT = 1  # 超时重试次数
RATE_LIMIT_DELAY = 30  # 被 Steam 限流(HTTP 429)后的等待秒数

# 读不到资料原值时，是否仍然强行提交修改
# 开启后会把没读到的字段（真实姓名 / 概要 / 位置 / 自定义URL）清空，一般保持关闭
ALLOW_EMPTY_FALLBACK = False

# 各项长度上限：按 UTF-8 字节算（中文一个字 3 字节），超长会被 Steam 静默截断
# 数值为实测值：昵称 32 字节 / 真实姓名 64 字节 / 概要 4096 字节
LIMITS = {
    'personaName': 32,
    'real_name': 64,
    'summary': 4096,
}

FIELD_LABELS = {
    'personaName': '昵称',
    'real_name': '真实姓名',
    'summary': '概要',
}

# 个人资料相关地址
ACCOUNT_URL = "https://store.steampowered.com/account/"
PROFILE_EDIT_INFO_URL = "https://steamcommunity.com/profiles/{steam_id}/edit/info"
PROFILE_EDIT_URL = "https://steamcommunity.com/profiles/{steam_id}/edit"
PROFILE_URL = "https://steamcommunity.com/profiles/{steam_id}/"

# 请求过于频繁时 Steam 返回 HTTP 429，页面是错误页而不是正常资料页
RATE_LIMIT_MARKERS = ('Steam Community :: Error', 'too many requests')


def is_rate_limited(html_content):
    """判断返回的内容是不是 Steam 的限流错误页（HTTP 429）"""
    text = (html_content or '').lower()
    return any(marker.lower() in text for marker in RATE_LIMIT_MARKERS)


def extract_steam_id(html_content):
    """
    从账户页面提取Steam ID
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


def extract_profile_edit_config(html_content):
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


def extract_persona_name(html_content):
    """从个人资料页提取当前昵称（公开页面效果）"""
    match = re.search(r'class="actual_persona_name">(.*?)</span>', html_content, re.S)
    if match:
        return html_lib.unescape(match.group(1)).strip()
    # 备用：页面标题 "Steam Community :: 昵称"
    match = re.search(r'<title>Steam Community :: (.*?)</title>', html_content, re.S)
    if match:
        return html_lib.unescape(match.group(1)).strip()
    return None


def split_account(item):
    """兼容 (账号, 密码, 新昵称) 与 (账号, 密码, 新昵称, 新真实姓名, 新概要) 两种写法"""
    username, password = item[0], item[1]
    rest = list(item[2:]) + [None] * (3 - len(item[2:]))
    return username, password, rest[0], rest[1], rest[2]


def brief(value, limit=40):
    """输出用：过长的内容截断显示，空值显示为 (空)"""
    if value == '':
        return '(空)'
    return value if len(value) <= limit else value[:limit] + '…'


async def close_steam(steam):
    """
    关闭 pysteamauth 底层的 aiohttp 会话，避免 Unclosed client session 警告
    关闭后把 _session 置空，否则对象回收时 BaseRequestStrategy.__del__ 会访问
    session.connector（已为 None）而抛出 Exception ignored
    """
    try:
        strategy = getattr(steam, '_requests', None)
        session = getattr(strategy, '_session', None)
        if session is not None:
            await session.close()
        if strategy is not None:
            strategy._session = None
    except Exception:
        pass


async def edit_profile(username, password, persona_name=None, real_name=None, summary=None):
    """
    修改（或只读取）单个账号的个人资料
    :param persona_name: 新昵称
    :param real_name:    新真实姓名
    :param summary:      新概要
    三个参数：None=保持原值不动，""=清空该项，其它=改成该内容；
    三个都为 None 时只读取当前资料，不做任何修改
    """
    changes = {
        'personaName': persona_name,
        'real_name': real_name,
        'summary': summary,
    }
    changes = {key: value for key, value in changes.items() if value is not None}

    steam = None
    for attempt in range(RETRY_COUNT + 1):
        try:
            steam = Steam(username, password)
            await steam.login_to_steam()

            # 1. 取 Steam ID（64位）
            account_page = await steam.request(ACCOUNT_URL)
            steam_id = extract_steam_id(account_page)
            if not steam_id:
                # 账户页面解析失败时，使用登录过程中拿到的 steamid
                try:
                    steam_id = str(steam.steamid)
                except Exception:
                    steam_id = None
            if not steam_id:
                return f"[{username}] 无法获取Steam ID"

            # 2. 读取资料原值（提交表单时必须原样回填其它字段）
            edit_info_html = await steam.request(PROFILE_EDIT_INFO_URL.format(steam_id=steam_id))
            config = extract_profile_edit_config(edit_info_html) or {}
            current = {
                'personaName': config.get('strPersonaName', ''),
                'real_name': config.get('strRealName', ''),
                'summary': config.get('strSummary', ''),
            }

            # 三个字段都是 None => 只做读取，不改资料
            if not changes:
                return (f"[{username}] 当前昵称: {brief(current['personaName'])}"
                        f" | 真实姓名: {brief(current['real_name'])}"
                        f" | 概要: {brief(current['summary'])}")

            if not config:
                # 被限流时 edit/info 返回的是 HTTP 429 错误页（没有 profile_edit_config），
                # 这时绝不能提交表单，否则真实姓名/概要/位置/自定义URL 会被空值覆盖
                if is_rate_limited(edit_info_html):
                    if attempt < RETRY_COUNT:
                        print(f"[{username}] 被Steam限流(429), {RATE_LIMIT_DELAY}秒后重试")
                        await asyncio.sleep(RATE_LIMIT_DELAY)
                        continue
                    return f"[{username}] 被Steam限流(429), 请拉大 BATCH_DELAY / 降低 BATCH_SIZE 后重试"
                if not ALLOW_EMPTY_FALLBACK:
                    return f"[{username}] 未读取到资料原值, 已跳过修改(避免清空真实姓名/概要/位置)"

            # 内容没有变化就不用提交
            if all(current[key] == value for key, value in changes.items()):
                return f"[{username}] 内容无需修改: " + "; ".join(
                    f"{FIELD_LABELS[key]}: {brief(current[key])}" for key in changes)

            # 超长内容会被 Steam 静默截断，这里提前提示
            for key, value in changes.items():
                size = len(value.encode('utf-8'))
                if size > LIMITS[key]:
                    print(f"[{username}] 提示: {FIELD_LABELS[key]} {size} 字节, "
                          f"超过 {LIMITS[key]} 字节, 可能会被Steam截断")

            # 3. 组装表单：除要改的字段外全部回填原值
            cookies = await steam.cookies('steamcommunity.com')
            session_id = cookies.get('sessionid') or cookies.get('sessionID')
            if not session_id:
                return f"[{username}] 未取到 sessionid, 无法提交表单"

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
                PROFILE_EDIT_URL.format(steam_id=steam_id),
                method='POST',
                data=form,
                headers={
                    # 模拟网页表单提交（非必需，但更贴近浏览器行为）
                    'Referer': PROFILE_EDIT_INFO_URL.format(steam_id=steam_id),
                    'Origin': 'https://steamcommunity.com',
                },
            )

            # 4. 解析返回的 JSON
            try:
                result = json.loads(resp_text)
            except Exception:
                if is_rate_limited(resp_text):
                    # 被限流时提交没有生效，可以等待后重试
                    if attempt < RETRY_COUNT:
                        print(f"[{username}] 提交被Steam限流(429), {RATE_LIMIT_DELAY}秒后重试")
                        await asyncio.sleep(RATE_LIMIT_DELAY)
                        continue
                    return f"[{username}] 提交被Steam限流(429), 请拉大 BATCH_DELAY / 降低 BATCH_SIZE 后重试"
                return f"[{username}] 修改失败: 返回内容无法解析 {resp_text[:120]!r}"

            if result.get('success') != 1:
                reason = result.get('errmsg') or result.get('error') or result
                return f"[{username}] 修改失败: {reason}"

            changed_desc = "; ".join(
                f"{FIELD_LABELS[key]}: {brief(current[key])} -> {brief(value)}"
                for key, value in changes.items()
            )

            # 5. 回读 edit/info 验证实际生效的内容
            verify_html = await steam.request(PROFILE_EDIT_INFO_URL.format(steam_id=steam_id))
            verify_config = extract_profile_edit_config(verify_html) or {}
            if not verify_config:
                # 提交已经成功，但回读被限流/失败，无法确认实际生效内容，只能提示手动确认
                reason = "(被Steam限流429)" if is_rate_limited(verify_html) else ""
                return f"[{username}] 已提交成功(返回{result}), 但回读失败{reason}, 请稍后手动确认"
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
                    truncated.append(f"{FIELD_LABELS[key]}被截断为 {brief(got)}"
                                     f"({len(got.encode('utf-8'))}字节)")
                else:
                    mismatched.append(f"{FIELD_LABELS[key]} 期望 {brief(want)}, 实际 {brief(got)}")

            # 改了昵称的话，顺手确认一下公开资料页也生效（该页有缓存，只作为提示）
            public_note = ''
            if 'personaName' in changes:
                profile_html = await steam.request(PROFILE_URL.format(steam_id=steam_id))
                public_name = extract_persona_name(profile_html)
                if public_name and public_name != now['personaName']:
                    public_note = f"; 公开资料页显示 {brief(public_name)}(可能有缓存)"

            if mismatched:
                return f"[{username}] 已提交成功(返回{result}), 但回读不一致: " + "; ".join(mismatched)
            if truncated:
                return f"[{username}] 修改成功: {changed_desc} ({'; '.join(truncated)}){public_note}"
            return f"[{username}] 修改成功: {changed_desc}{public_note}"

        except Exception as e:
            if attempt < RETRY_COUNT:
                print(f"[{username}] 第 {attempt + 1}/{RETRY_COUNT} 次失败，{BATCH_DELAY}秒后重试")
                await asyncio.sleep(BATCH_DELAY)
            else:
                return f"[{username}] 重试{RETRY_COUNT}次仍失败({e})(请尝试VPN/TUN代理/路由模式游戏加速器)"
        finally:
            if steam:
                await close_steam(steam)


async def main():
    """主函数：批量处理账号的资料修改"""
    for i in range(0, len(accounts), BATCH_SIZE):
        batch = accounts[i:i + BATCH_SIZE]
        tasks = [edit_profile(*split_account(acc)) for acc in batch]
        results = await asyncio.gather(*tasks)
        for r in results:
            print(r)
        if i + BATCH_SIZE < len(accounts):
            await asyncio.sleep(BATCH_DELAY)


if __name__ == '__main__':
    asyncio.run(main())
