#!/usr/bin/env python3
"""Apply a well-formed public GitHub title edit request, recording nickname and GitHub author.

Called ONLY by GitHub Actions on issues.opened. No code from the issue is evaluated.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
GALLERY = ROOT / 'gallery.json'
OVERRIDES = ROOT / 'title-overrides.json'
ISSUE = ROOT / '.incoming_title_issue.json'

def main():
    event = json.loads(ISSUE.read_text(encoding='utf-8'))
    issue = event.get('issue') or {}
    title = issue.get('title') or ''
    if not title.startswith('[작품 제목 변경] '):
        print('Not a title edit issue.');return 0
    if issue.get('user',{}).get('type') == 'Bot':
        print('Bot changes ignored');return 0
    body = issue.get('body') or ''
    fields = {}
    for line in body.splitlines():
        m = re.match(r'^\s*(작품 ID|새 제목|수정자 닉네임):\s*(.*)$',line)
        if m and m.group(1) not in fields:
            fields[m.group(1)] = m.group(2).strip()
    artid, new_title, nickname = [fields.get(k,'') for k in ('작품 ID','새 제목','수정자 닉네임')]
    # Allow only known, exact ID; forbid markup, line breaks, and whitespace-only input.
    if not artid or len(artid)>130 or not re.fullmatch(r'[0-9A-Za-z_-]+',artid):
        print('Invalid artwork ID');return 0
    if not (1<=len(new_title)<=100 and 1<=len(nickname)<=40) or any(c in new_title+nickname for c in '<>\r\n\x00'):
        print('Invalid title or nickname');return 0
    if not GALLERY.exists():
        print('Missing gallery database');return 0
    artworks = json.loads(GALLERY.read_text(encoding='utf-8')).get('artworks',[])
    if not any(str(a.get('id'))==artid for a in artworks):
        print('Artwork not found');return 0
    overrides = json.loads(OVERRIDES.read_text(encoding='utf-8')) if OVERRIDES.exists() else {}
    old = overrides.get(artid,{})
    previous = old.get('history', [])
    if old:
        previous = (previous + [{k:v for k,v in old.items() if k!='history'}])[-30:]
    overrides[artid] = {'title':new_title, 'nickname':nickname,
                        'githubUser':issue.get('user',{}).get('login','unknown'),
                        'issue':issue.get('number'), 'updatedAt':datetime.now(timezone.utc).isoformat(),
                        'history':previous}
    OVERRIDES.write_text(json.dumps(overrides, ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Saved title override:',artid,'by',nickname)
    return 0

if __name__ == '__main__':
    sys.exit(main())
