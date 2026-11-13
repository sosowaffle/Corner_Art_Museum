#!/usr/bin/env python3
"""Optional reference-image visual classifier. Fail closed: uncertain works stay unclassified.

Requires OPENAI_API_KEY and 3 character references. Never equates uploader to character.
"""
import base64
import io
import json
import os
import re
import time
from pathlib import Path
from urllib.request import Request, urlopen
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
GALLERY = ROOT / 'gallery.json'
TAGS = ROOT / 'character-tags.json'
REFS = {'corner': ROOT / 'assets/character_refs/corner.png',
        'sosowaffle': ROOT / 'assets/character_refs/sosowaffle.png',
        'gangsi': ROOT / 'assets/character_refs/gangsi.png'}
ALLOWED = set(REFS)
MAX_NEW = max(1, min(10, int(os.environ.get('AI_CLASSIFY_PER_RUN', '5'))))

def image_data(path):
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
        im.thumbnail((700, 700))
        buf = io.BytesIO()
        im.save(buf, 'JPEG', quality=78, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')

def predict(image_path, refs, key):
    blocks = [{'type':'input_text','text': (
        '사진 1은 전시 작품이며 이후 3장은 각각 심심한 코너(corner), 소소와플(sosowaffle), 강시(gangsi)의 기준 캐릭터 이미지다. '
        '작품 속에 등장하는 캐릭터를 외형 특징(머리, 눈, 의상, 특징적인 요소)으로만 비교하라. '
        '작품 업로더, 채널 이름, 파일명은 사용하지 말라. 2명 이상 등장하면 모두 포함 가능. '
        '비슷해 보이기만 하거나 불확실한 경우 characters는 빈 배열. '
        '반드시 JSON 객체만 반환: {"characters":["corner"],"confidence":0.92}. '
        '확신할 수 있는 경우에만 0.85 이상으로 표시하라.'
    )}, {'type':'input_image','image_url':image_data(image_path),'detail':'low'}]
    for name, item in refs.items():
        blocks.append({'type':'input_text','text':'REFERENCE '+name})
        blocks.append({'type':'input_image','image_url':item,'detail':'low'})
    payload = {'model':os.environ.get('OPENAI_VISION_MODEL','gpt-4.1-mini'), 'store':False,
               'input':[{'role':'user','content':blocks}], 'max_output_tokens':180}
    req = Request('https://api.openai.com/v1/responses',
                  data=json.dumps(payload).encode(), headers={
                      'Authorization':'Bearer '+key, 'Content-Type':'application/json'}, method='POST')
    with urlopen(req, timeout=80) as res:
        response = json.load(res)
    parts = [p.get('text','') for item in response.get('output', [])
             for p in item.get('content', []) if p.get('type') == 'output_text']
    raw = '\n'.join(parts).strip()
    raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw)
    obj = json.loads(raw)
    confidence = float(obj.get('confidence', 0))
    tags = obj.get('characters', [])
    if not isinstance(tags, list):
        tags = []
    tags = [x for x in tags if x in ALLOWED] if confidence >= 0.85 else []
    return {'characters':list(dict.fromkeys(tags)), 'confidence':round(confidence, 3), 'source':'vision-ai'}

def main():
    key = os.environ.get('OPENAI_API_KEY','').strip()
    if not key:
        print('AI skipped: OPENAI_API_KEY is not configured. Existing tags preserved.')
        return
    missing = [p.name for p in REFS.values() if not p.is_file()]
    if missing:
        print('AI skipped: reference images missing:', ', '.join(missing))
        return
    if not GALLERY.is_file():
        print('AI skipped: missing gallery.json')
        return
    refs = {slug:image_data(path) for slug,path in REFS.items()}
    gallery = json.loads(GALLERY.read_text(encoding='utf-8'))
    tags = json.loads(TAGS.read_text(encoding='utf-8')) if TAGS.exists() else {}
    updated = 0
    errors = 0
    for art in gallery.get('artworks', []):
        aid = str(art.get('id',''))
        if not aid or aid in tags:
            continue
        p = str(art.get('poster') or art.get('media') or art.get('image') or '')
        if not p.startswith(('assets/artworks/','assets/posters/')) or '..' in p:
            continue
        path = ROOT / p
        if not path.is_file() or path.suffix.lower() not in {'.jpg','.jpeg','.png','.webp','.gif'}:
            continue
        try:
            tags[aid] = predict(path, refs, key)
            updated += 1
            print('Classified:', aid, tags[aid]['characters'])
        except Exception as ex:
            errors += 1
            print('Classification failed for', aid, type(ex).__name__, str(ex)[:180])
            if errors >= 3:
                break
        if updated >= MAX_NEW:
            break
        time.sleep(0.2)
    if updated:
        TAGS.write_text(json.dumps(tags, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
    print('AI completed:',updated,'new classifications,',errors,'errors; total',len(tags))

if __name__ == '__main__':
    main()
