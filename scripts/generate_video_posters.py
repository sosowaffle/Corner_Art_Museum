#!/usr/bin/env python3
"""Create stable JPEG video posters using ffmpeg; never modify original videos."""
import json
import shutil
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
GALLERY = ROOT / 'gallery.json'
POSTERS = ROOT / 'assets' / 'posters'

def main():
    if not GALLERY.exists():
        return
    gallery = json.loads(GALLERY.read_text(encoding='utf-8'))
    if not isinstance(gallery.get('artworks'), list):
        return
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        print('ffmpeg unavailable; in-browser video frame preview will be used.')
        return
    changed = 0
    for art in gallery['artworks']:
        src = str(art.get('media') or '')
        if not (art.get('mediaType') == 'video' or src.lower().endswith(('.mp4', '.webm'))):
            continue
        if not src.startswith('assets/artworks/') or '..' in src:
            continue
        file = ROOT / src
        if not file.is_file():
            continue
        dest = POSTERS / (file.stem + '.jpg')
        if not dest.exists() or dest.stat().st_size == 0:
            POSTERS.mkdir(parents=True, exist_ok=True)
            cmd = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y', '-ss', '0.5', '-i', str(file), '-frames:v', '1', '-vf', 'scale=640:640:force_original_aspect_ratio=decrease', '-q:v', '4', str(dest)]
            try:
                subprocess.run(cmd, check=True, timeout=55, capture_output=True)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                dest.unlink(missing_ok=True)
                print('Could not create poster for', file.name)
                continue
        poster_path = 'assets/posters/' + dest.name
        if art.get('poster') != poster_path:
            art['poster'] = poster_path
            changed += 1
    if changed:
        GALLERY.write_text(json.dumps(gallery, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Video poster records updated: {changed}')

if __name__ == '__main__':
    main()
