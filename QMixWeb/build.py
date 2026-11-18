#!/usr/bin/env python3
"""Build the static site from the self-contained HTML and the release manifest."""
import base64
import hashlib
import json
import re
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from download_sections import render_downloads

ROOT = Path(__file__).resolve().parent
MIME_SUFFIX = {'image/png':'png','image/webp':'webp','image/jpeg':'jpg','image/svg+xml':'svg','video/mp4':'mp4'}
MEDIA = re.compile(r'data:(image/(?:png|webp|jpeg|svg\+xml)|video/mp4);base64,([A-Za-z0-9+/=]+)')


def build():
    source = (ROOT / 'index.html').read_text(encoding='utf-8')
    releases = json.loads((ROOT / 'downloads.json').read_text(encoding='utf-8'))
    expected = {'windows': {'x64', 'arm64'}, 'macos': {'arm64', 'x86_64'}}
    for platform, arches in expected.items():
        if set(releases[platform]) != arches:
            raise ValueError(f'Invalid architecture list for {platform}')
        if any(set(mirrors) != {'r2','github'} for mirrors in releases[platform].values()):
            raise ValueError(f'Invalid mirror list for {platform}')
    downloads = render_downloads(releases)
    source, count = re.subn(r'<!--QMIX-DOWNLOADS-->.*?<!--/QMIX-DOWNLOADS-->',
                            lambda _: '<!--QMIX-DOWNLOADS-->'+downloads+'<!--/QMIX-DOWNLOADS-->',
                            source, flags=re.S)
    if count != 1:
        raise ValueError('Expected exactly one download section')

    # Stage all assets first so a bad input cannot destroy an existing preview.
    cache = ROOT.parent / '.cache'
    cache.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix='qmix-web-build-',dir=cache) as stage_name:
        stage = Path(stage_name)
        (stage/'assets').mkdir()
        def emit(match):
            mime, encoded = match.groups()
            binary = base64.b64decode(encoded, validate=True)
            digest = hashlib.sha256(binary).hexdigest()[:24]
            target = f'assets/{digest}.{MIME_SUFFIX[mime]}'
            if not (stage/target).exists():
                (stage/target).write_bytes(binary)
            return target

        source = MEDIA.sub(emit,source)
        catalog = json.loads(re.search(r'<script id="qmix-assets" type="application/json">(.*?)</script>',source,re.S)[1])
        def image_tag(match):
            tag, name = match[0], match[1]
            return tag if re.search(r'\bsrc=',tag) else tag.replace('<img ',f'<img src="{catalog[name]}" ',1)
        source = re.sub(r'<img\b[^>]*\bdata-image="([^"]+)"[^>]*>', image_tag, source)
        if len(source.encode()) >= 2_000_000:
            raise ValueError('Large inline payload remains in the published HTML')
        (stage/'index.html').write_text(source,encoding='utf-8')
        for name in ('robots.txt','sitemap.xml','_headers','_redirects'):
            shutil.copy2(ROOT/name,stage/name)
        for file in ROOT.glob('*.txt'):
            if re.fullmatch(r'[a-f0-9]{32}\.txt',file.name) and file.read_text().strip()==file.stem:
                shutil.copy2(file,stage/file.name)
        out = ROOT/'dist'
        if out.exists():
            shutil.rmtree(out)
        shutil.move(str(stage),str(out))
    print(f'Built {out}: {len(source.encode()):,} bytes HTML, {len(list((out/"assets").iterdir()))} media assets')


if __name__ == '__main__':
    build()
