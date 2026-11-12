#!/usr/bin/env python3
"""Fetch image and video attachments from allowlisted Discord channels into the static site.

Runs under GitHub Actions. Only the bot token and channel map are read from secrets.
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'assets' / 'artworks'
GALLERY = ROOT / 'gallery.json'
STATE = ROOT / 'sync-state.json'
API = 'https://discord.com/api/v10'
CONTENT_TYPES = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp', 'image/gif': '.gif',
                 'video/mp4': '.mp4', 'video/webm': '.webm'}
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_VIDEO_BYTES = 40 * 1024 * 1024
MAX_PAGES = 20

EXTENSIONS = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp', '.gif': 'image/gif', '.mp4': 'video/mp4', '.webm': 'video/webm'}

def attachment_mime(attachment):
    mime = str(attachment.get('content_type') or '').split(';')[0].strip().lower()
    if mime in CONTENT_TYPES:
        return mime
    extension = Path(str(attachment.get('filename') or '')).suffix.lower()
    return EXTENSIONS.get(extension, '')

# Artist IDs are Discord USER IDs, never channel IDs.
ARTISTS = {
    '444120879526445066': ('gangsi', '강시'),
    '397722270891769858': ('corner', '심심한 코너'),
    '664976847402172417': ('sosowaffle', '소소와플'),
}



def request(url, token=None):
    headers = {'User-Agent': 'CommunityArtMuseum/1.0 (GitHub Actions)'}
    if token:
        headers['Authorization'] = 'Bot ' + token
    for attempt in range(5):
        try:
            with urlopen(Request(url, headers=headers), timeout=25) as resp:
                content = resp.read()
                return content, resp.headers.get('Content-Type', ''), resp.geturl()
        except HTTPError as e:
            if e.code == 429 and attempt < 4:
                try:
                    wait = min(float(json.loads(e.read()).get('retry_after', 2)), 35)
                except Exception:
                    wait = 3
                time.sleep(max(1, wait))
                continue
            if e.code >= 500 and attempt < 4:
                time.sleep(2 ** attempt)
                continue
            raise
        except URLError:
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError('Failed after retries')


def get_messages(channel_id, token, cursor):
    """Get newest messages backwards, stopping once the last processed ID is reached."""
    messages = []
    before = None
    for page in range(MAX_PAGES):
        uri = f'{API}/channels/{channel_id}/messages?limit=100'
        if before:
            uri += f'&before={before}'
        raw, _, _ = request(uri, token=token)
        batch = json.loads(raw)
        if not isinstance(batch, list):
            raise RuntimeError(f'Unexpected API response in channel {channel_id}')
        if not batch:
            break
        for msg in batch:
            if cursor and int(msg['id']) <= int(cursor):
                return sorted(messages, key=lambda m: int(m['id']))
            messages.append(msg)
        before = batch[-1]['id']
        if len(batch) < 100:
            break
    else:
        print(f'WARNING: channel {channel_id} has more than {MAX_PAGES * 100} new messages; older messages may be skipped.', file=sys.stderr)
    return sorted(messages, key=lambda m: int(m['id']))


def get_channel_info(channel_id, token):
    raw, _, _ = request(f'{API}/channels/{channel_id}', token=token)
    return json.loads(raw)


def get_forum_threads(channel_id, guild_id, token):
    """Find accessible active + recent public archived posts for a forum channel."""
    raw, _, _ = request(f'{API}/guilds/{guild_id}/threads/active', token=token)
    active = json.loads(raw).get('threads', [])
    posts = {str(t['id']): t for t in active if str(t.get('parent_id')) == str(channel_id)}
    before = None
    # Scan at most 500 most recently archived threads; older archives require a separate import.
    for _ in range(5):
        url = f'{API}/channels/{channel_id}/threads/archived/public?limit=100'
        if before:
            from urllib.parse import quote
            url += '&before=' + quote(before, safe='')
        raw, _, _ = request(url, token=token)
        data = json.loads(raw)
        threads = data.get('threads', [])
        for thread in threads:
            posts.setdefault(str(thread['id']), thread)
        if not data.get('has_more') or not threads:
            break
        before = threads[-1].get('thread_metadata', {}).get('archive_timestamp')
        if not before:
            break
    return list(posts.values())


def parse_caption(raw, filename):
    lines = [re.sub(r'[`*_#]', '', line).strip() for line in (raw or '').splitlines() if line.strip()]
    title = ''
    description = []
    for line in lines:
        m = re.match(r'^(?:제목|작품명|title)\s*[:：]\s*(.+)$', line, re.I)
        if m:
            title = m.group(1)
        else:
            description.append(re.sub(r'^(?:설명|description)\s*[:：]\s*', '', line, flags=re.I))
    if not title and description:
        title = description.pop(0)
    if not title:
        title = Path(filename).stem.replace('_', ' ').replace('-', ' ')
    return title[:100], '\n'.join(description)[:1200]


def download_attachment(attachment, destination):
    mime = attachment_mime(attachment)
    ext = CONTENT_TYPES.get(mime)
    if not ext:
        return None
    max_bytes = MAX_VIDEO_BYTES if mime.startswith('video/') else MAX_IMAGE_BYTES
    if attachment.get('size', 0) > max_bytes:
        print(f'SKIP oversized attachment: {attachment.get("filename")}')
        return None
    url = attachment.get('url', '')
    if urlparse(url).scheme != 'https' or urlparse(url).hostname not in ('cdn.discordapp.com', 'media.discordapp.net'):
        print('SKIP non-Discord attachment URL')
        return None
    content, real_type, final_url = request(url)
    if urlparse(final_url).scheme != 'https' or urlparse(final_url).hostname not in ('cdn.discordapp.com', 'media.discordapp.net'):
        raise RuntimeError('Unexpected image redirect host')
    if len(content) > max_bytes:
        print(f'SKIP oversized downloaded attachment: {attachment.get("filename")}')
        return None
    # Reject mislabeled media using magic headers. For MP4, ftyp sits at offset 4.
    signatures = {'.png': content.startswith(b'\x89PNG\r\n\x1a\n'), '.jpg': content.startswith(b'\xff\xd8\xff'), '.gif': content.startswith((b'GIF87a', b'GIF89a')), '.webp': content.startswith(b'RIFF') and content[8:12] == b'WEBP', '.mp4': len(content)>12 and content[4:8] == b'ftyp', '.webm': content.startswith(b'\x1a\x45\xdf\xa3')}
    if not signatures[ext]:
        print(f'SKIP invalid media content: {attachment.get("filename")}')
        return None
    DEST.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return ext


def main():
    token = os.environ.get('DISCORD_BOT_TOKEN', '').strip()
    raw_channels = os.environ.get('DISCORD_CHANNELS', '').strip()
    if not raw_channels and (ROOT / 'channels.json').exists():
        raw_channels = (ROOT / 'channels.json').read_text(encoding='utf-8')
    if not token or not raw_channels:
        print('ERROR: Add DISCORD_BOT_TOKEN secret and channels.json config.', file=sys.stderr)
        return 1
    channels = json.loads(raw_channels)
    if not isinstance(channels, dict) or not channels:
        raise ValueError('DISCORD_CHANNELS must be a nonempty JSON object')
    if not all(re.fullmatch(r'\d{15,25}', str(channel_id)) for channel_id in channels):
        raise ValueError('Channel IDs must be Discord snowflake numbers')
    gallery = json.loads(GALLERY.read_text(encoding='utf-8')) if GALLERY.exists() else {'artworks': []}
    state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'cursors': {}}
    artworks = [] if gallery.get('demo') else gallery.get('artworks', [])
    # Initial import recovery: never let stale cursors hide all existing art.
    # A successful previous run may have advanced cursors without importing media.
    if not artworks:
        if state.get('cursors'):
            print('No real artwork in gallery; rescanning existing channel history.')
        state = {'cursors': {}}
    # Fix any previously imported artworks incorrectly attributed by channel.
    # Preserve uploader credits and leave unidentified uploads unassigned.
    corrected = 0
    for artwork in artworks:
        uploader_id = str(artwork.get('uploaderId') or '')
        if uploader_id in ARTISTS:
            artist_id, artist_name = ARTISTS[uploader_id]
        else:
            artist_id = uploader_id or 'unassigned'
            artist_name = str(artwork.get('uploaderName') or '미확인 작가')[:80]
        if artwork.get('authorId') != artist_id or artwork.get('authorName') != artist_name:
            artwork['authorId'] = artist_id
            artwork['authorName'] = artist_name
            corrected += 1
    known = {a['id'] for a in artworks}
    new_count = 0
    inspected_messages = 0
    found_attachments = 0
    unsupported_files = 0
    for channel_id, config in channels.items():
        if isinstance(config, str):
            config = {'name': config, 'category': 'other'}
        if not isinstance(config, dict):
            raise ValueError(f'Invalid channel config: {channel_id}')
        category = re.sub(r'[^a-z0-9-]', '', str(config.get('category', 'other')).lower())[:30] or 'other'
        info = get_channel_info(channel_id, token)
        channel_type = info.get('type')
        # 15 = Forum, 16 = Media: all artwork messages live within post threads.
        if channel_type in (15, 16):
            guild_id = info.get('guild_id')
            if not guild_id:
                raise RuntimeError(f'Forum channel {channel_id} has no guild_id')
            sources = [(str(post['id']), str(post.get('name') or '게시글'))
                       for post in get_forum_threads(channel_id, guild_id, token)]
        else:
            sources = [(channel_id, '')]
        for source_id, thread_title in sources:
            cursor = state.get('cursors', {}).get(source_id)
            messages = get_messages(source_id, token, cursor)
            print(f'Channel {channel_id} / source {source_id}: {len(messages)} new messages')
            inspected_messages += len(messages)
            for msg in messages:
                if msg.get('author', {}).get('bot'):
                    continue
                attachments = msg.get('attachments') or []
                found_attachments += len(attachments)
                for attachment in attachments:
                    mime = attachment_mime(attachment)
                    ext = CONTENT_TYPES.get(mime)
                    if not ext:
                        unsupported_files += 1
                        print(f'SKIP unsupported attachment: {attachment.get("filename", "unknown")} / {attachment.get("content_type", "unknown")}')
                        continue
                    aid = str(attachment['id'])
                    item_id = f'{channel_id}-{msg["id"]}-{aid}'
                    if item_id in known:
                        continue
                    path = DEST / f'{item_id}{ext}'
                    if not path.exists():
                        ok = download_attachment(attachment, path)
                        if not ok:
                            continue
                    title, description = parse_caption(msg.get('content'), attachment.get('filename', 'artwork'))
                    if thread_title and not (msg.get('content') or '').strip():
                        title = thread_title[:100]
                    author = msg.get('author', {})
                    uploader_id = str(author.get('id', 'unknown'))
                    uploader_name = (msg.get('member', {}).get('nick') or author.get('global_name') or author.get('username') or '익명의 업로더')[:80]
                    # Associate works with actual Discord user identity,
                    # independent of which of the six channels hosts the work.
                    artist_id, artist_name = ARTISTS.get(uploader_id, (uploader_id, uploader_name))
                    guild_id = msg.get('guild_id') or '@me'
                    kind = 'video' if mime.startswith('video/') else 'image'
                    artworks.append({
                        'id': item_id,
                        'title': title,
                        'description': description,
                        'authorId': artist_id,
                        'authorName': artist_name,
                        'uploaderId': uploader_id,
                        'uploaderName': uploader_name,
                        'category': category,
                        'channelName': str(config.get('name', '전시실'))[:80],
                        'createdAt': msg.get('timestamp'),
                        'mediaType': kind,
                        'media': f'assets/artworks/{path.name}',
                        **({'image': f'assets/artworks/{path.name}'} if kind == 'image' else {}),
                        'messageUrl': f'https://discord.com/channels/{guild_id}/{source_id}/{msg["id"]}' if guild_id != '@me' else '',
                    })
                    new_count += 1
                    known.add(item_id)
            if messages:
                state.setdefault('cursors', {})[source_id] = str(max(int(m['id']) for m in messages))
    artworks.sort(key=lambda a: a.get('createdAt') or '', reverse=True)
    # No-op runs do not create commits or update displayed timestamp.
    if new_count or corrected or gallery.get('demo'):
        gallery = {'demo': False, 'updatedAt': datetime.now(timezone.utc).isoformat(), 'artworks': artworks}
        GALLERY.write_text(json.dumps(gallery, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # Advance cursors even when new messages contain no images.
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Checked {inspected_messages} messages, found {found_attachments} attachments, skipped {unsupported_files} unsupported files')
    print(f'Imported {new_count} new artworks (images/videos); corrected {corrected} artist credits; total {len(artworks)}')
    if not artworks:
        print('NOTICE: No artworks imported. Check SKIP messages, bot channel permissions, and whether media were sent as actual attachments (not just URLs).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
