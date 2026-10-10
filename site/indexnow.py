#!/usr/bin/env python3
"""Tell IndexNow (Bing, Yandex and others) about pages that changed in this build.

  indexnow.py diff   compare each sitemap page in _site with the live copy; print the URLs that differ
  indexnow.py ping   read URLs on stdin and submit them

Run `diff` before deploying (the live site is still the old version) and `ping` after.
"""
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "_site"
UA = {"User-Agent": "crossplay-indexnow/1.0"}


def norm(html):
    # Ignore the cache-busting query strings on static assets, which change on every build.
    return hashlib.sha1(re.sub(r"\?v=[0-9a-f]+", "", html).encode()).hexdigest()


def diff():
    urls = re.findall(r"<loc>([^<]+)</loc>", (OUT / "sitemap.xml").read_text())
    base = config.BASE_URL.rstrip("/")
    for u in urls:
        local = OUT / u[len(base):].lstrip("/") / "index.html"
        if not local.exists():
            continue
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=20) as r:
                live = r.read().decode("utf-8", "replace")
        except Exception:
            live = ""  # new page (404) or fetch error: report it
        if norm(live) != norm(local.read_text()):
            print(u)


def ping():
    urls = [l.strip() for l in sys.stdin if l.strip()][:10000]
    if not urls or not config.INDEXNOW_KEY or not config.INDEXABLE:
        print("nothing to submit")
        return
    body = json.dumps({"host": config.DOMAIN, "key": config.INDEXNOW_KEY,
                       "keyLocation": f"{config.BASE_URL}/{config.INDEXNOW_KEY}.txt", "urlList": urls}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                                 headers={"Content-Type": "application/json; charset=utf-8", **UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        print(f"IndexNow {r.status}: {len(urls)} URLs")


if __name__ == "__main__":
    {"diff": diff, "ping": ping}[sys.argv[1]]()
