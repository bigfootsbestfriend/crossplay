"""Shared helpers for the crossplay collectors: env loading, HTTP and the IGDB client.

Standard library only, so the GitHub Action needs no pip install.
"""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
UA = "CrossplayGuide/0.1 (+https://github.com/bigfootsbestfriend/crossplay)"


def load_env(*required):
    """Read ../.env for local runs; in GitHub Actions the secrets are already in the environment."""
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise SystemExit("Missing secrets: " + ", ".join(missing))


def http(method, url, headers=None, data=None, retries=4, raw=False):
    body = None
    if data is not None:
        body = data.encode() if isinstance(data, str) else json.dumps(data).encode()
    headers = {"User-Agent": UA, **(headers or {})}
    for attempt in range(retries):
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                content = r.read()
                return content if raw else json.loads(content or b"null")
        except urllib.error.HTTPError as e:
            # 429 = rate limited (IGDB allows 4/s); back off and retry
            if e.code == 429 or e.code >= 500:
                time.sleep(2 ** attempt)
                continue
            raise SystemExit(f"{method} {url} failed: {e.code} {e.read().decode()[:500]}")
        except urllib.error.URLError:
            time.sleep(2 ** attempt)
    raise SystemExit(f"{method} {url} failed after {retries} retries")


def norm(name):
    """Loose title key for matching: drop bracketed notes, edition words and everything but letters/digits."""
    name = re.sub(r"\([^)]*\)", "", name or "").lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]", "", name)


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower().replace("&", "and").replace("'", "")).strip("-")
    return s or "game"


def load_json(name, default):
    p = DATA / name
    return json.loads(p.read_text()) if p.exists() else default


def save_json(name, obj):
    DATA.mkdir(exist_ok=True)
    (DATA / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=True) + "\n")


class IGDB:
    def __init__(self):
        q = urllib.parse.urlencode({
            "client_id": os.environ["IGDB_CLIENT_ID"],
            "client_secret": os.environ["IGDB_CLIENT_SECRET"],
            "grant_type": "client_credentials",
        })
        tok = http("POST", "https://id.twitch.tv/oauth2/token?" + q)["access_token"]
        self.headers = {"Client-ID": os.environ["IGDB_CLIENT_ID"], "Authorization": "Bearer " + tok}

    def query(self, endpoint, body):
        time.sleep(0.3)
        return http("POST", "https://api.igdb.com/v4/" + endpoint, self.headers, body)
