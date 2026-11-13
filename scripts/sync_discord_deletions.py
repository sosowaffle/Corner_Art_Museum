#!/usr/bin/env python3
"""Conservatively hide Discord-deleted attachments from the published gallery.

Only count a missing message after verifying its source channel/thread is accessible.
Require two independent scheduled runs confirming absence. Preserve local media files.
"""
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
GALLERY = ROOT / 'gallery.json'
STATE = ROOT / 'sync-state.json'
API = 'https://discord.com/api/v10'
BATCH_SIZE = max(1, min(100, int(os.getenv('DELETION_AUDIT_BATCH', '60'))))


def api_get(path, token):
    url = API + path
    for attempt in range(5):
        try:
            with urlopen(Request(url, headers={
                'Authorization': 'Bot ' + token,
                'User-Agent': 'CornerArtMuseum/1.0',
            }), timeout=20) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            if error.code == 429 and attempt < 4:
                try:
                    pause = float(json.loads(error.read()).get('retry_after', 2))
                except (ValueError, TypeError):
                    pause = 2
                time.sleep(min(max(pause, 1), 40))
                continue
            if error.code >= 500 and attempt < 4:
                time.sleep(2 ** attempt)
                continue
            return error.code, None
        except (URLError, TimeoutError) as error:
            if attempt == 4:
                print(f'WARNING: network error {path}: {error}')
                return 0, None
            time.sleep(2 ** attempt)
    return 0, None


def source_for(artwork):
    """Resolve a specific message source; never assume parent forum is its thread."""
    item_id = str(artwork.get('id', ''))
    parts = item_id.split('-')
    if len(parts) != 3 or any(not re.fullmatch(r'\d{15,25}', p) for p in parts):
        return None
    parent, message, attachment = parts
    url = str(artwork.get('messageUrl') or '')
    match = re.match(r'https://discord\.com/channels/(?:\d+|@me)/(\d{15,25})/(\d{15,25})/?$', url)
    if match and match.group(2) == message:
        return match.group(1), message, attachment
    # For standard channels parent is itself the message source.
    # For forum/media channels the original source is the thread ID, which
    # cannot be inferred from an old artwork ID without an authoritative URL.
    return parent, message, attachment


def main():
    token = os.getenv('DISCORD_BOT_TOKEN', '').strip()
    if not token:
        raise SystemExit('Missing DISCORD_BOT_TOKEN')
    gallery = json.loads(GALLERY.read_text(encoding='utf-8'))
    state = json.loads(STATE.read_text(encoding='utf-8'))
    artworks = gallery.get('artworks')
    if not isinstance(artworks, list) or not artworks:
        raise SystemExit('Refusing deletion audit on empty/invalid gallery')
    channel_configs = json.loads((ROOT / 'channels.json').read_text(encoding='utf-8'))
    allowed = {str(c) for c in channel_configs}
    audit = state.setdefault('deletionAudit', {})
    consecutive = audit.setdefault('missingConfirmations', {})
    source_type = {}
    for parent_id in allowed:
        status, info = api_get(f'/channels/{parent_id}', token)
        if status == 200 and isinstance(info, dict):
            source_type[parent_id] = info.get('type')
        else:
            print(f'WARNING: channel {parent_id} not accessible (HTTP {status}), skipping its audit')

    indexed = []
    for artwork in artworks:
        parsed = source_for(artwork)
        if not parsed:
            continue
        parent = str(artwork['id']).split('-')[0]
        if parent not in allowed or parent not in source_type:
            continue
        source, message, attachment = parsed
        # Without a link, old forum/media pieces cannot be audited safely.
        if source_type[parent] in (15, 16) and source == parent:
            continue
        indexed.append((artwork, source, message, attachment))
    indexed.sort(key=lambda rec: str(rec[0]['id']))
    if not indexed:
        print('Audit: no safely verifiable artworks yet (old forum items may lack message URLs).')
        return 0
    offset = int(audit.get('offset') or 0) % len(indexed)
    batch = (indexed + indexed)[offset:offset + min(BATCH_SIZE, len(indexed))]
    audit['offset'] = (offset + len(batch)) % len(indexed)

    source_status = {}
    msg_results = {}
    removed = set()
    inconclusive = 0
    missing_first = 0
    for artwork, source, message, attachment in batch:
        item_id = artwork['id']
        if source not in source_status:
            status, _ = api_get(f'/channels/{source}', token)
            source_status[source] = status
        if source_status[source] != 200:
            consecutive.pop(item_id, None)
            inconclusive += 1
            continue
        key = (source, message)
        if key not in msg_results:
            msg_results[key] = api_get(f'/channels/{source}/messages/{message}', token)
        status, payload = msg_results[key]
        missing = False
        if status == 404:  # The source itself was just verified accessible.
            missing = True
        elif status == 200 and isinstance(payload, dict):
            missing = attachment not in {
                str(a.get('id')) for a in payload.get('attachments', [])
            }
        else:
            consecutive.pop(item_id, None)
            inconclusive += 1
            continue
        if missing:
            consecutive[item_id] = min(int(consecutive.get(item_id, 0)) + 1, 2)
            if consecutive[item_id] >= 2:
                removed.add(item_id)
            else:
                missing_first += 1
        else:
            consecutive.pop(item_id, None)

    if removed:
        gallery['artworks'] = [art for art in artworks if art.get('id') not in removed]
        gallery['updatedAt'] = datetime.now(timezone.utc).isoformat()
        GALLERY.write_text(json.dumps(gallery, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        for item_id in removed:
            consecutive.pop(item_id, None)
    state['deletionAudit'] = audit
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Deletion audit: checked {len(batch)}/{len(indexed)} verifiable artworks; '
          f'first missing checks {missing_first}; hidden {len(removed)}; inconclusive {inconclusive}; '
          f'not safely verifiable {len(artworks) - len(indexed)}')
    print('Local assets/artworks files were preserved.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
