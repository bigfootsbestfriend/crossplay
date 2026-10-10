"""Match every crossplay game (Wikipedia and data/manual.json) to IGDB and store facts in data/igdb.json.

Matches are cached by title, so the nightly run only searches for new titles.
Fix a bad match by putting the right IGDB id (or null to skip) in data/igdb_overrides.json.

We keep facts only (platforms, dates, genres, multiplayer modes, cover image id); no IGDB
summaries, since those are often publishers' marketing copy.
"""
import argparse
import re
import time

from common import IGDB, load_env, load_json, merged_games, norm, save_json

FIELDS = ("name,slug,url,first_release_date,cover.image_id,platforms.name,platforms.abbreviation,"
          "genres.name,themes.name,game_modes.name,total_rating_count,hypes,game_type,"
          "involved_companies.company.name,involved_companies.developer,involved_companies.publisher,"
          "multiplayer_modes.platform,multiplayer_modes.onlinecoop,multiplayer_modes.onlinecoopmax,"
          "multiplayer_modes.onlinemax,multiplayer_modes.offlinecoop,multiplayer_modes.offlinecoopmax,"
          "multiplayer_modes.offlinemax,multiplayer_modes.splitscreen,multiplayer_modes.splitscreenonline,"
          "multiplayer_modes.lancoop,multiplayer_modes.campaigncoop,multiplayer_modes.dropin,"
          "franchises.name,collections.name,websites.url,websites.type,external_games.uid,external_games.external_game_source")
MAIN_TYPES = (0, 8, 9, 10, 11)  # main game, remake, remaster, expanded game, port


def score(cand, title):
    s = 0
    if norm(cand["name"]) == norm(title):
        s += 100
    elif norm(title) in norm(cand["name"]) or norm(cand["name"]) in norm(title):
        s += 40
    if cand.get("game_type") in MAIN_TYPES:
        s += 20
    s += min(cand.get("total_rating_count") or 0, 2000) / 100  # prefer the well-known game on ties
    return s


def search(igdb, title, wiki_link):
    best = None
    for q in dict.fromkeys([title, re.sub(r"\s*\(.*?\)", "", wiki_link or "")]):
        if not q:
            continue
        q = q.replace('"', "")
        res = igdb.query("games", f'fields {FIELDS}; where name ~ "{q}"; limit 15;')  # exact, any case
        res += igdb.query("games", f'search "{q}"; fields {FIELDS}; limit 15;')
        for c in res or []:
            sc = score(c, title)
            if wiki_link:
                sc = max(sc, score(c, re.sub(r"\s*\(.*?\)", "", wiki_link)))
            if sc >= 60 and (best is None or sc > best[0]):
                best = (sc, c)
    return best[1] if best else None


def by_id(igdb, ids):
    out = {}
    for i in range(0, len(ids), 200):
        chunk = ",".join(str(x) for x in ids[i:i + 200])
        for g in igdb.query("games", f"fields {FIELDS}; where id = ({chunk}); limit 200;"):
            out[g["id"]] = g
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-fetch facts for every matched game")
    args = ap.parse_args()
    load_env("IGDB_CLIENT_ID", "IGDB_CLIENT_SECRET")
    igdb = IGDB()
    games = merged_games()[1]
    cache = load_json("igdb.json", {})          # title -> IGDB game (or None if no match)
    overrides = load_json("igdb_overrides.json", {})
    overrides.update({g["igdb_key"]: g["igdb_id"] for g in games if g.get("igdb_id")})  # researched entries carry their id

    want_ids = {t: v for t, v in overrides.items() if v and (t not in cache or not cache[t] or cache[t]["id"] != v)}
    if args.refresh:
        want_ids.update({t: g["id"] for t, g in cache.items() if g and t not in overrides})
    for g in by_id(igdb, sorted(set(want_ids.values()))).values():
        for t, v in want_ids.items():
            if v == g["id"]:
                cache[t] = g

    new = 0
    for w in games:
        t = w["igdb_key"]
        if t in overrides and overrides[t] is None:
            cache[t] = None
            continue
        if t in cache:
            continue
        cache[t] = search(igdb, t, w.get("wiki_link"))
        new += 1
        print(("  ✓ " if cache[t] else "  ✗ ") + t + (f" → {cache[t]['name']}" if cache[t] else ""))
        time.sleep(0.1)

    titles = {w["igdb_key"] for w in games}
    cache = {t: g for t, g in cache.items() if t in titles}
    save_json("igdb.json", cache)
    print(f"IGDB: {sum(1 for g in cache.values() if g)}/{len(cache)} matched, {new} searched this run")


if __name__ == "__main__":
    main()
