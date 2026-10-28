#!/usr/bin/env python3
"""Build the deployable single-page site without changing original image bytes."""
import base64
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "dist"
DOWNLOAD_ARCHITECTURES = {"windows": {"x64", "arm64"}, "macos": {"arm64", "x86_64"}}


def validate_downloads(downloads):
    if not isinstance(downloads, dict) or set(downloads) != set(DOWNLOAD_ARCHITECTURES):
        raise ValueError("Downloads require Windows and macOS architecture groups")
    for platform, architectures in DOWNLOAD_ARCHITECTURES.items():
        groups = downloads[platform]
        if not isinstance(groups, dict) or set(groups) != architectures:
            raise ValueError(f"Wrong download architecture set: {platform}")
        for architecture, providers in groups.items():
            if not isinstance(providers, dict) or set(providers) != {"r2", "github"}:
                raise ValueError(f"Downloads require R2 and GitHub entries: {platform}/{architecture}")
            for provider, url in providers.items():
                if url is None:
                    continue
                if not isinstance(url, str):
                    raise ValueError("Download URL must be HTTPS or null")
                parsed = urlsplit(url)
                if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                    raise ValueError(f"Download URL must be HTTPS without credentials: {platform}/{architecture}/{provider}")


def build():
    source = (ROOT / "index.html").read_text(encoding="utf-8")
    downloads = json.loads((ROOT / "downloads.json").read_text(encoding="utf-8"))
    validate_downloads(downloads)
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    manifest = {}

    def emit_asset(name, data_uri):
        match = re.fullmatch(r"data:(image/(?:png|jpeg|webp|svg\+xml));base64,(.+)", data_uri, re.S)
        if not match:
            raise ValueError(f"Unsupported image data: {name}")
        raw = base64.b64decode(match[2], validate=True)
        suffix = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/svg+xml": "svg"}[match[1]]
        digest = hashlib.sha256(raw).hexdigest()
        target = f"assets/{name}-{digest[:12]}.{suffix}"
        (OUT / target).write_bytes(raw)
        manifest[name] = {"path": target, "sha256": digest, "bytes": len(raw)}
        return target

    pattern = r'(<script id="qmix-assets" type="application/json">)(.*?)(</script>)'
    payload = re.search(pattern, source, re.S)
    if not payload:
        raise ValueError("Missing website image payload")
    images = json.loads(payload[2])
    urls = {name: emit_asset(name, data) for name, data in images.items()}
    source = re.sub(pattern, lambda m: m[1] + json.dumps(urls, separators=(",", ":")) + m[3], source, count=1, flags=re.S)
    source = re.sub(r'(<link rel="icon" href=")(data:[^"]+)(")', lambda m: m[1] + emit_asset("favicon", m[2]) + m[3], source, count=1)

    def image_src(match):
        tag, name = match[0], match[1]
        return tag if re.search(r"\bsrc=", tag) else tag.replace("<img ", f'<img src="{urls[name]}" ', 1)

    source = re.sub(r'<img\b[^>]*\bdata-image="([^"]+)"[^>]*>', image_src, source)
    def download_link(match):
        tag = match[0]
        platform = re.search(r'data-platform="([^"]+)"', tag)[1]
        architecture_match = re.search(r'data-architecture="([^"]+)"', tag)
        if not architecture_match:
            raise ValueError(f"Download control is missing its architecture: {platform}")
        architecture = architecture_match[1]
        provider = re.search(r'data-download-source="([^"]+)"', tag)[1]
        url = downloads[platform][architecture][provider]
        if url is None:
            return tag
        tag = tag.replace("<button ", '<a href="' + html.escape(url, quote=True) + '" ', 1)
        tag = tag.replace(' type="button"', "").replace(" disabled", "")
        tag = tag.replace("，即将开放", "").replace("<span>即将开放</span>", "<span>下载 ↗</span>")
        return tag.replace("</button>", "</a>")

    source = re.sub(r'<button\b[^>]*data-download-source="[^"]+"[^>]*>.*?</button>', download_link, source, flags=re.S)
    if len(source.encode("utf-8")) >= 2_000_000:
        raise ValueError("Published HTML must stay below Google's 2 MB HTML fetch limit")
    (OUT / "index.html").write_text(source, encoding="utf-8")
    for name in ["robots.txt", "sitemap.xml", "_headers", "_redirects"]:
        shutil.copy2(ROOT / name, OUT / name)
    for file in ROOT.glob("*.txt"):
        if re.fullmatch(r"[a-f0-9]{32}\.txt", file.name) and file.read_text().strip() == file.stem:
            shutil.copy2(file, OUT / file.name)
    manifest_path = ROOT.parent / ".cache" / "qmix-web-deploy-20261024" / "build-manifest.json"
    if manifest_path.parent.exists():
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Built {OUT}: HTML {len(source.encode('utf-8')):,} bytes, {len(manifest)} original image assets")


if __name__ == "__main__":
    build()
