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
        if windows_release.get("available") is False and any(
            downloads["windows"][architecture][provider]
            for architecture in DOWNLOAD_ARCHITECTURES["windows"]
            for provider in ("r2", "github")
        ):
            raise ValueError("Delisted Windows releases must not expose public download URLs")


def build():
    source = (ROOT / "index.html").read_text(encoding="utf-8")
    # Keep the Windows safety note in both standalone and published versions.
    if 'id="windows-download-safety"' not in source:
        windows_safety = "<div class=\"download-safety\" id=\"windows-download-safety\"><strong>Windows \u4e0b\u8f7d\u4e0e\u5b89\u88c5\u63d0\u793a \u00b7 \u672a\u7b7e\u540d</strong><p>QMix \u7684 Windows \u5b89\u88c5\u5305\u76ee\u524d\u672a\u8fdb\u884c\u4ee3\u7801\u7b7e\u540d\u3002Edge \u53ef\u80fd\u63d0\u793a\u201c\u901a\u5e38\u4e0d\u4f1a\u4e0b\u8f7d\u201d\uff0c\u9996\u6b21\u8fd0\u884c\u65f6 Windows \u4e5f\u53ef\u80fd\u663e\u793a\u201c\u672a\u77e5\u53d1\u5e03\u8005\u201d\u6216\u201cWindows \u5df2\u4fdd\u62a4\u4f60\u7684\u7535\u8111\u201d\u3002\u8fd9\u4e9b\u63d0\u793a\u4e0e\u7b7e\u540d\u53ca\u6587\u4ef6\u4fe1\u8a89\u6709\u5173\uff0c\u4e0d\u80fd\u5355\u51ed\u63d0\u793a\u5224\u65ad\u6587\u4ef6\u662f\u5426\u5b89\u5168\u3002</p><p><b>\u4e0b\u8f7d\u524d\u8bf7\u786e\u8ba4\uff1a</b>\u4ec5\u4ece\u672c\u5b98\u7f51\u7684\u300c\u4e0b\u8f7d\u300d\u6216\u300cGitHub \u4e0b\u8f7d\u300d\u83b7\u53d6\u5b89\u88c5\u5305\uff0c\u6309\u5bf9\u5e94\u7248\u672c\u3001\u67b6\u6784\u6838\u5bf9\u4e0a\u65b9 SHA-256 \u6821\u9a8c\u503c\uff0c\u5e76\u4f7f\u7528 Windows \u5b89\u5168\u4e2d\u5fc3\u626b\u63cf\u6587\u4ef6\u3002</p><p><b>Edge \u4e0b\u8f7d\u63d0\u793a\uff1a</b>\u786e\u8ba4\u6765\u6e90\u53ef\u4fe1\u540e\uff0c\u5728\u4e0b\u8f7d\u9879\u53f3\u4fa7\u70b9\u51fb\u300c\u2026\u300d\u2192\u300c\u4fdd\u7559\u300d\uff1b\u82e5\u8fd8\u6709\u786e\u8ba4\u9875\u9762\uff0c\u53ef\u5c55\u5f00\u300c\u663e\u793a\u66f4\u591a\u300d\u5e76\u9009\u62e9\u300c\u4ecd\u7136\u4fdd\u7559\u300d\u3002\u4e0d\u540c\u7248\u672c\u7684\u6d4f\u89c8\u5668\u6587\u5b57\u53ef\u80fd\u7565\u6709\u5dee\u5f02\u3002</p><p><b>\u9996\u6b21\u8fd0\u884c\u63d0\u793a\uff1a</b>\u6587\u4ef6\u6765\u6e90\u4e0e\u6821\u9a8c\u503c\u786e\u8ba4\u65e0\u8bef\u540e\uff0c\u82e5 SmartScreen \u63d0\u793a\u5e94\u7528\u672a\u88ab\u8bc6\u522b\u4e14\u63d0\u4f9b\u8be5\u9009\u9879\uff0c\u53ef\u70b9\u51fb\u300c\u66f4\u591a\u4fe1\u606f\u300d\u2192\u300c\u4ecd\u8981\u8fd0\u884c\u300d\u3002\u65e0\u9700\u5173\u95ed Defender\u3001SmartScreen \u6216\u6dfb\u52a0\u6392\u9664\u9879\uff1b\u82e5\u660e\u786e\u68c0\u6d4b\u5230\u75c5\u6bd2/\u6076\u610f\u8f6f\u4ef6\u3001\u6821\u9a8c\u503c\u4e0d\u4e00\u81f4\u6216\u6765\u6e90\u4e0d\u660e\uff0c\u8bf7\u505c\u6b62\u5b89\u88c5\u5e76\u8054\u7cfb\u4f5c\u8005\u3002</p><a href=\"https://learn.microsoft.com/en-us/troubleshoot/microsoft-edge/development/download-failures\" target=\"_blank\" rel=\"noopener noreferrer\">Microsoft \u5b98\u65b9\u4e0b\u8f7d\u63d0\u793a\u8bf4\u660e \u2197</a></div>"
        source, inserted = re.subn(
            r'(<article\b[^>]*aria-labelledby="download-windows-title"[^>]*>.*?)(</article>)',
            lambda match: match[1] + windows_safety + match[2],
            source, count=1, flags=re.S,
        )
        if inserted != 1:
            raise ValueError("Could not insert Windows download safety note")
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
        if windows_release.get("available") is False:
            paused_faq = f"Windows 版本暂时下架，官网当前提供 macOS {macos_version} 的 Intel / Apple M 系列独立安装包。"
            source, faq_replacements = re.subn(
                r"当前正式版 \d+\.\d+\.\d+ 已提供 Windows x64 / ARM64 与 macOS Intel / Apple M 系列的独立安装包，可在下方下载区域选择对应系统与架构。",
                paused_faq,
                source,
                count=1,
            )
            if faq_replacements != 1:
                source = source.replace(
                    "macOS 1.0.0 提供两种芯片的独立安装包；Windows 安装包正在准备中。",
                    paused_faq,
                    1,
                )
    source = source.replace(
        "应用采集复制原应用声音，原播放仍会继续。如果原应用已在耳机中播放，又通过 QMix 监听同一声音，就可能重复。检查原应用输出、硬件直通与 QMix 监听路径，避免同一音源重复回到耳机。",
        "macOS 14.2 及以上的系统音源接管发往 QMix 的声音：系统输出选择 QMix 时，由软件路由控制；选择其他输出设备时可直接播放。其他应用采集方式可能保留原播放。请检查系统输出、硬件直通与 QMix 监听路径，避免同一音源重复回到耳机。",
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
