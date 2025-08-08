import locale
import urllib.request
import pypinyin
from pypinyin import Style

def get_system_language():
    lang, _ = locale.getlocale()
    print(f"检测到的语言: {lang}")
    if lang:
        if lang.startswith('Chinese'):
            return 'Chinese'
        else:
            return 'en'

github_url = "https://raw.githubusercontent.com/ImLTHQ/SteamAccountManager/main/version"
def check_for_update(root, title, lang, version):
    try:
        with urllib.request.urlopen(github_url, timeout=3) as response:
            remote_version = response.read().decode('utf-8-sig').strip()
            if remote_version != version:
                if lang['new_version'] not in title:
                    root.title(title + lang['new_version'])
    except Exception:
        pass

def get_pinyin_initial_abbr(text):
    if not text:
        return ""
    # 处理每个字符的拼音首字母
    initials = []
    for char in text:
        # 获取拼音首字母（忽略声调）
        pinyin_list = pypinyin.pinyin(char, style=Style.FIRST_LETTER, strict=False)
        if pinyin_list and pinyin_list[0]:
            initial = pinyin_list[0][0].upper()  # 转为大写
            initials.append(initial)
        else:
            # 非中文字符直接保留（转为大写）
            initials.append(str(char).upper())
    return ''.join(initials)