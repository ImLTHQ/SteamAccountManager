from pysteamauth.auth import Steam

async def main():
    steam = Steam(
        login='dpkzi45933', 
        password='gybf85950A',
    )
    
    await steam.login_to_steam()

    await steam.request('https://steamcommunity.com')
    await steam.request('https://store.steampowered.com')
    await steam.request('https://help.steampowered.com')

# 查询账号等级用
# https://store.steampowered.com/account/
# Get SteamID 星号替换成ID
# https://steamcommunity.com/profiles/*/gcpd/730