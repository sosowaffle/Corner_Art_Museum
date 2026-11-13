#!/usr/bin/env python3
"""Fetch public avatar pictures for three configured Discord users.

Requires DISCORD_BOT_TOKEN in GitHub Actions. Token is never written to disk.
Each image is saved in assets/avatars/{slug}.png, static for GitHub Pages.
"""
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = Path(__file__).resolve().parent
OUT = BASE / 'assets' / 'avatars'
USERS = {
    'corner': '397722270891769858',
    'sosowaffle': '664976847402172417',
    'gangsi': '444120879526445066',
}

def fetch(url, headers=None):
    req = Request(url, headers=headers or {'User-Agent': 'CornerArtMuseum/1.0'})
    with urlopen(req, timeout=20) as r:
        data = r.read(3_000_000)
        if len(data) >= 3_000_000:
            raise ValueError('avatar too large')
        return data

def main():
    token=os.environ.get('DISCORD_BOT_TOKEN', '').strip()
    if not token:
        raise SystemExit('DISCORD_BOT_TOKEN is missing. Put it in repository Actions Secrets.')
    OUT.mkdir(parents=True, exist_ok=True)
    count=0
    for slug,uid in USERS.items():
        try:
            raw=fetch('https://discord.com/api/v10/users/'+uid,
                {'Authorization':'Bot '+token, 'User-Agent':'CornerArtMuseum/1.0'})
            user=json.loads(raw)
            hash_=user.get('avatar')
            if not hash_:
                print(slug, 'no custom avatar; keep current fallback')
                continue
            image=fetch(f'https://cdn.discordapp.com/avatars/{uid}/{hash_}.png?size=256')
            if not image.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('invalid PNG avatar response')
            (OUT/(slug+'.png')).write_bytes(image)
            count+=1
            print('saved avatar for',slug)
        except (HTTPError, URLError, ValueError, KeyError) as e:
            print('avatar failed for',slug,repr(e)[:160])
    print('avatars updated:',count)

if __name__=='__main__': main()
