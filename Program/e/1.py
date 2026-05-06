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