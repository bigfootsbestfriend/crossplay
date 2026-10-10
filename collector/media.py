"""Extra media and availability facts for game pages.

  data/trailers.json  YouTube id -> playable (checked once via oEmbed, so removed or
                      embed-blocked videos are skipped). Only the best few candidates per game are checked.
  data/gamepass.json  Xbox Game Pass catalogue (PC and console), from Microsoft's public catalogue feeds.
"""
import datetime
import urllib.error
import urllib.parse
import urllib.request

from common import UA, http, load_json, save_json, trailer_candidates

SIGLS = {"pc": "fdd9e2a7-0fee-49f6-ad69-4354098401ff", "console": "f6f1f99f-9b49-4ccd-b3bf-4d9767a77f5e"}


def playable(video_id):
    """True if YouTube will embed the video (oEmbed returns 401/403/404 for blocked, private or removed)."""
    q = urllib.parse.urlencode({"url": "https://www.youtube.com/watch?v=" + video_id, "format": "json"})
    req = urllib.request.Request("https://www.youtube.com/oembed?" + q, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30):
            return True
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404):
            return False
        raise


def trailers():
    igdb = load_json("igdb.json", {})
    cache = load_json("trailers.json", {})
    checked = 0
    for entry in igdb.values():
        for vid in trailer_candidates(entry)[:4]:
            if vid not in cache:
                cache[vid] = playable(vid)
                checked += 1
            if cache[vid]:
                break
    save_json("trailers.json", cache)
    print(f"trailers: checked {checked} new videos, {sum(cache.values())}/{len(cache)} playable")


def gamepass():
    out = {"fetched": datetime.date.today().isoformat()}
    for key, sigl in SIGLS.items():
        rows = http("GET", f"https://catalog.gamepass.com/sigls/v2?id={sigl}&language=en-us&market=US")
        ids = [r["id"] for r in rows[1:] if r.get("id")]
        products = []
        for i in range(0, len(ids), 20):
            res = http("GET", "https://displaycatalog.mp.microsoft.com/v7.0/products?bigIds="
                       + ",".join(ids[i:i + 20]) + "&market=US&languages=en-us")
            for p in res.get("Products", []):
                prices = [a["Availabilities"][0]["OrderManagementData"]["Price"]["ListPrice"]
                          for a in p.get("DisplaySkuAvailabilities", []) if a.get("Availabilities")]
                products.append({"id": p["ProductId"], "title": p["LocalizedProperties"][0]["ProductTitle"],
                                 # free-to-play games appear in the feed too; they aren't a Game Pass perk
                                 "free": bool(prices) and max(prices) == 0})
        if len(products) < 100:  # feed broke; keep yesterday's list rather than emptying it
            raise SystemExit(f"Game Pass {key}: only {len(products)} products, not saving")
        out[key] = sorted(products, key=lambda p: p["title"].lower())
    save_json("gamepass.json", out)
    print("game pass:", {k: len(v) for k, v in out.items() if k != "fetched"})


if __name__ == "__main__":
    import sys
    if "--gamepass" not in sys.argv:
        trailers()
    gamepass()
