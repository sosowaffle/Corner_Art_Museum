#!/usr/bin/env python3
"""Safely add visual character tags to a static Discord art museum.

Requires OPENAI_API_KEY to perform vision classification. Manual tags take priority.
This version only knows the 'corner' character; others remain unclassified.
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps, ImageSequence
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
GALLERY = ROOT / 'gallery.json'
TAGS = ROOT / 'character-tags.json'
REFERENCES = ROOT / 'character-references' / 'corner-reference-sheet.jpg'
MODEL = os.getenv('CHARACTER_VISION_MODEL', 'gpt-4.1-mini')
BATCH = max(1, min(30, int(os.getenv('CHARACTER_CLASSIFY_BATCH', '10'))))


def data_url(image: Image.Image, width=900, height=1200):
    image = ImageOps.exif_transpose(image).convert('RGB')
    image.thumbnail((width, height))
    out = io.BytesIO()
    image.save(out, format='JPEG', quality=78, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(out.getvalue()).decode('ascii')


def composite_art(path: Path):
    """For long comics, show top/middle/end panels together rather than shrinking all text."""
    with Image.open(path) as im:
        frame = ImageSequence.Iterator(im)[0].copy().convert('RGB')
    w, h = frame.size
    if h <= w * 2.6:
        return frame
    regions = []
    band = min(h, max(120, round(w * 1.2)))
    for start in (0, max(0, (h - band)//2), max(0, h-band)):
        crop = frame.crop((0, start, w, min(h, start+band)))
        crop.thumbnail((600, 520))
        regions.append(crop)
    target = Image.new('RGB', (max(p.width for p in regions), sum(p.height for p in regions)+20), 'white')
    y=0
    for part in regions:
        target.paste(part,(0,y))
        y += part.height+10
    return target


def classify(client: OpenAI, path: Path, reference_url: str):
    content = [
        {'type':'text','text': (
            'The first image is a REFERENCE SHEET with seven drawings of the SAME fictional '
            'character, named Corner. The second image is the NEW ARTWORK. '
            'Determine whether the same fictional character visibly appears in the NEW ARTWORK. '
            'Compare facial features, hair shape, colors, and clothing, accounting for chibi and '
            'realistic styles. Be conservative: generic black-haired people are NOT sufficient. '
            'Do not infer identity from uploader, text title, channel, or overall black hair. '
            'If multiple characters are present, mark true only if Corner visibly appears. '
            'Reply with JSON only, of the form {"corner": true/false, "confidence": number between 0 and 1}. '
            'Return false if uncertain or no character is identifiable.'
        )},
        {'type':'image_url','image_url':{'url':reference_url,'detail':'high'}},
        {'type':'image_url','image_url':{'url':data_url(composite_art(path)),'detail':'high'}},
    ]
    answer=client.chat.completions.create(
        model=MODEL,
        messages=[{'role':'user','content':content}],
        response_format={'type':'json_object'},
        max_tokens=120,
        temperature=0,
        timeout=60,
    )
    obj=json.loads(answer.choices[0].message.content)
    confidence=float(obj.get('confidence',0))
    return bool(obj.get('corner') is True and confidence>=0.85), confidence


def main():
    if not GALLERY.exists():
        raise SystemExit('Missing gallery.json')
    if not REFERENCES.exists():
        raise SystemExit('Missing reference character sheet')
    key=os.getenv('OPENAI_API_KEY','').strip()
    if not key:
        print('Character AI classification skipped: OPENAI_API_KEY secret not set.')
        return
    gallery=json.loads(GALLERY.read_text(encoding='utf-8'))
    artworks=gallery.get('artworks',[])
    if not isinstance(artworks,list):
        raise SystemExit('Invalid gallery.json')
    tags=json.loads(TAGS.read_text(encoding='utf-8')) if TAGS.exists() else {}
    if not isinstance(tags,dict):
        raise SystemExit('Invalid character-tags.json: expected object')
    reference_url='data:image/jpeg;base64,'+base64.b64encode(REFERENCES.read_bytes()).decode('ascii')
    client=OpenAI(api_key=key, max_retries=2)
    queued=0; scanned=0; matched=0; skipped=0
    for art in reversed(artworks):
        ident=str(art.get('id') or '')
        if not ident or ident in tags:  # preserve existing manually tagged artworks
            continue
        if str(art.get('mediaType','image')).lower() != 'image':
            skipped+=1
            continue
        media=str(art.get('media') or art.get('image') or '')
        path=(ROOT / media).resolve()
        try:
            path.relative_to(ROOT)
        except ValueError:
            skipped+=1
            continue
        if path.suffix.lower() not in ('.png','.jpg','.jpeg','.webp','.gif') or not path.is_file():
            skipped+=1
            continue
        if queued>=BATCH:
            break
        queued+=1
        try:
            has_corner,confidence=classify(client,path,reference_url)
        except Exception as exc:
            print(f'Classification error for {ident}: {type(exc).__name__}: {exc}',file=sys.stderr)
            # Do not mark on error; reattempt on next run.
            continue
        tags[ident]={
            'characters':['corner'] if has_corner else [],
            'autoClassified':True,
            'method':MODEL,
            'confidence':round(confidence,3),
            'classifiedAt':datetime.now(timezone.utc).isoformat()
        }
        matched+=int(has_corner);scanned+=1
        print(f'Classified {ident}: {"corner" if has_corner else "unclassified"} ({confidence:.2f})')
    if scanned:
        TAGS.write_text(json.dumps(tags,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Character auto-tag results: {scanned} classified, {matched} Corner matches, {skipped} unsupported, {len(tags)} total tagged.')

if __name__=='__main__':
    main()
