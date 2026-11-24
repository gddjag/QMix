"""Generate the preview's static download cards and support section."""
from html import escape
import re

from urllib.parse import urlsplit

def lang(zh, en, tag="span", attrs=""):
    return f'<{tag}{attrs} data-zh="{escape(zh, quote=True)}" data-en="{escape(en, quote=True)}">{escape(zh)}</{tag}>'

def label(zh, en, tag="span", css=""):
    return lang(zh, en, tag, f' class="{css}"' if css else "")

NS = ' target="_blank" rel="noopener noreferrer"'
NOTES = {
    "windows": (
        "Edge 提示“通常不会下载”？", "Edge says this file isn’t commonly downloaded?",
        [
            ("Windows 安装包未进行代码签名。Edge 可能提示“通常不会下载”，首次运行时也可能显示“未知发布者”。",
             "The Windows installer is unsigned. Edge may flag it as an uncommon download, and Windows may show “Unknown publisher” when you open it."),
            ("确认来自本页的下载链接后，可在 Edge 下载菜单选择「…」→「保留」以保存文件。运行前核对本页对应架构的 SHA-256，并用 Windows 安全中心扫描。",
             "If you downloaded the installer from this page, choose … → Keep in Edge to save it. Before running it, compare its SHA-256 with the value for your architecture and scan it with Windows Security."),
            ("若 SmartScreen 仅提示应用无法识别，核验后可在提供该选项时选择「更多信息」→「仍要运行」。若校验值不符或系统检测到恶意软件，请停止安装。",
             "If SmartScreen only reports an unrecognized app, you can choose More info → Run anyway after verifying the file, where available. Stop if the checksum differs or a malware scan flags the file.")
        ],
        "Microsoft 官方说明", "Microsoft’s download guidance",
        "https://learn.microsoft.com/zh-cn/troubleshoot/microsoft-edge/development/download-failures",
        "https://learn.microsoft.com/en-us/troubleshoot/microsoft-edge/development/download-failures"
    ),
    "macos": (
        "首次打开时遇到安全提示？", "Seeing a security prompt on first launch?",
        [
            ("该安装包未经 Apple 公证，也未使用 Developer ID 签名。请核对下载来源与对应芯片的 SHA-256，并先阅读 Apple 关于安全打开 App 的官方说明。",
             "This installer is not Developer ID signed or notarized by Apple. Verify its source and the SHA-256 for your chip, then read Apple’s guide to safely opening apps."),
            ("若系统明确检测到恶意软件或校验值不符，请停止安装。",
             "Stop if macOS detects malware or if the checksum differs.")
        ],
        "Apple 官方说明", "Apple’s guide to opening apps safely",
        "https://support.apple.com/zh-cn/102445", "https://support.apple.com/en-us/102445"
    )
}

def notice(platform):
    qzh, qen, body, lzh, len_, href, href_en = NOTES[platform]
    note_id = "windows-download-safety" if platform == "windows" else "macos-download-safety"
    body_html = "".join(label(zh,en,"p") for zh,en in body)
    return (f'<details class="qd-detail" id="{note_id}"><summary>{label(qzh,qen)}</summary>'
            f'<div class="qd-detail-body">{body_html}<a href="{href}" data-href-zh="{href}" data-href-en="{href_en}"{NS}>'
            f'{label(lzh,len_)} <span aria-hidden="true">↗</span></a></div></details>')

def card(manifest, platform, name, minimum, minimum_en, architectures, extension):
    release = (manifest.get("release") or {}).get(platform) or {}
    available = release.get("available", True) and any(
        any((providers or {}).values()) for providers in manifest[platform].values()
    )
    if available and not re.fullmatch(r"\d+\.\d+\.\d+", release.get("version") or ""):
        raise ValueError(f"Missing or invalid version for {platform}")
    meta = f"v{escape(release['version'])} · {extension}" if available else label("暂未开放","Unavailable")
    rows = []
    checksum = []
    for arch, zh, en in architectures:
        urls = manifest[platform].get(arch) or {}
        checksum_value = (release.get(arch) or {}).get('sha256')
        active = available and any(urls.values())
        if active and not re.fullmatch(r'[0-9a-f]{64}', checksum_value or ''):
            raise ValueError(f"Missing or invalid checksum for {platform}/{arch}")
        links = []
        primary = 'r2' if urls.get('r2') else 'github'
        for key, zh_label, en_label in [('r2','下载','Download'),('github','GitHub 下载','GitHub mirror')]:
            if active and not urls.get(key):
                continue
            style = 'r2' if active and key == primary else key
            if active and key == primary:
                zh_label, en_label = '下载', 'Download'
            attrs = f' class="qd-btn qd-{style}" data-platform="{platform}" data-architecture="{arch}" data-download-source="{key}"'
            if available and urls.get(key):
                parsed = urlsplit(urls[key])
                if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                    raise ValueError(f"Invalid download URL for {platform}/{arch}/{key}")
                links.append(f'<a{attrs} href="{escape(urls[key], quote=True)}">{label(zh_label,en_label)} <span aria-hidden="true">{"↓" if key==primary else "↗"}</span></a>')
            else:
                links.append(f'<button type="button"{attrs} disabled>{label(zh_label,en_label)} {label("暂未开放","Unavailable","small")}</button>')
        rows.append(f'<div class="qd-arch"><h4>{label(zh,en)}</h4><div class="qd-actions">{"".join(links)}</div></div>')
        if active:
            checksum.append(f'<div class="qd-hash">{label(zh,en)}<code id="checksum-{platform}-{arch}">{checksum_value}</code></div>')
    checksum_help = (('在 PowerShell 中运行下列命令，把引号中的路径换成下载的文件，再逐字对照以上校验值。',
                     'In PowerShell, replace the quoted path with the file you downloaded, then compare the result with the checksum above.',
                     'Get-FileHash -Algorithm SHA256 -LiteralPath "path/to/installer.exe"') if platform=='windows' else
                     ('在终端中运行下列命令，把引号中的路径换成下载的文件，再逐字对照以上校验值。',
                      'In Terminal, replace the quoted path with the file you downloaded, then compare the result with the checksum above.',
                      'shasum -a 256 "path/to/installer.pkg"'))
    safety = ('安装包未签名。Edge 可能提示“通常不会下载”。','Unsigned installer. Edge may flag this as an uncommon download.') if platform=='windows' else (
        '安装包未经 Apple 公证。首次打开时可能出现系统提示。','The installer is not notarized by Apple. macOS may show a security prompt.')
    if checksum:
        checksum_body = "".join(checksum) + label(*checksum_help[:2], tag="p") + f'<code class="qd-cmd">{escape(checksum_help[2])}</code>'
    else:
        checksum_body = label("安装包发布时会提供校验值。", "Checksums will be available when the installers are released.", "p")
    icon_path = (
        '<path d="M3 3h8v8H3zM13 3h8v8h-8zM3 13h8v8H3zM13 13h8v8h-8z"/>'
        if platform == "windows" else
        '<path d="M17.05 12.54c.03 3.2 2.8 4.26 2.83 4.27-.02.08-.44 1.52-1.46 3.01-.88 1.29-1.8 2.58-3.24 2.61-1.41.03-1.87-.84-3.48-.84-1.61 0-2.11.81-3.45.87-1.39.05-2.45-1.4-3.34-2.68-1.81-2.62-3.19-7.4-1.33-10.63.92-1.6 2.57-2.61 4.36-2.64 1.36-.03 2.65.92 3.48.92.84 0 2.4-1.14 4.05-.98.69.03 2.62.28 3.86 2.1-.1.06-2.31 1.35-2.28 3.99zM14.41 4.7c.74-.89 1.24-2.13 1.1-3.37-1.07.04-2.36.72-3.13 1.61-.69.79-1.3 2.05-1.14 3.26 1.2.09 2.43-.61 3.17-1.5z"/>'
    )
    icon = f'<svg class="qd-platform-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{icon_path}</svg>'
    return (f'<article class="qd-card" aria-labelledby="download-{platform}-title"><header class="qd-card-head"><h3 id="download-{platform}-title">{icon}<span>{name}</span></h3>'
            f'<span class="qd-meta">{meta}</span></header>{label(minimum,minimum_en,"p","qd-minimum")}'
            f'{"".join(rows)}<div class="qd-safety"><i aria-hidden="true">i</i>{label(*safety)}</div>'
            f'{notice(platform)}<details class="qd-detail"><summary>{label("查看 SHA-256 校验值","View SHA-256 checksums")}</summary>'
            f'<div class="qd-detail-body">{checksum_body}</div></details></article>')


def render_support(images=None):
    cards = []
    for key, brand, name, english, hint, english_hint in (
        ('support-wechat', 'WECHAT', '微信支持', 'WeChat Pay',
         '微信扫码 · 点击放大', 'Scan with WeChat · Tap to enlarge'),
        ('support-alipay', 'ALIPAY', '支付宝支持', 'Alipay',
         '支付宝扫码 · 点击放大', 'Scan with Alipay · Tap to enlarge'),
    ):
        alt = '微信收款码' if brand == 'WECHAT' else '支付宝收款码'
        alt_en = f'{english} payment QR code'
        image_attr = f'src="{escape(images[key], quote=True)}"' if images else f'data-image="{key}"'
        cards.append(
            f'<article class="support-method"><header><span lang="en">{brand}</span>{label(name,english,"h3")}</header>'
            f'<button type="button" class="support-zoom" aria-haspopup="dialog" aria-controls="shot-dialog" '
            f'aria-label="放大{alt}" data-aria-zh="放大{alt}" data-aria-en="Enlarge {alt_en}">'
            f'<img {image_attr} alt="{alt}" data-alt-zh="{alt}" data-alt-en="{alt_en}" '
            f'width="196" height="196" loading="lazy">{label(hint,english_hint,"span","support-hint")}</button></article>'
        )
    return (
        '<section id="support-author" class="qd-support" aria-labelledby="support-title"><div class="wrap">'
        '<header class="support-intro">'
        + label('KEEP GOOD SOUND GOING / 一起，让 QMix 更好', 'KEEP GOOD SOUND GOING', 'p', 'support-kicker')
        + '<h2 id="support-title">'
        + label('支持 QMix', 'Support QMix') + label('持续生长', 'Help it grow', 'span', 'support-accent') + '</h2>'
        + label('软件永久免费使用。持续开发与维护需要时间，也需要设备适配和测试投入。如果 QMix 为你的直播带来了便利，欢迎通过小额打赏支持后续开发。',
                'QMix is free to use, always. Development, maintenance and device testing take time. If QMix makes streaming easier for you, a small tip helps fund that work.',
                'p', 'support-lead')
        + label('你的支持将用于软件优化、功能迭代、多平台适配与持续更新。',
                'Your support helps improve the mixer, develop new features and test updates across platforms.',
                'p', 'support-purpose')
        + '</header><div class="support-methods">' + ''.join(cards) + '</div><div class="support-note">'
        + label('打赏完全自愿，不绑定软件功能，也不提供专属特权。无论是否打赏，都可以免费使用 QMix 的全部内置功能。',
                'Tips are entirely optional. All built-in QMix features are free for everyone. Tipping does not unlock extra features or privileges.', 'p')
        + label('感谢每一份支持，也感谢你的使用与反馈。', 'Thank you for your support, for using QMix, and for sharing your feedback.', 'p', 'support-thanks')
        + '</div></div></section>'
    )

def render_downloads(manifest):
    downloads = (f'<section class="qd-downloads" id="downloads"><div class="qd-wrap"><header class="qd-heading">'
                 f'{label("下载 QMix","Download QMix","h2")}{label("为你的电脑选择安装包。","Choose an installer for your computer.","p")}</header><div class="qd-grid">')
    windows = card(manifest,'windows','Windows','Windows 10（2004 及以上）或 Windows 11','Windows 10 (version 2004 or later) or Windows 11',
                   [('x64','Windows x64','Windows x64'),('arm64','Windows ARM64','Windows ARM64')],'EXE')
    mac = card(manifest,'macos','macOS','macOS 13.4 及以上','macOS 13.4 or later',
               [('arm64','Apple 芯片（M 系列）','Apple silicon (M series)'),('x86_64','Intel（x86_64）','Intel (x86_64)')],'PKG')
    return downloads + windows + mac + "</div></div></section>"
