#!/usr/bin/env python3
"""Sync Discord avatar images and stable revision data for GitHub Pages.

Needs DISCORD_BOT_TOKEN. Saves assets/avatars/{slug}.png and versions.json.
No changes are written if the Discord avatar has not changed.
"""
import hashlib
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets' / 'avatars'
USERS = {
    'corner': '397722270891769858',
    'sosowaffle': '664976847402172417',
    'gangsi': '444120879526445066',
}


def fetch(url, headers=None):
    headers = headers or {'User-Agent': 'CornerArtMuseum/1.0'}
    req = Request(url, headers=headers)
    with urlopen(req, timeout=25) as response:
        return response.read(4_000_001)


def main():
    token = os.environ.get('DISCORD_BOT_TOKEN', '').strip()
    if not token:
        raise SystemExit('Missing DISCORD_BOT_TOKEN in GitHub Actions Secrets.')

    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / 'versions.json'
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if not isinstance(manifest, dict):
            manifest = {}
    except (FileNotFoundError, ValueError):
        manifest = {}

    updated = 0
    for slug, user_id in USERS.items():
        try:
            raw = fetch(
                f'https://discord.com/api/v10/users/{user_id}',
                {'Authorization': 'Bot ' + token, 'User-Agent': 'CornerArtMuseum/1.0'},
            )
            user = json.loads(raw)
            avatar_hash = user.get('avatar')
            if not avatar_hash:
                print(f'{slug}: no custom avatar; current fallback retained')
                continue
            img_path = OUT / f'{slug}.png'
            if manifest.get(slug) == avatar_hash and img_path.exists():
                print(f'{slug}: unchanged')
                continue
            data = fetch(f'https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png?size=256')
            if len(data) > 4_000_000 or not data.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('Invalid/oversized PNG response')
            if not img_path.exists() or img_path.read_bytes() != data:
                img_path.write_bytes(data)
            manifest[slug] = avatar_hash
            updated += 1
            print(f'{slug}: avatar refreshed')
        except (HTTPError, URLError, ValueError, OSError, KeyError) as ex:
            print(f'{slug}: update failed: {type(ex).__name__} ({ex})')

    ordered = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    if not manifest_path.exists() or manifest_path.read_text(encoding='utf-8') != ordered:
        manifest_path.write_text(ordered, encoding='utf-8')
    print(f'Avatar updates: {updated}; revision map entries: {len(manifest)}')


if __name__ == '__main__':
    main()
