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
    if not isinstance(downloads, dict) or set(downloads) - {"release"} != set(DOWNLOAD_ARCHITECTURES):
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
    windows_release = downloads.get("release", {}).get("windows", {})
    if windows_release:
        version = windows_release.get("version")
        if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
            raise ValueError("Windows release metadata requires a semantic version")
        for architecture in DOWNLOAD_ARCHITECTURES["windows"]:
            checksum = windows_release.get(architecture, {}).get("sha256")
            if not isinstance(checksum, str) or not re.fullmatch(r"[a-f0-9]{64}", checksum):
                raise ValueError(f"Windows {architecture} release metadata requires a SHA-256 checksum")


def build():
    source = (ROOT / "index.html").read_text(encoding="utf-8")
    downloads = json.loads((ROOT / "downloads.json").read_text(encoding="utf-8"))
    validate_downloads(downloads)
    macos_release = downloads.get("release", {}).get("macos", {})
    if macos_release:
        version = macos_release.get("version")
        if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
            raise ValueError("macOS release metadata requires a semantic version")
        source = source.replace("版本 1.0.2", f"版本 {version}", 1)
        source = source.replace("1.0.2 · PKG", f"{version} · PKG")
        for architecture, label in (("arm64", "Apple M（arm64）"), ("x86_64", "Intel（x86_64）")):
            checksum = macos_release.get(architecture, {}).get("sha256")
            if not isinstance(checksum, str) or not re.fullmatch(r"[a-f0-9]{64}", checksum):
                raise ValueError(f"macOS {architecture} release metadata requires a SHA-256 checksum")
            pattern = rf'({re.escape(label)}· )[^<]+(<br><code id="checksum-macos-{architecture}">)[a-f0-9]{{64}}(</code>)'
            source, replacements = re.subn(pattern, rf"\g<1>{version} · PKG\g<2>{checksum}\g<3>", source, count=1)
            if replacements != 1:
                raise ValueError(f"Could not update the {architecture} macOS release checksum")
    windows_release = downloads.get("release", {}).get("windows", {})
    if windows_release:
        version = windows_release["version"]
        source = source.replace("安装包准备中", f"版本 {version}", 1)
        specs = (
            '<dd>Windows 10 / 11</dd></div><div><dt>适用设备</dt><dd>Windows 电脑</dd></div></dl>'
            '<!-- 后续替换为 Windows 安装包的真实下载链接。 -->'
        )
        release_specs = (
            f'<dd>Windows 10 2004+ / 11</dd></div><div><dt>适用设备</dt><dd>Windows x64 / ARM64</dd></div>'
            f'<div><dt>版本 / 格式</dt><dd>{version} · EXE 安装包</dd></div></dl>'
        )
        source, replacements = source.replace(specs, release_specs, 1), source.count(specs)
        if replacements != 1:
            raise ValueError("Could not update Windows release specifications")
        note = '<p class="download-note" id="windows-download-note">Windows 10 2004+ / 11；x64 与 ARM64 分开提供，请按处理器架构选择。</p>'
        source, replacements = re.subn(
            r'<p class="download-note" id="windows-download-note">.*?</p>', note, source, count=1, flags=re.S
        )
        if replacements != 1:
            raise ValueError("Could not update the Windows release note")
        checksum_markup = (
            '<div class="download-checksum"><strong>SHA-256 校验值</strong>'
            f'<p>x64 · {version} · EXE<br><code id="checksum-windows-x64">{windows_release["x64"]["sha256"]}</code></p>'
            f'<p>ARM64 · {version} · EXE<br><code id="checksum-windows-arm64">{windows_release["arm64"]["sha256"]}</code></p>'
            '<a href="#download-verification" onclick="document.getElementById(\'download-verification\').open=true">'
            '如何核对校验值 ↗</a></div>'
        )
        source, replacements = re.subn(
            r'<div class="download-checksum"><strong>SHA-256 校验值</strong>.*?</a></div>',
            checksum_markup,
            source,
            count=1,
            flags=re.S,
        )
        if replacements != 1:
            raise ValueError("Could not update Windows release checksums")
        source = source.replace("Windows 校验值将在发布时提供。", "Windows 校验值见上方对应架构。", 1)
        macos_version = macos_release.get("version")
        faq_release_note = f"当前正式版 {version} 已提供 Windows x64 / ARM64 与 macOS Intel / Apple M 系列的独立安装包，可在下方下载区域选择对应系统与架构。"
        source = source.replace(
            "macOS 1.0.0 提供两种芯片的独立安装包；Windows 安装包正在准备中。",
            faq_release_note,
            1,
        )
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
        tag = tag.replace("，即将开放", "").replace("<span>即将开放</span>", '<span aria-hidden="true">↗</span>')
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
