#!/usr/bin/env python3
"""Validate the public site, and submit to IndexNow only with --submit."""
import argparse
import json
from pathlib import Path
import re
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
SITE = "https://qmix.top/"


def get(url):
    request = urllib.request.Request(url, headers={"User-Agent": "QMix-IndexNow-Preflight/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.url != url or response.status != 200:
            raise ValueError(f"Expected HTTP 200 without redirects: {url}")
        return response.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submit", action="store_true", help="Notify IndexNow after all checks pass")
    args = parser.parse_args()
    files = [p for p in ROOT.glob("*.txt") if re.fullmatch(r"[a-f0-9]{32}\.txt", p.name)]
    if len(files) != 1:
        raise ValueError("Expected exactly one IndexNow key file")
    key = files[0].stem
    if get(SITE + files[0].name).decode().strip() != key:
        raise ValueError("Public IndexNow verification file does not match")
    home = get(SITE).decode("utf-8")
    if "QMix" not in home or 'rel="canonical" href="https://qmix.top/"' not in home:
        raise ValueError("Public homepage does not match the prepared QMix site")
    if "https://qmix.top/sitemap.xml" not in get(SITE + "robots.txt").decode():
        raise ValueError("Public robots.txt does not advertise the sitemap")
    if "https://qmix.top/" not in get(SITE + "sitemap.xml").decode():
        raise ValueError("Public sitemap does not contain the homepage")
    print("Public-site preflight passed.")
    if not args.submit:
        print("Nothing submitted. Add --submit when ready to notify IndexNow.")
        return
    payload = {"host": "qmix.top", "key": key, "keyLocation": SITE + files[0].name, "urlList": [SITE]}
    request = urllib.request.Request("https://api.indexnow.org/indexnow", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status not in (200, 202):
            raise ValueError(f"Unexpected IndexNow response: {response.status}")
        print(f"IndexNow HTTP {response.status}: received; this is not an indexing guarantee.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, urllib.error.URLError) as error:
        raise SystemExit(f"Not submitted: {error}")
