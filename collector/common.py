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


def merged_games():
    """Wikipedia's list plus our own researched entries (data/manual.json), in one wiki-shaped list.

    A manual entry replaces the Wikipedia row with the same title (or any title in its "replaces"),
    so a researched entry always wins. data/title_overrides.json renames Wikipedia titles to the
    name people search for ("Fortnite Battle Royale" -> "Fortnite"); IGDB data stays keyed by
    the original title ("igdb_key").
    """
    wiki = load_json("wikipedia.json", {"games": []})
    manual = load_json("manual.json", {"games": []})["games"]
    renames = load_json("title_overrides.json", {})
    replaced = {norm(m["title"]) for m in manual} | {norm(r) for m in manual for r in m.get("replaces", [])}
    games = []
    for w in wiki["games"]:
        title = renames.get(w["title"], w["title"])
        if not w["discontinued"] and (norm(w["title"]) in replaced or norm(title) in replaced):
            continue
        games.append({**w, "title": title, "igdb_key": w["title"], "source": "wikipedia"})
    for m in manual:
        games.append({
            "title": m["title"], "igdb_key": m["title"], "igdb_id": m.get("igdb_id"), "source": "manual",
            "wiki_link": None, "discontinued": m.get("discontinued", False),
            "crossplay": m.get("crossplay", True), "separate": m.get("separate", []),
            "groups": [{"platforms": gr["platforms"], "pc_stores": gr.get("pc_stores", []),
                        "others": gr.get("others", []), "refs": []} for gr in m.get("groups", [])],
            "notes": m.get("notes", []), "sources": m.get("sources", []), "checked": m.get("checked"), "crossprog": m.get("crossprog"),
        })
    return wiki, games


TRAILER_ORDER = ("launch trailer", "release trailer", "release date trailer", "trailer", "gameplay trailer",
                 "announcement trailer", "reveal trailer", "official trailer")


def trailer_candidates(igdb_entry):
    """IGDB video ids for a game, best trailer first (launch/release trailers before teasers and dev diaries)."""
    vids = [v for v in (igdb_entry or {}).get("videos", []) if v.get("video_id")]

    def rank(v):
        name = (v.get("name") or "").lower().strip()
        if name in TRAILER_ORDER:
            return TRAILER_ORDER.index(name)
        return len(TRAILER_ORDER) + (0 if "trailer" in name else 1)
    return [v["video_id"] for v in sorted(vids, key=rank)]
