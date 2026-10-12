"""Build the static site from data/*.json into _site/.

    python3 site/build.py

Pages: home, one page per game, platform hubs, platform-pair hubs, genre hubs, updates,
about/methodology, privacy, 404, sitemap and a small search index.
"""
import urllib.parse
import datetime
import html
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "collector"))
import config  # noqa: E402
from common import load_json, save_json, merged_games, norm, slugify, trailer_candidates  # noqa: E402

OUT = HERE.parent / "_site"
GA_TAG = (f'<script async src="https://www.googletagmanager.com/gtag/js?id={config.GA_ID}"></script>\n'
          f"<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}"
          f"gtag('js',new Date());gtag('config','{config.GA_ID}');</script>\n") if config.GA_ID else ""
VERIFY_TAGS = ((f'<meta name="google-site-verification" content="{config.GOOGLE_VERIFY}">\n' if config.GOOGLE_VERIFY else "")
               + (f'<meta name="msvalidate.01" content="{config.BING_VERIFY}">\n' if config.BING_VERIFY else ""))
CLICKY_TAG = (f'<script async data-id="{config.CLICKY_ID}" src="https://static.getclicky.com/js"></script>\n'
              if config.CLICKY_ID else "")
CF_TAG = ("<script defer src=\"https://static.cloudflareinsights.com/beacon.min.js\" "
          f"data-cf-beacon='{{\"token\": \"{config.CF_BEACON}\"}}'></script>\n" if config.CF_BEACON else "")
# Cache-busting: a short hash of each file's contents, so browsers refetch the moment it changes.
ASSET_V = {n: __import__("hashlib").sha1((HERE / "static" / n).read_bytes()).hexdigest()[:10]
           for n in ("style.css", "site.js", "track.js")}
TODAY = datetime.date.today()

# key: (display name, short name, hub slug)
PLATFORMS = {
    "pc": ("PC", "PC", "pc"),
    "ps5": ("PlayStation 5", "PS5", "ps5"),
    "ps4": ("PlayStation 4", "PS4", "ps4"),
    "xseries": ("Xbox Series X|S", "Xbox Series", "xbox-series"),
    "xone": ("Xbox One", "Xbox One", "xbox-one"),
    "switch2": ("Nintendo Switch 2", "Switch 2", "switch-2"),
    "switch": ("Nintendo Switch", "Switch", "switch"),
    "mac": ("Mac", "Mac", "mac"),
    "linux": ("Linux", "Linux", "linux"),
    "ios": ("iPhone & iPad", "iOS", "ios"),
    "android": ("Android", "Android", "android"),
    "quest": ("Meta Quest", "Quest", None),
    "ps3": ("PlayStation 3", "PS3", None),
    "vita": ("PS Vita", "Vita", None),
    "x360": ("Xbox 360", "Xbox 360", None),
    "wiiu": ("Wii U", "Wii U", None),
    "3ds": ("Nintendo 3DS", "3DS", None),
    "ps2": ("PlayStation 2", "PS2", None),
    "psp": ("PSP", "PSP", None),
    "dreamcast": ("Dreamcast", "Dreamcast", None),
    "winphone": ("Windows Phone", "Windows Phone", None),
    "stadia": ("Stadia", "Stadia", None),
    "luna": ("Amazon Luna", "Luna", None),
    "geforcenow": ("GeForce Now", "GeForce Now", None),
    "xcloud": ("Xbox Cloud Gaming", "Xbox Cloud", None),
}
CLOUD = {"geforcenow", "xcloud", "stadia", "luna"}
IGDB_PLATFORMS = {6: "pc", 48: "ps4", 167: "ps5", 49: "xone", 169: "xseries", 130: "switch", 508: "switch2",
                  14: "mac", 3: "linux", 39: "ios", 34: "android", 9: "ps3", 46: "vita", 12: "x360",
                  41: "wiiu", 37: "3ds", 8: "ps2", 38: "psp", 23: "dreamcast", 74: "winphone", 170: "stadia",
                  384: "quest", 386: "quest", 471: "quest"}
GAMEPASS = ("console", "pc")
GP_DATE = load_json("gamepass.json", {}).get("fetched")
CROSSPROG = {"yes": ("Yes", "your progress follows your account between platforms."),
             "partial": ("Partly", "only some platforms share progress; see the notes above."),
             "no": ("No", "progress stays on the platform you played on.")}
CURRENT = ["pc", "ps5", "ps4", "xseries", "xone", "switch2", "switch", "mac", "linux", "ios", "android"]

# Families for the pair hubs ("PlayStation and PC crossplay games").
FAMILIES = {
    "pc": ("PC", {"pc"}),
    "playstation": ("PlayStation", {"ps5", "ps4"}),
    "xbox": ("Xbox", {"xseries", "xone"}),
    "switch": ("Switch", {"switch", "switch2"}),
    "mobile": ("Mobile", {"ios", "android"}),
    "mac": ("Mac", {"mac"}),
}
FAMILY_LONG = {"playstation": "PlayStation (PS5 & PS4)", "xbox": "Xbox (Series X|S & One)",
               "switch": "Nintendo Switch", "mobile": "mobile (iOS & Android)", "pc": "PC", "mac": "Mac"}

# Genre hubs: slug -> (title, test)
def _genre(*names):
    return lambda g: any(x["name"] in names for x in g.get("genres", []))


def _mode(name):
    return lambda g: any(x["name"] == name for x in g.get("game_modes", []))


def _theme(name):
    return lambda g: any(x["name"] == name for x in g.get("themes", []))


GENRES = {
    "shooters": ("Shooters", _genre("Shooter")),
    "co-op": ("Co-op games", _mode("Co-operative")),
    "split-screen": ("Games with split screen", _mode("Split screen")),
    "battle-royale": ("Battle royale games", _mode("Battle Royale")),
    "mmo": ("MMOs", _mode("Massively Multiplayer Online (MMO)")),
    "rpg": ("RPGs", _genre("Role-playing (RPG)")),
    "fighting": ("Fighting games", _genre("Fighting")),
    "racing": ("Racing games", _genre("Racing")),
    "sports": ("Sports games", _genre("Sport")),
    "strategy": ("Strategy games", _genre("Strategy", "Real Time Strategy (RTS)", "Turn-based strategy (TBS)")),
    "card-and-board": ("Card & board games", _genre("Card & Board Game")),
    "horror": ("Horror games", _theme("Horror")),
    "survival": ("Survival games", _theme("Survival")),
    "puzzle": ("Puzzle games", _genre("Puzzle")),
    "platformers": ("Platformers", _genre("Platform")),
    "simulation": ("Simulation games", _genre("Simulator")),
    "indie": ("Indie games", _genre("Indie")),
}

e = html.escape


def url(path):
    return config.BASE_PATH + path


def abs_url(path):
    return config.BASE_URL + path


def plist(keys, short=False):
    names = [PLATFORMS[k][1 if short else 0] for k in keys]
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def order(keys):
    return sorted(keys, key=lambda k: list(PLATFORMS).index(k))


def nice_date(d):
    d = datetime.date.fromisoformat(d) if isinstance(d, str) else d
    return d.strftime("%B %-d, %Y")


def domain(u):
    m = re.match(r"https?://(?:www\.)?([^/]+)", u)
    return m.group(1) if m else u


# ---------------------------------------------------------------- data model

def gp_key(title):
    """Match key for Game Pass catalogue titles: drop trademark signs, platform suffixes and edition words."""
    t = re.sub(r"[\u2122\u00ae\u00a9]", "", (title or "").lower())
    t = re.sub(r"\s*[-\u2013\u2014:(]\s*(for )?(xbox series x\|s|xbox one|windows( 10| pc)?|pc)\)?\s*$", "", t)
    t = re.sub(r"\b(standard|deluxe|game of the year|goty|definitive|complete|ultimate|digital|enhanced) edition\b", "", t)
    return norm(t)


def load_games():
    wiki, merged = merged_games()
    igdb = load_json("igdb.json", {})
    hist = load_json("history.json", {"games": {}, "log": []})
    trailers = load_json("trailers.json", {})
    gp = load_json("gamepass.json", {})
    gp_ids = {k: {p["id"].upper() for p in gp.get(k, []) if not p.get("free")} for k in GAMEPASS}
    gp_titles = {k: {gp_key(p["title"]) for p in gp.get(k, []) if not p.get("free")} for k in GAMEPASS}
    games, slugs = [], set()
    # A current game gets the plain slug even when an old discontinued version shares its name.
    live = {slugify(w["title"]) for w in merged if not w["discontinued"]}
    for w in merged:
        ig = igdb.get(w["igdb_key"]) or {}
        key = w["title"] + (" (discontinued)" if w["discontinued"] else "")
        slug = slugify(w["title"])
        if w["discontinued"] and slug in live:
            slug += "-discontinued"
        elif slug in slugs:
            slug += "-discontinued" if w["discontinued"] else "-2"
        slugs.add(slug)
        groups = []
        for gr in w["groups"]:
            plats = order(gr["platforms"])
            if plats:
                groups.append({"platforms": plats, "partial": [k for k, v in gr["platforms"].items() if v != "yes"],
                               "pc_stores": gr["pc_stores"], "others": gr["others"], "refs": gr["refs"]})
        on = {IGDB_PLATFORMS[p["id"]] for p in ig.get("platforms", []) if p["id"] in IGDB_PLATFORMS}
        # Researched entries can name platforms confirmed to have no crossplay ("separate"), or say the
        # game has none at all; each such platform becomes its own one-platform group.
        lone = set(w.get("separate", []))
        if w.get("crossplay") is False and not groups:
            lone |= on & set(CURRENT)  # "no crossplay" with no detail: every released platform is on its own
        for k in order(lone):
            groups.append({"platforms": [k], "partial": [], "pc_stores": [], "others": [], "refs": []})
        if not groups:
            continue
        in_groups = {k for gr in groups for k in gr["platforms"]}
        if "switch" in in_groups:
            in_groups_plus = in_groups | {"switch2"}  # Switch 2 runs Switch games; the list has no Switch 2 column
        else:
            in_groups_plus = in_groups
        companies = ig.get("involved_companies", [])
        g = {
            "title": w["title"], "slug": slug, "discontinued": w["discontinued"], "groups": groups,
            "wiki_link": w["wiki_link"], "igdb": ig,
            "available": order(on | in_groups),
            "outside": order((on - in_groups_plus) & set(CURRENT)) if not w["discontinued"] else [],
            "cover": (ig.get("cover") or {}).get("image_id"),
            "year": datetime.datetime.fromtimestamp(ig["first_release_date"], datetime.timezone.utc).year if ig.get("first_release_date") else None,
            "released": (datetime.datetime.fromtimestamp(ig["first_release_date"], datetime.timezone.utc).date()
                         if ig.get("first_release_date") else None),
            "developers": [c["company"]["name"] for c in companies if c.get("developer")],
            "publishers": [c["company"]["name"] for c in companies if c.get("publisher")],
            "genres": [x["name"] for x in ig.get("genres", [])],
            "popularity": (ig.get("total_rating_count") or 0) + (ig.get("hypes") or 0),
            "history": hist["games"].get(key, {}),
            "source": w["source"], "crossplay": w.get("crossplay", True), "notes": w.get("notes", []),
            "sources": w.get("sources", []),
            "checked": w.get("checked") or wiki.get("fetched", TODAY.isoformat()),
            "crossprog": w.get("crossprog"), "audited": w.get("audited"), "verdict": w.get("verdict"), "toggle": w.get("toggle") or [], "progress": w.get("progress") or [], "f2p": bool(w.get("f2p")), "news": w.get("news"),
            "trailer": next((v for v in trailer_candidates(ig)[:4] if trailers.get(v)), None),
            "shots": [x["image_id"] for x in ig.get("screenshots", []) if x.get("image_id")][:8],
        }
        ms_ids = {x["uid"].upper() for x in ig.get("external_games", [])
                  if x.get("external_game_source") == 11 and x.get("uid")}
        g["gamepass"] = [] if w["discontinued"] else [
            k for k in GAMEPASS if ms_ids & gp_ids[k] or {gp_key(w["title"]), gp_key(ig.get("name"))} & gp_titles[k]]
        g["hubs"] = [s for s, (_, test) in GENRES.items() if ig and test(ig)]
        games.append(g)
    return games, wiki, hist


def cross_groups(g):
    """Groups where at least two different platforms (or PC stores) play together."""
    return [gr for gr in g["groups"]
            if len([k for k in gr["platforms"] if k not in CLOUD]) >= 2 or len(gr["pc_stores"]) >= 2]


def together(g, a, b):
    """'yes' / 'partial' / 'no' / 'na' for whether platforms a and b play together."""
    if a not in g["available"] or b not in g["available"]:
        return "na"
    for gr in g["groups"]:
        if a in gr["platforms"] and b in gr["platforms"]:
            return "partial" if (a in gr["partial"] or b in gr["partial"]) else "yes"
    return "no"


def family_match(g, fa, fb):
    if g["discontinued"] or not g["crossplay"]:
        return False
    A, B = FAMILIES[fa][1], FAMILIES[fb][1]
    return any(set(gr["platforms"]) & A and set(gr["platforms"]) & B for gr in g["groups"])


def platform_match(g, k):
    return not g["discontinued"] and g["crossplay"] and any(k in gr["platforms"] and len(gr["platforms"]) >= 2 for gr in g["groups"])


# ---------------------------------------------------------------- text

def verdict(g):
    t = g["title"]
    cg = cross_groups(g)
    if g.get("verdict"):  # researched override, e.g. unreleased games with no crossplay announcement
        v = g["verdict"]
        return v.get("kind", "no"), v["word"], v["summary"]
    if g["discontinued"]:
        pools = "; ".join(plist(gr["platforms"]) for gr in g["groups"])
        return "ended", "No longer", f"{t} used to support crossplay ({pools}), but that has been discontinued."
    if not g["crossplay"]:
        plats = order({k for gr in g["groups"] for k in gr["platforms"]})
        if plats == ["pc"] and not g["outside"]:
            return "no", "No", f"{t} is only on PC, so there's no other platform to cross-play with yet."
        pools = [gr["platforms"] for gr in g["groups"] if len(gr["platforms"]) >= 2]
        same = "; ".join(plist(p, short=True) + " players can play together" for p in pools)
        return "no", "No", (f"{t} doesn't have crossplay: each platform family has its own players"
                            + (f". {same[0].upper() + same[1:]}." if same else "."))
    if not cg:
        gr = g["groups"][0]
        return "no", "Not really", (f"{t} only connects players on {plist(gr['platforms'])}"
                                    f"{' (' + ', '.join(gr['others']) + ')' if gr['others'] else ''}.")
    if len(cg) == 1:
        gr = cg[0]
        if len(gr["platforms"]) == 1 and gr["platforms"][0] == "pc":
            return "yes", "PC only", (f"{t} has cross-store play on PC: {', '.join(gr['pc_stores'])} players "
                                      f"can play together, but there's no console crossplay.")
        word = "Yes" if not gr["partial"] else "Mostly"
        cloud = [k for k in gr["platforms"] if k in CLOUD]
        main = [k for k in gr["platforms"] if k not in CLOUD]
        lone = [o["platforms"][0] for o in g["groups"] if len(o["platforms"]) == 1 and not o["pc_stores"]
                and o["platforms"][0] not in gr["platforms"]]
        if lone:
            word = "Partly"
        return "yes", word, (f"{t} supports crossplay between {plist(main)}."
                             + (f" {plist(lone)} {'is' if len(lone) == 1 else 'are'} separate." if lone else "")
                             + (f" You can also stream it via {plist(cloud)}." if cloud else ""))
    pools = "; ".join(plist([k for k in gr["platforms"] if k not in CLOUD]) for gr in cg)
    lone = [o["platforms"][0] for o in g["groups"] if len(o["platforms"]) == 1 and not o["pc_stores"]]
    return "split", "Partly", (f"{t} has crossplay, but players are split into {len(cg)} separate groups "
                               f"that can't meet: {pools}."
                               + (f" {plist(lone)} {'has' if len(lone) == 1 else 'have'} no crossplay." if lone else ""))


def single_platform(g):
    """True when the game is only on one platform, so there's no one to cross-play with."""
    return len(g["groups"]) == 1 and len(g["groups"][0]["platforms"]) == 1 and not g["outside"]


def pc_note(g):
    stores = sorted({s for gr in g["groups"] if "pc" in gr["platforms"] for s in gr["pc_stores"]})
    if not stores:
        return ""
    if not g["crossplay"] and len(stores) == 1:
        return ""
    if single_platform(g):
        return f"On PC it's sold on {' and '.join(stores) if len(stores) < 3 else ', '.join(stores[:-1]) + ' and ' + stores[-1]}."
    if len(stores) == 1:
        return f"On PC, the crossplay version is the {stores[0]} one."
    return f"On PC, crossplay covers {', '.join(stores[:-1])} and {stores[-1]}."


def multiplayer_facts(g):
    modes = g["igdb"].get("multiplayer_modes") or []
    gm = {x["name"] for x in g["igdb"].get("game_modes", [])}
    facts = []
    online = max([m.get("onlinemax") or 0 for m in modes] + [0])
    if online:
        facts.append(("Online players", f"Up to {online}"))
    coop = max([m.get("onlinecoopmax") or 0 for m in modes] + [0])
    if any(m.get("onlinecoop") for m in modes) or "Co-operative" in gm:
        facts.append(("Online co-op", f"Yes, up to {coop}" if coop else "Yes"))
    if any(m.get("splitscreen") for m in modes) or "Split screen" in gm:
        facts.append(("Split screen", "Yes"))
    elif modes:
        facts.append(("Split screen", "No"))
    if any(m.get("lancoop") for m in modes):
        facts.append(("LAN co-op", "Yes"))
    if "Massively Multiplayer Online (MMO)" in gm:
        facts.append(("Type", "MMO"))
    if "Battle Royale" in gm:
        facts.append(("Type", "Battle royale"))
    return facts


# ---------------------------------------------------------------- layout

NOINDEX = set()

FONTS = ("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&"
         "family=JetBrains+Mono:wght@500;700&family=Space+Grotesk:wght@600;700&display=swap")


def page(path, title, desc, body, schema=None, crumbs=None, noindex=False, image=None):
    canonical = abs_url(path)
    og_image = abs_url(image or "/og/default.png")
    if noindex:
        NOINDEX.add(path)
    robots = "" if config.INDEXABLE and not noindex else '<meta name="robots" content="noindex">\n'
    ld = ""
    blocks = list(schema or [])
    if crumbs:
        blocks.append({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, "item": abs_url(p)} for i, (n, p) in enumerate(crumbs)]})
    for b in blocks:
        ld += '<script type="application/ld+json">' + json.dumps(b, ensure_ascii=False).replace("</", "<\\/") + "</script>\n"
    crumb_html = ""
    if crumbs:
        crumb_html = '<nav class="crumbs" aria-label="Breadcrumb">' + " <span>/</span> ".join(
            f'<a href="{url(p)}">{e(n)}</a>' for n, p in crumbs[:-1]) + f" <span>/</span> {e(crumbs[-1][0])}</nav>"
    full_title = title if title.endswith(config.SITE_NAME) else f"{title} | {config.SITE_NAME}"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(full_title)}</title>
<meta name="description" content="{e(desc)}">
{robots}<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="{e(config.SITE_NAME)}">
<meta property="og:type" content="website">
<meta property="og:image" content="{og_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{url('/static/favicon.svg')}" type="image/svg+xml">
<link rel="apple-touch-icon" href="{url('/static/apple-touch-icon.png')}">
<link rel="alternate" type="application/rss+xml" title="{e(config.SITE_NAME)} updates" href="{url('/feed.xml')}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{url('/static/style.css')}?v={ASSET_V['style.css']}">
{config.AD_SCRIPT}
{VERIFY_TAGS}{GA_TAG}{CLICKY_TAG}{CF_TAG}{ld}</head>
<body>
<header class="top">
  <div class="wrap top-in">
    <a class="brand" href="{url('/')}" aria-label="{e(config.SITE_NAME)} home">
      <img src="{url('/static/favicon.svg')}" width="44" height="44" alt="">
      <span class="wm"><small>{e(config.LOGO_KICKER)}</small><span>{e(config.LOGO_WORD)}<i>.</i></span></span>
    </a>
    <nav class="mainnav">
      <a href="{url('/platforms/')}">Platforms</a>
      <a href="{url('/games/')}">All games</a>
      <a href="{url('/who-can-i-play-with/')}">Play together</a>
      <a href="{url('/coming-soon/')}">Coming soon</a>
      <a href="{url('/updates/')}">Updates</a>
    </nav>
    <form class="search" role="search" action="{url('/games/')}" onsubmit="return false">
      <input type="search" placeholder="Search a game…" aria-label="Search games" autocomplete="off" data-search>
      <div class="results" data-results hidden></div>
    </form>
  </div>
</header>
<main class="wrap">
{crumb_html}
{body}
</main>
<footer class="foot">
  <div class="wrap foot-in">
    <div>
      <p class="foot-brand">{e(config.SITE_NAME)}</p>
      <p>{e(config.TAGLINE)}</p>
      <p class="small">Crossplay facts come from the community-maintained
      <a href="https://en.wikipedia.org/wiki/List_of_video_games_that_support_cross-platform_play">Wikipedia list</a>
      (CC BY-SA 4.0) and the publishers' own announcements it cites. Game details from
      <a href="https://www.igdb.com/">IGDB</a>. Not affiliated with Sony, Microsoft, Nintendo, Valve, Epic or any publisher;
      all trademarks belong to their owners.</p>
    </div>
    <nav>
      <a href="{url('/about/')}">About</a>
      <a href="{url('/guides/crossplay-not-working/')}">Crossplay not working?</a>
      <a href="{url('/updates/')}">Recent changes</a>
      <a href="{url('/for-developers/')}">For developers</a>
      <a href="{url('/feed.xml')}">RSS feed</a>
{f"""<a href="{url('/newsletter/')}">Weekly email</a>""" if config.NEWSLETTER_API else ""}
      <a href="{url('/privacy/')}">Privacy</a>
      <a href="{correction_link()}">Report a mistake</a>
    </nav>
  </div>
</footer>
<script src="{url('/static/site.js')}?v={ASSET_V['site.js']}" defer></script>
<script src="{url('/static/track.js')}?v={ASSET_V['track.js']}" defer></script>
</body>
</html>
"""


NEWSLETTER_STATES = {
    "check": "Almost done: check your inbox for a confirmation email and click the button in it.",
    "invalid": "That email address doesn't look right. Please try again.",
    "confirming": "Confirming your subscription…",
    "confirmed": "You're subscribed. The next weekly email will land in your inbox.",
    "expired": "That confirmation link has expired. Sign up again below and we'll send a new one.",
    "error": "Something went wrong on our side. Please try again in a few minutes.",
}


def signup_box(uid):
    if not config.NEWSLETTER_API:
        return ""
    return f"""<section class="signup" id="signup" data-bar="New crossplay games and changes, once a week"><h2>New crossplay games, once a week</h2>
<p>Which games added crossplay this week, and what changed. One short email, unsubscribe in one click.</p>
<form action="{e(config.NEWSLETTER_API)}/subscribe" method="post"><input type="hidden" name="site" value="crossplay">
<input class="sr" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">
<label for="email-{uid}" class="sr">Email address</label>
<input id="email-{uid}" name="email" type="email" required placeholder="you@example.com" autocomplete="email">
<button type="submit" class="btn">Sign me up</button></form></section>"""


def newsletter_page():
    states = "".join(f'<p class="lede" data-state="{k}" hidden><strong>{e(v)}</strong></p>' for k, v in NEWSLETTER_STATES.items())
    script = f"""<script>
(() => {{
  const show = s => {{
    document.querySelectorAll("[data-state]").forEach(p => p.hidden = p.dataset.state !== s);
    const form = document.querySelector(".signup");
    if (form) form.style.display = ["check", "confirming", "confirmed"].includes(s) ? "none" : "";
  }};
  const t = new URLSearchParams(location.search).get("confirm");
  if (t) {{
    show("confirming");
    history.replaceState(null, "", location.pathname);
    fetch({json.dumps(config.NEWSLETTER_API + "/confirm")}, {{method: "POST", headers: {{"content-type": "application/json"}}, body: JSON.stringify({{t}})}})
      .then(r => r.json()).then(d => show(d.state === "invalid" ? "expired" : d.state)).catch(() => show("error"));
  }} else if (location.hash) show(location.hash.slice(1));
}})();
</script>"""
    body = (f'<section class="hub-head"><h1>The {e(config.SITE_NAME)} weekly email</h1>{states}'
            f'<p class="lede">Every week: games that just added crossplay, crossplay that changed or ended, and the '
            f'biggest updates. No spam.</p></section>{signup_box("page")}{script}')
    return page("/newsletter/", f"The {config.SITE_NAME} Weekly Email",
                "A weekly email with new crossplay games and changes to existing ones.", body,
                crumbs=[("Home", "/"), ("Newsletter", "/newsletter/")])


def newsletter_json(log, slug_by_title):
    """This week's content for the weekly email; the newsletter repo turns it into a Resend broadcast."""
    since = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    week = [x for x in log if x["date"] >= since and x["title"] in slug_by_title]
    labels = {"added": "New crossplay games", "crossplay details changed": "Crossplay changes"}
    sections = []
    for what, title in labels.items():
        items = [x for x in week if x["what"] == what]
        if not items:
            continue
        shown = [{"title": x["title"], "url": abs_url("/games/" + slug_by_title[x["title"]] + "/"), "note": nice_date(x["date"])}
                 for x in items[:12]]
        if len(items) > 12:
            shown.append({"title": f"…and {len(items) - 12} more", "url": abs_url("/updates/"), "note": "See every change"})
        sections.append({"title": title, "items": shown})
    added = sum(1 for x in week if x["what"] == "added")
    return json.dumps({
        "site": "crossplay",
        "date": datetime.date.today().isoformat(),
        "subject": f"{added} new crossplay game{'s' if added != 1 else ''} this week" if added else "Crossplay this week",
        "intro": "Here's what changed in crossplay this week.",
        "sections": sections,
    }, indent=1)


def correction_link(title=None):
    if config.CONTACT_EMAIL:
        # The address itself is assembled by site.js (see /contact/), so it never appears in the HTML.
        return url("/contact/") + ("?about=" + urllib.parse.quote(title) if title else "")
    subject = f"Correction: {title}" if title else "Correction"
    return "https://github.com/bigfootsbestfriend/crossplay/issues/new?title=" + e(subject.replace(" ", "+"))


def cover(g, size="t_cover_big", w=264, h=352, cls="cover"):
    if g["cover"]:
        return (f'<img class="{cls}" src="https://images.igdb.com/igdb/image/upload/{size}/{g["cover"]}.jpg" '
                f'width="{w}" height="{h}" alt="{e(g["title"])} cover art" loading="lazy">')
    initials = "".join(w[0] for w in re.findall(r"[A-Za-z0-9]+", g["title"])[:2]).upper()
    return f'<div class="{cls} cover-blank" aria-hidden="true"><span>{e(initials)}</span></div>'


HUBS = set()  # platform keys that have a hub page; filled in build() before game pages are rendered


class Raw(str):
    """Fact value that is already HTML (so it isn't escaped again)."""


def chip(k, cls="", link=False):
    """Platform chip. link=True makes it a link to the platform's hub (not inside cards, which are links already)."""
    if link and k in HUBS:
        return (f'<a class="chip p-{k} {cls}" href="{url("/platforms/" + PLATFORMS[k][2] + "/")}" '
                f'title="All {e(PLATFORMS[k][1])} crossplay games">{e(PLATFORMS[k][1])}</a>')
    return f'<span class="chip p-{k} {cls}">{e(PLATFORMS[k][1])}</span>'


def card(g):
    kind, word, _ = verdict(g)
    plats = order({k for gr in cross_groups(g) or g["groups"] for k in gr["platforms"] if k not in CLOUD})
    return (f'<a class="card" href="{url("/games/" + g["slug"] + "/")}">{cover(g, "t_cover_big", 132, 176)}'
            f'<span class="card-body"><span class="card-title">{e(g["title"])}</span>'
            f'<span class="tag v-{kind}">{e(word)}</span>'
            f'<span class="chips">{"".join(chip(k) for k in plats[:6])}{"<span class=more>+" + str(len(plats) - 6) + "</span>" if len(plats) > 6 else ""}</span>'
            f'</span></a>')


def grid(games):
    return '<div class="grid">' + "".join(card(g) for g in games) + "</div>"


# ---------------------------------------------------------------- pages

def plist_words(xs):
    xs = list(xs)
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def game_page(g, games):
    t = g["title"]
    kind, word, summary = verdict(g)
    cg = cross_groups(g) or g["groups"]
    pcn = pc_note(g)
    parts = []

    # Answer box
    extra = list(g["notes"])
    if pcn:
        extra.append(pcn)
    if g["outside"] and g["source"] == "manual":
        extra.append(f"The {plist(g['outside'])} version{'s' if len(g['outside']) > 1 else ''} "
                     f"{'doesn' if len(g['outside']) == 1 else 'don'}'t have crossplay with other platforms.")
    elif g["outside"]:
        extra.append(f"{t} has also been released on {plist(g['outside'])}, but our sources don't list "
                     f"crossplay for {'that version' if len(g['outside']) == 1 else 'those versions'}. "
                     f"Check before you buy for that platform.")
    if any(gr["partial"] for gr in g["groups"]):
        extra.append("Some platforms are marked as partial support: crossplay works with limits "
                     "(for example only some modes, or an opt-in setting).")
    byline = (f'Researched by <a href="{url('/about/')}#who">{e(config.AUTHOR)}</a> · '
              if g["source"] == "manual" and config.AUTHOR else "")
    xprog = ""
    if g["crossprog"] and not g["progress"]:
        w_, why = CROSSPROG[g["crossprog"]]
        xprog = f'<p class="xprog"><span class="tag x-{g["crossprog"]}">Cross-progression: {w_}</span> {e(why[0].upper() + why[1:])}</p>'
    watch = ""
    if config.NEWSLETTER_API:
        ask = f"Tell me if {t} gets crossplay" if kind in ("no", "ended") else f"Tell me when {t}'s crossplay changes"
        watch = (f'<p class="watch"><button type="button" class="btn-watch" data-signup>{e(ask)}</button> '
                 f'<span class="small">in our free weekly email</span></p>')
    # "Your group": the platforms saved on this device (shared with the group finder) checked against this
    # game, plus a one-tap "did it work?" vote. Filled in by site.js.
    mine = ""
    if not g.get("verdict") and not g["discontinued"]:
        on = set(g["available"]) | {k for gr in g["groups"] for k in gr["platforms"]}
        if "switch" in on:
            on.add("switch2")  # Switch 2 runs Switch games
        mdata = json.dumps({"slug": g["slug"], "api": config.API_URL or "",
                            "groups": [{"p": gr["platforms"], "x": gr["partial"]} for gr in g["groups"]],
                            "on": [k for k in CURRENT if k in on],
                            "names": {k: PLATFORMS[k][1] for k in CURRENT if k != "linux"},
                            "finder": url("/who-can-i-play-with/")}, separators=(",", ":"))
        mine = f'''<div class="mine" data-mine='{e(mdata)}' hidden></div>'''
    parts.append(f"""
<section class="answer v-{kind}">
  <div class="answer-cover">{cover(g)}</div>
  <div class="answer-body">
    <p class="kicker">Is {e(t)} cross-platform?</p>
    <h1>{e(t)} crossplay</h1>
    <p class="verdict"><span class="badge v-{kind}">{e(word)}</span> {e(summary)}</p>
    {"".join(f'<p>{e(x)}</p>' for x in extra)}
    {xprog}
    {mine}
    {watch}
    <p class="checked">{byline}Last checked {nice_date(g["checked"])}
    {f' · Details last changed {nice_date(g["history"]["changed"])}' if g["history"].get("changed") and g["history"]["changed"] != g["history"].get("first_seen") else ''}</p>
  </div>
</section>""")

    # Groups
    rows = []
    for i, gr in enumerate(g["groups"], 1):
        label = (PLATFORMS[gr["platforms"][0]][1] + " only" if len(gr["platforms"]) == 1 and not gr["pc_stores"]
                 and len(g["groups"]) > 1 else f"Group {i}" if len(g["groups"]) > 1
                 else "Only on" if single_platform(g) else "Plays together")
        stores = f'<p class="small">PC stores: {e(", ".join(gr["pc_stores"]))}</p>' if gr["pc_stores"] else ""
        partial = (f'<p class="small">Partial support: {e(plist(gr["partial"]))}</p>' if gr["partial"] else "")
        others = f'<p class="small">Also: {e(", ".join(gr["others"]))}</p>' if gr["others"] else ""
        rows.append(f'<div class="pool"><h3>{label}</h3><div class="chips big">'
                    f'{"".join(chip(k, "partial" if k in gr["partial"] else "", link=True) for k in gr["platforms"])}</div>'
                    f'{stores}{partial}{others}</div>')
    if g["outside"]:
        known = g["source"] == "manual"
        rows.append(f'<div class="pool outside"><h3>{"No crossplay" if known else "Not confirmed"}</h3><div class="chips big">'
                    f'{"".join(chip(k, link=True) for k in g["outside"])}</div>'
                    + ('<p class="small">These versions don&#39;t have crossplay with other platforms. See the notes above for details.</p></div>'
                       if known else '<p class="small">Released here, but no crossplay source lists this version (or it may no longer be sold).</p></div>'))
    heading = ("Who can play with whom" if len(g["groups"]) > 1 or g["outside"]
               else "Where you can play it" if single_platform(g) else "Platforms that play together")
    if not g.get("verdict"):
        parts.append(f'<section><h2>{heading}</h2><div class="pools">{"".join(rows)}</div></section>')
    parts.append(signup_box("game"))

    # Settings and progression get their own headings: they match the searches people make after
    # "is it crossplay" ("how to turn off crossplay in X", "X cross progression").
    fix_link = (f'<p class="small">Crossplay not working even with the setting on? '
                f'<a href="{url("/guides/crossplay-not-working/")}">Check these console and PC settings</a>.</p>')
    if g["toggle"] and not g.get("verdict"):
        parts.append(f'<section id="settings"><h2>How to turn crossplay on or off in {e(t)}</h2>'
                     + "".join(f"<p>{e(x)}</p>" for x in g["toggle"]) + fix_link + "</section>")
    if g["progress"] and not g.get("verdict"):
        tag = ""
        if g["crossprog"]:
            tag = f'<p class="xprog"><span class="tag x-{g["crossprog"]}">Cross-progression: {CROSSPROG[g["crossprog"]][0]}</span></p>'
        parts.append(f'<section id="progress"><h2>Does {e(t)} have cross-progression?</h2>{tag}'
                     + "".join(f"<p>{e(x)}</p>" for x in g["progress"]) + "</section>")
    if kind in ("yes", "partial") and not g["toggle"] and not g.get("verdict"):
        parts.append(f'<section class="fix">{fix_link}</section>')

    # Checker + pair table
    items = []
    avail = [k for k in g["available"] if k in CURRENT or any(k in gr["platforms"] for gr in g["groups"])]
    avail = [k for k in avail if k not in CLOUD]
    pairs = []
    for i, a in enumerate(avail):
        for b in avail[i + 1:]:
            pairs.append((a, b, together(g, a, b)))
    if len(avail) >= 2 and not g["discontinued"] and not g.get("verdict"):
        opts = "".join(f'<option value="{k}">{e(PLATFORMS[k][0])}</option>' for k in avail)
        data = json.dumps({"groups": [{"p": gr["platforms"], "x": gr["partial"]} for gr in g["groups"]],
                           "names": {k: PLATFORMS[k][0] for k in avail}, "title": t})
        parts.append(f"""
<section class="checker" data-checker='{e(data)}'>
  <h2>Check your two platforms</h2>
  <div class="checker-row">
    <label>I play on <select data-a>{opts}</select></label>
    <label>my friend plays on <select data-b>{opts}</select></label>
  </div>
  <p class="checker-out" data-out aria-live="polite"></p>
</section>""")
        word_for = {"yes": "Yes", "partial": "Partly", "no": "No"}
        faq = [(a, b, r) for a, b, r in pairs if r != "na"]
        faq.sort(key=lambda x: (x[2] != "yes", CURRENT.index(x[0]) if x[0] in CURRENT else 99))
        items = []
        for a, b, r in faq[:8]:
            q = f"Can {PLATFORMS[a][1]} and {PLATFORMS[b][1]} players play {t} together?"
            if r == "yes":
                ans = f"Yes. {PLATFORMS[a][1]} and {PLATFORMS[b][1]} are in the same crossplay group."
                gr = next(gr for gr in g["groups"] if a in gr["platforms"] and b in gr["platforms"])
                if "pc" in (a, b) and gr["pc_stores"]:
                    ans += f" On PC that covers {plist_words(gr['pc_stores'])}."
                if g["crossprog"] == "yes":
                    ans += " Your progress also carries over between them."
            elif r == "partial":
                lim = [k for k in (a, b) if any(k in gr["partial"] for gr in g["groups"])]
                ans = (f"Partly. Crossplay works with limits on {plist(lim)}"
                       + (f". {g['notes'][0]}" if g["notes"] and len(g["notes"][0]) < 200 else ".") if lim else "Partly. Crossplay between them is listed with limits.")
            else:
                ans = f"No. {PLATFORMS[a][1]} and {PLATFORMS[b][1]} players are matched separately."
            items.append((q, ans, r))
        if items:
            parts.append('<section><h2>Quick answers</h2><dl class="faq">' + "".join(
                f'<div class="qa r-{r}"><dt>{e(q)}</dt><dd><span class="dot"></span>{e(a)}</dd></div>'
                for q, a, r in items) + "</dl></section>")

    # Trailer + screenshots. The YouTube player only loads on click (site.js), so pages stay fast and
    # YouTube sets no cookies until a reader asks for the video.
    if g["trailer"] or g["shots"]:
        media = ""
        if g["trailer"]:
            media += (f'<button class="yt" type="button" data-yt="{e(g["trailer"])}" aria-label="Play the {e(t)} trailer">'
                      f'<img src="https://i.ytimg.com/vi/{e(g["trailer"])}/hqdefault.jpg" width="480" height="360" '
                      f'alt="{e(t)} trailer" loading="lazy"><span class="yt-play" aria-hidden="true"></span></button>')
        if g["shots"]:
            n = len(g["shots"])
            thumbs = []
            for i, s in enumerate(g["shots"], 1):
                more = f'<span class="more-shots">+{n - 4} more</span>' if i == 4 and n > 4 else ""
                thumbs.append(
                    f'<a href="https://images.igdb.com/igdb/image/upload/t_1080p/{s}.jpg" target="_blank" rel="noopener"'
                    f'{" hidden" if i > 4 else ""} aria-label="{e(t)} screenshot {i} of {n}">'
                    f'<img src="https://images.igdb.com/igdb/image/upload/t_screenshot_med/{s}.jpg" width="569" height="320" '
                    f'alt="{e(t)} screenshot {i} of {n}" loading="lazy">{more}</a>')
            media += (f'<p class="shots-label">{n} screenshot{"s" if n != 1 else ""}'
                      f'<span class="small"> · tap to enlarge</span></p>'
                      f'<div class="shots" data-lightbox data-title="{e(t)}">' + "".join(thumbs) + "</div>")
        head = "trailer and screenshots" if g["trailer"] and g["shots"] else "trailer" if g["trailer"] else "screenshots"
        parts.append(f'<section class="media"><h2>{e(t)} {head}</h2>{media}'
                     + ('<p class="small">The trailer plays from YouTube when you press play.'
                        + (' Screenshots via IGDB.' if g["shots"] else '') + '</p>' if g["trailer"]
                        else '<p class="small">Screenshots via IGDB.</p>')
                     + "</section>")

    # Player reports (only when the community API is configured)
    if config.API_URL and not g["discontinued"]:
        plats = {k: PLATFORMS[k][0] for k in avail} if len(avail) >= 2 else {k: PLATFORMS[k][0] for k in g["available"] if k not in CLOUD}
        cdata = json.dumps({"slug": g["slug"], "title": t, "plats": plats, "api": config.API_URL,
                            "turnstile": config.TURNSTILE_SITEKEY})
        parts.append(f"""
<section class="community" id="community" data-community='{e(cdata)}' hidden>
  <h2>Did crossplay work for you?</h2>
  <form class="vote" data-vote>
    <label>I played on <select name="a"></select></label>
    <label>with someone on <select name="b"></select></label>
    <span class="vote-btns"><button type="submit" name="result" value="yes" class="btn yes">It worked</button>
    <button type="submit" name="result" value="no" class="btn no">It didn't</button></span>
  </form>
  <p class="tally" data-tally aria-live="polite"></p>
  <h2>Player tips</h2>
  <div class="tips" data-tips></div>
  <details class="tipform">
    <summary>Add a tip or report a problem</summary>
    <form data-post>
      <label>Type <select name="kind"><option value="review">Tip or short review</option>
        <option value="report">Something on this page is wrong</option></select></label>
      <label>Your name <input name="name" maxlength="40" placeholder="Shown with your tip (optional)"></label>
      <label>Platform you play on <select name="platform"></select></label>
      <label>Your tip <textarea name="body" maxlength="600" rows="4" required
        placeholder="e.g. Crossplay only worked after we both linked an EA account."></textarea></label>
      <input name="website" class="hp" tabindex="-1" autocomplete="off" aria-hidden="true">
      <div data-ts></div>
      <button class="btn" type="submit">Send</button>
      <p class="small">Tips are checked by a person before they appear. Don't include personal details.</p>
      <p class="sent" data-sent aria-live="polite"></p>
    </form>
  </details>
</section>""")

    # Multiplayer + game facts
    mp = multiplayer_facts(g)
    facts = []
    if g["released"]:
        facts.append(("Released", nice_date(g["released"])))
    if g["developers"]:
        facts.append(("Developer", ", ".join(g["developers"][:2])))
    if g["publishers"]:
        facts.append(("Publisher", ", ".join(g["publishers"][:2])))
    if g["genres"]:
        facts.append(("Genre", ", ".join(g["genres"][:3])))
    if g["available"]:
        facts.append(("Platforms", Raw('<span class="chips">' + "".join(
            chip(k, link=True) for k in g["available"] if k not in CLOUD) + "</span>")))
    if g["gamepass"]:
        facts.append(("Game Pass", {("console", "pc"): "Console and PC", ("console",): "Console",
                                    ("pc",): "PC"}[tuple(g["gamepass"])] + f" (as of {nice_date(GP_DATE)})"))
    if g["crossprog"]:
        facts.append(("Cross-progression", CROSSPROG[g["crossprog"]][0]))
    if mp or facts:
        # Only use two columns when both panels have something in them; otherwise the left one sits empty.
        parts.append(f'<section class="{"two" if mp and facts else "one"}"><div>' +
                     ('<h2>Multiplayer at a glance</h2><dl class="facts">' +
                      "".join(f"<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>" for a, b in mp) +
                      '</dl><p class="small">From IGDB\'s multiplayer data; modes can differ by platform.</p>'
                      if mp else "") +
                     '</div><div>' + ('<h2>Game details</h2><dl class="facts">' +
                     "".join(f"<div><dt>{e(a)}</dt><dd>{b if isinstance(b, Raw) else e(b)}</dd></div>" for a, b in facts) +
                     "</dl>" if facts else "") + "</div></section>")

    # Sources
    refs = sorted({r for gr in g["groups"] for r in gr["refs"]})
    src = "".join(f'<li><a href="{e(r)}" rel="nofollow noopener" target="_blank">{e(domain(r))}</a></li>' for r in refs)
    src += "".join(f'<li><a href="{e(s["url"])}" rel="nofollow noopener" target="_blank">{e(s["title"])}</a> '
                   f'<span class="small">({e(domain(s["url"]))})</span></li>' for s in g["sources"])
    if g["source"] == "wikipedia":
        wiki = "https://en.wikipedia.org/wiki/List_of_video_games_that_support_cross-platform_play"
        src += (f'<li><a href="{wiki}" rel="noopener" target="_blank">Wikipedia: List of video games that support '
                f'cross-platform play</a> (CC BY-SA 4.0)</li>')
    if g["igdb"].get("url"):
        src += f'<li><a href="{e(g["igdb"]["url"])}" rel="noopener" target="_blank">IGDB entry</a> (release and multiplayer details)</li>'
    parts.append(f"""<section class="sources"><h2>Sources</h2><ul>{src}</ul>
<p class="small">Crossplay changes with patches. If something here is out of date,
<a href="{correction_link(t)}">tell us</a> and we'll fix it.</p></section>""")

    # Related
    same = [x for x in games if x is not g and not x["discontinued"] and x["crossplay"]
            and set(x["hubs"]) & set(g["hubs"])]
    same.sort(key=lambda x: (-len(set(x["hubs"]) & set(g["hubs"])), -x["popularity"]))
    if same:
        parts.append(f'<section><h2>More crossplay games like {e(t)}</h2>{grid(same[:6])}</section>')
    hub_links = [f'<a class="pill" href="{url("/genre/" + h + "/")}">Crossplay {e(GENRES[h][0].lower())}</a>' for h in g["hubs"][:4]]
    for gr in cg:
        for k in gr["platforms"]:
            if PLATFORMS[k][2] and not g["discontinued"]:
                hub_links.append(f'<a class="pill" href="{url("/platforms/" + PLATFORMS[k][2] + "/")}">{e(PLATFORMS[k][1])} crossplay games</a>')
    if hub_links:
        parts.append('<nav class="pills">' + "".join(dict.fromkeys(hub_links)) + "</nav>")

    # Schema
    faq_schema = []
    if len(avail) >= 2 and not g["discontinued"] and items:
        faq_schema = [{"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": f"Is {t} cross-platform?",
             "acceptedAnswer": {"@type": "Answer", "text": summary}}] + [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a, _ in items[:6]]}]
    if not g.get("verdict") and (g["toggle"] or g["progress"]):
        extra_q = []
        if g["toggle"]:
            extra_q.append((f"How do I turn crossplay on or off in {t}?", " ".join(g["toggle"])))
        if g["progress"]:
            lead = CROSSPROG[g["crossprog"]][0] + ". " if g["crossprog"] else ""
            extra_q.append((f"Does {t} have cross-progression?", lead + " ".join(g["progress"])))
        qs = [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in extra_q]
        if faq_schema:
            faq_schema[0]["mainEntity"] += qs
        else:
            faq_schema = [{"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": qs}]
    vg = {"@context": "https://schema.org", "@type": "VideoGame", "name": t,
          "gamePlatform": [PLATFORMS[k][0] for k in g["available"]], "url": abs_url("/games/" + g["slug"] + "/")}
    if g["cover"]:
        vg["image"] = f"https://images.igdb.com/igdb/image/upload/t_cover_big/{g['cover']}.jpg"
    if g["genres"]:
        vg["genre"] = g["genres"]
    if g["developers"]:
        vg["author"] = [{"@type": "Organization", "name": n} for n in g["developers"][:2]]
    if g["publishers"]:
        vg["publisher"] = [{"@type": "Organization", "name": n} for n in g["publishers"][:2]]

    title = f"Is {t} Cross-Platform? Crossplay Explained"
    if g["discontinued"]:
        title = f"Is {t} Still Cross-Platform? (Crossplay Ended)"
    desc = summary + (" " + pcn if pcn else "")
    # Only researched pages that have passed the deep audit (research/audit.md) go to search engines; the rest
    # stay visible to readers but are noindexed until audited.
    return page("/games/" + g["slug"] + "/", title, desc[:300], "\n".join(parts), [vg] + faq_schema,
                [("Home", "/"), ("Games", "/games/"), (t, "/games/" + g["slug"] + "/")],
                noindex=not g.get("audited"), image="/og/" + g["slug"] + ".png")


TOOL_PLATS = [("pc", "PC"), ("ps5", "PS5"), ("xseries", "Xbox Series"), ("switch2", "Switch 2"), ("switch", "Switch"), ("mobile", "Mobile")]


def list_tools(n):
    """Search, platform chips and sort for a long game table (site.js). The table HTML stays A to Z and fully shown."""
    chips = "".join(f'<button type="button" class="chip p-{"ios" if k == "mobile" else k}" data-p="{k}">{e(lbl)}</button>' for k, lbl in TOOL_PLATS)
    return (f'<div class="ltools" data-ltools><input type="search" placeholder="Filter these {n} games" aria-label="Filter games" data-lq>'
            f'<div class="lrow"><div class="lchips" role="group" aria-label="Plays on"><span>Plays on</span>'
            f'<button type="button" class="chip on" data-p="">Any</button>{chips}</div>'
            f'<label class="lsort"><span>Sort</span><select data-lsort><option value="n">A to Z</option><option value="y">Newest first</option>'
            f'<option value="c">Most platforms</option></select></label></div>'
            f'<p class="small" data-lcount aria-live="polite">Showing all {n} games</p></div>')


def list_table(games, show=None):
    rows = []
    for g in games:
        kind, word, _ = verdict(g)
        plats = order({k for gr in cross_groups(g) or g["groups"] for k in gr["platforms"] if k not in CLOUD})
        tags = set(plats) | ({"mobile"} if {"ios", "android"} & set(plats) else set())
        rows.append(f'<tr data-n="{e(g["title"].lower())}" data-p="{" ".join(sorted(tags))}" data-y="{g["year"] or 0}" data-c="{len(plats)}">'
                    f'<td class="t"><a href="{url("/games/" + g["slug"] + "/")}">{cover(g, "t_thumb", 45, 60, "thumb")}'
                    f'<span>{e(g["title"])}</span></a></td>'
                    f'<td><span class="tag v-{kind}">{e(word)}</span></td>'
                    f'<td class="chips">{"".join(chip(k) for k in plats)}</td>'
                    f'<td class="y">{g["year"] or ""}</td></tr>')
    return ((list_tools(len(games)) if len(games) > 20 else "") +
            '<div class="tablewrap"><table class="list"><thead><tr><th>Game</th><th>Crossplay</th>'
            '<th>Plays together</th><th>Year</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")


def together_tool(heading="h2"):
    """Group finder: everyone picks their platform, the page lists games that put all of them in one lobby."""
    plats = [k for k in CURRENT if k != "linux"]
    opts = "".join(f'<option value="{k}">{e(PLATFORMS[k][1])}</option>' for k in plats)
    genres = "".join(f'<option value="{k}">{e(v[0])}</option>' for k, v in GENRES.items())
    return f"""<section class="together" data-together data-src="{url('/static/together.json')}">
  {f"<{heading}>Who can I play with?</{heading}>" if heading else ""}
  <p class="small">Pick everyone's platform. We'll list the games that put all of you in the same lobby.</p>
  <div class="people" data-people data-opts='{e(opts)}'></div>
  <div class="together-controls">
    <button type="button" class="btn ghost" data-add>+ Add a friend</button>
    <button type="button" class="btn ghost" data-share-group>Share this group</button>
    <label>Genre <select data-genre><option value="">Any</option>{genres}</select></label>
    <label class="check"><input type="checkbox" data-checked> Only games we've checked</label>
    <label class="check"><input type="checkbox" data-free> Free to play</label>
  </div>
  <p class="together-count" data-count aria-live="polite"></p>
  <ul class="together-list" data-list></ul>
  <button type="button" class="btn ghost" data-more hidden>Show more</button>
</section>"""


def best_page(path, title, h1, intro, games, crumbs, note=""):
    """A ranked list built only from games we've checked, with the facts that matter for choosing one."""
    games = sorted(games, key=lambda g: -g["popularity"])[:25]
    items = []
    for i, g in enumerate(games, 1):
        plats = order({k for gr in cross_groups(g) or g["groups"] for k in gr["platforms"] if k not in CLOUD})
        facts = []
        if g.get("f2p"):
            facts.append("Free to play" + (" (multiplayer)" if g["title"] == "Halo Infinite" else ""))
        if g["crossprog"]:
            facts.append("Cross-progression: " + CROSSPROG[g["crossprog"]][0].lower())
        if "co-op" in g["hubs"]:
            facts.append("Co-op")
        first = re.split(r"(?<=[.!?])\s+", g["notes"][0])[0] if g["notes"] else ""
        items.append(f'''<li class="best"><span class="best-n">{i}</span>{cover(g, "t_cover_big", 90, 120)}<div class="best-body">
<h2><a href="{url("/games/" + g["slug"] + "/")}">{e(g["title"])}</a></h2>
<div class="chips">{"".join(chip(k) for k in plats)}</div>
{f'<p class="small">{" · ".join(facts)}</p>' if facts else ""}<p>{e(first)}</p></div></li>''')
    body = (f'<section class="hub-head"><h1>{e(h1)}</h1><p class="lede">{intro}</p></section>'
            f'<section><ol class="bestlist">{"".join(items)}</ol>'
            f'<p class="small">Ranked by popularity (IGDB player and search interest), and limited to games we\'ve checked against '
            f'official sources. {note}Each game\'s page has the full crossplay details and sources.</p></section>')
    schema = [{"@context": "https://schema.org", "@type": "ItemList", "name": h1, "numberOfItems": len(games),
               "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": g["title"],
                                    "url": abs_url("/games/" + g["slug"] + "/")} for i, g in enumerate(games)]}]
    return page(path, title, re.sub("<[^>]+>", "", intro)[:300], body, schema, crumbs)


def hub_page(path, title, h1, intro, games, crumbs, extra=""):
    games = sorted(games, key=lambda g: -g["popularity"])
    # Only games we've checked by hand are presented as verified; the rest come straight from the Wikipedia list.
    checked = [g for g in games if g.get("audited")]
    rest = [g for g in games if not g.get("audited")]
    body = f'<section class="hub-head"><h1>{e(h1)}</h1><p class="lede">{intro}</p></section>'
    if checked:
        body += (f'<section><h2>Checked by us ({len(checked)})</h2>'
                 f'<p class="small">We researched these against official sources and re-check them regularly.</p>'
                 + (grid(checked[:8]) if len(checked) > 4 else "") + list_table(checked) + "</section>")
    if rest:
        body += (f'<section><h2>{"Not yet verified" if checked else "All games"} ({len(rest)})</h2>'
                 f'<p class="small">These come from the community-maintained Wikipedia crossplay list and we '
                 f'haven&#39;t checked them by hand yet. Check before you buy.</p>{list_table(rest)}</section>')
    body += extra
    listed = checked or games
    schema = [{"@context": "https://schema.org", "@type": "ItemList", "name": h1, "numberOfItems": len(listed),
               "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": g["title"],
                                    "url": abs_url("/games/" + g["slug"] + "/")} for i, g in enumerate(listed[:50])]}]
    return page(path, title, re.sub("<[^>]+>", "", intro)[:300], body, schema, crumbs)


def build():
    games, wiki, hist = load_games()
    current = [g for g in games if not g["discontinued"] and g["crossplay"]]
    nocross = [g for g in games if not g["discontinued"] and not g["crossplay"]]
    fetched = wiki.get("fetched", TODAY.isoformat())
    pages = {}

    HUBS.update(k for k in CURRENT if PLATFORMS[k][2] and sum(1 for g in current if platform_match(g, k)) >= 3)
    for g in games:
        pages["/games/" + g["slug"] + "/"] = game_page(g, games)

    # Platform hubs
    plat_cards = []
    for k in CURRENT:
        name, short, slug = PLATFORMS[k]
        matched = [g for g in current if platform_match(g, k)]
        if len(matched) < 3:
            continue
        partners = defaultdict(int)
        for g in matched:
            for gr in g["groups"]:
                if k in gr["platforms"]:
                    for o in gr["platforms"]:
                        if o != k and o not in CLOUD:
                            partners[o] += 1
        top = sorted(partners.items(), key=lambda x: -x[1])
        partner_txt = ", ".join(f"{PLATFORMS[o][1]} ({n})" for o, n in top[:5])
        intro = (f"{len(matched)} games let {e(short)} players team up with or play against people on other "
                 f"platforms. Most often that's {e(partner_txt)}. Tap a game to see exactly which platforms "
                 f"are in its crossplay pool.")
        pages[f"/platforms/{slug}/"] = hub_page(
            f"/platforms/{slug}/", f"{short} Crossplay Games: All {len(matched)} Cross-Platform Games",
            f"{name} crossplay games", intro, matched,
            [("Home", "/"), ("Platforms", "/platforms/"), (short, f"/platforms/{slug}/")])
        plat_cards.append((k, len(matched)))

    # Pair hubs
    pair_links = []
    fams = list(FAMILIES)
    for i, fa in enumerate(fams):
        for fb in fams[i + 1:]:
            matched = [g for g in current if family_match(g, fa, fb)]
            if len(matched) < 3:
                continue
            a, b = FAMILIES[fa][0], FAMILIES[fb][0]
            slug = f"{fa}-and-{fb}"
            intro = (f"{len(matched)} games have crossplay between {e(FAMILY_LONG[fa])} and {e(FAMILY_LONG[fb])}. "
                     f"Some only link one console generation, so check the game page for the exact pairing "
                     f"before you buy.")
            pages[f"/crossplay/{slug}/"] = hub_page(
                f"/crossplay/{slug}/", f"{a} and {b} Crossplay Games ({len(matched)} Games)",
                f"{a} and {b} crossplay games", intro, matched,
                [("Home", "/"), ("Platforms", "/platforms/"), (f"{a} + {b}", f"/crossplay/{slug}/")])
            pair_links.append((slug, a, b, len(matched)))

    # Genre hubs
    genre_links = []
    for slug, (name, _) in GENRES.items():
        matched = [g for g in current if slug in g["hubs"]]
        if len(matched) < 5:
            continue
        intro = (f"{len(matched)} {e(name.lower())} you can play across platforms, sorted by popularity. "
                 f"Each game page shows which consoles, PC stores and phones share servers.")
        pages[f"/genre/{slug}/"] = hub_page(
            f"/genre/{slug}/", f"Crossplay {name}: {len(matched)} Cross-Platform Picks",
            f"Crossplay {name.lower()}", intro, matched,
            [("Home", "/"), ("Games", "/games/"), (f"Crossplay {name.lower()}", f"/genre/{slug}/")])
        genre_links.append((slug, name, len(matched)))

    # Game Pass hub
    gp_games = sorted([g for g in current if g["gamepass"]], key=lambda g: -g["popularity"])
    if gp_games and GP_DATE:
        pages["/game-pass/"] = hub_page(
            "/game-pass/", f"Crossplay Games on Xbox Game Pass ({len(gp_games)} Games)",
            "Crossplay games on Game Pass",
            f"{len(gp_games)} crossplay games are in the Xbox Game Pass library right now (checked {nice_date(GP_DATE)}), "
            f"so a Game Pass subscriber can play them with friends on PlayStation, Switch or Steam. "
            f"Free-to-play games aren't listed here, since they don't need Game Pass.",
            gp_games, [("Home", "/"), ("Platforms", "/platforms/"), ("Game Pass", "/game-pass/")])

    # Platforms index
    pc = "".join(f'<a class="plat p-{k}" href="{url("/platforms/" + PLATFORMS[k][2] + "/")}">'
                 f'<b>{e(PLATFORMS[k][1])}</b><span>{n} games</span></a>' for k, n in plat_cards)
    pl = "".join(f'<a class="pill" href="{url("/crossplay/" + s + "/")}">{e(a)} + {e(b)} <small>{n}</small></a>'
                 for s, a, b, n in pair_links)
    pages["/platforms/"] = page("/platforms/", "Crossplay Games by Platform",
                                "Find cross-platform games for PS5, Xbox, Switch, PC, Mac and mobile, or pick two platforms.",
                                f'<section class="hub-head"><h1>Crossplay by platform</h1><p class="lede">Pick your '
                                f'platform, or a pair of them, to see every game that lets you play together.</p></section>'
                                f'<section><div class="plats">{pc}</div></section>'
                                f'<section><h2>Two platforms</h2><nav class="pills">{pl}</nav></section>'
                                + (f'<section><h2>Subscriptions</h2><nav class="pills"><a class="pill" href="{url("/game-pass/")}">'
                                   f'Crossplay games on Game Pass <small>{len(gp_games)}</small></a></nav></section>' if gp_games else ""),
                                crumbs=[("Home", "/"), ("Platforms", "/platforms/")])

    # All games
    gl = "".join(f'<a class="pill" href="{url("/genre/" + s + "/")}">{e(n)} <small>{c}</small></a>' for s, n, c in genre_links)
    disc = [g for g in games if g["discontinued"]]
    pages["/games/"] = page(
        "/games/", f"All {len(current)} Crossplay Games (A–Z)",
        f"Every game we track with cross-platform play: {len(current)} games, with the platforms that play together.",
        f'<section class="hub-head"><h1>Every crossplay game we track</h1><p class="lede">{len(current)} games with '
        f'cross-platform play, A to Z. Use the search box to jump straight to one.</p></section>'
        f'<section><h2>By genre</h2><nav class="pills">{gl}</nav></section>'
        f'<section><h2>A–Z</h2>{list_table(sorted(current, key=lambda g: g["title"].lower().lstrip("#")))}</section>'
        + (f'<section><h2>No crossplay</h2><p>Popular multiplayer games where each platform plays separately. '
           f'We keep checking these in case that changes.</p>{list_table(sorted(nocross, key=lambda g: g["title"].lower()))}'
           f'</section>' if nocross else "")
        + f'<section><h2>Crossplay that has ended</h2><p>These games used to have crossplay, but it was switched off '
        f'or the servers closed.</p>{list_table(sorted(disc, key=lambda g: g["title"].lower()))}</section>',
        crumbs=[("Home", "/"), ("Games", "/games/")])

    # Updates
    log = list(reversed(hist.get("log", [])))
    slug_by_title = {g["title"]: g["slug"] for g in games}
    if log:
        items = "".join(f'<li><time>{nice_date(x["date"])}</time> '
                        + (f'<a href="{url("/games/" + slug_by_title[x["title"]] + "/")}">{e(x["title"])}</a>'
                           if x["title"] in slug_by_title else e(x["title"]))
                        + f': {e(x["what"])}</li>' for x in log[:200])
        upd = f'<ul class="log">{items}</ul>'
    else:
        upd = (f'<p>No changes yet. We started tracking on {nice_date(min(h["first_seen"] for h in hist["games"].values()))}; '
               f'every addition or change to a game\'s crossplay details will be listed here.</p>')
    pages["/updates/"] = page("/updates/", "Crossplay Updates: Recent Changes",
                              "New crossplay games and changes to existing ones, checked every day.",
                              f'<section class="hub-head"><h1>Recent crossplay changes</h1><p class="lede">We re-check '
                              f'every game daily. Last check: {nice_date(fetched)}.</p></section>{signup_box("updates")}<section>{upd}</section>',
                              crumbs=[("Home", "/"), ("Updates", "/updates/")])

    # RSS feed of the updates log
    feed_items = "".join(
        f"<item><title>{e(x['title'])}: {e(x['what'])}</title>"
        f"<link>{abs_url('/games/' + slug_by_title[x['title']] + '/') if x['title'] in slug_by_title else abs_url('/updates/')}</link>"
        f"<guid isPermaLink=\"false\">{e(x['date'] + ':' + x['title'] + ':' + x['what'])}</guid>"
        f"<pubDate>{datetime.datetime.combine(datetime.date.fromisoformat(x['date']), datetime.time(9)).strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate></item>"
        for x in log[:50])
    if config.NEWSLETTER_API:
        pages["/newsletter/"] = newsletter_page()
    NEWSLETTER_JSON = newsletter_json(log, slug_by_title)
    feed = (f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>{e(config.SITE_NAME)}: crossplay updates</title>'
            f'<link>{abs_url("/updates/")}</link><description>New crossplay games and changes to existing ones.</description>'
            f'<language>en</language>{feed_items}</channel></rss>\n')

    # Static pages
    pages["/about/"] = page("/about/", "About Crossplay Guide and How We Check", "Who runs Crossplay Guide, where our crossplay data comes from and how often we check it.",
                            ABOUT.format(n=len(current), contact=correction_link(), fetched=nice_date(fetched),
                                         photo=url("/static/mike-johnston.jpg")),
                            [{"@context": "https://schema.org", "@type": "AboutPage", "url": abs_url("/about/"),
                              "mainEntity": {"@type": "Person", "name": config.AUTHOR,
                                             "image": abs_url("/static/mike-johnston.jpg"),
                                             "url": abs_url("/about/") + "#who"}}],
                            crumbs=[("Home", "/"), ("About", "/about/")])
    pages["/guides/crossplay-not-working/"] = page(
        "/guides/crossplay-not-working/", "Crossplay Not Working? 9 Settings to Check on PS5, Xbox, Switch and PC",
        "Crossplay on but you still can't find your friend? Check these console, account and network settings on PlayStation, Xbox, Switch and PC.",
        FIXGUIDE.format(contact=correction_link()),
        crumbs=[("Home", "/"), ("Crossplay not working", "/guides/crossplay-not-working/")])
    if config.CONTACT_EMAIL:
        user, domain = config.CONTACT_EMAIL.split(chr(64))
        codes = ",".join(str(ord(c)) for c in config.CONTACT_EMAIL[::-1])
        pages["/contact/"] = page("/contact/", "Contact Crossplay Guide",
            "Report a mistake or ask a question about a game's crossplay.",
            f'''<section class="hub-head"><h1>Contact us</h1>
<p class="lede">Spotted a mistake, or know about a crossplay change we've missed? Send it over and we'll check it.</p></section>
<section class="prose">
<p>Email: <a data-mail="{codes}" href="#">{e(user)} (at) {e(domain.replace(".", " (dot) "))}</a></p>
<p>If it's about a specific game, include the game's name and, if you can, a link to where you saw the change
(patch notes, a support page or an official post). We read everything, and we credit nothing to you publicly
unless you ask.</p>
</section>''', noindex=True, crumbs=[("Home", "/"), ("Contact", "/contact/")])
        pages["/for-developers/"] = page(
            "/for-developers/", "For Developers and Publishers: Add Your Game or Partner With Us",
            "Developers and publishers can send crossplay details for their games, or get in touch about sponsorships "
            "and partnerships with Crossplay Guide.",
            FORDEVS.format(codes=codes, user=e(user), domain=e(domain.replace(".", " (dot) ")),
                           n=len([g for g in games if g.get("audited")]), about=url("/about/")),
            crumbs=[("Home", "/"), ("For developers", "/for-developers/")])
    pages["/privacy/"] = page("/privacy/", "Privacy Policy", "How this site handles your data.",
                              PRIVACY.format(site=e(config.SITE_NAME), contact=correction_link(), date=nice_date(TODAY),
                                             community=PRIVACY_COMMUNITY if config.API_URL else "",
                                             newsletter=PRIVACY_NEWSLETTER if config.NEWSLETTER_API else ""),
                              crumbs=[("Home", "/"), ("Privacy", "/privacy/")])
    pages["/404.html"] = page("/404.html", "Page not found", "That page doesn't exist.",
                              '<section class="hub-head"><h1>Game over (404)</h1><p class="lede">That page doesn\'t '
                              'exist. Try the search box above, or <a href="' + url("/games/") + '">browse every game</a>.</p></section>')

    # Home
    popular = sorted([g for g in current if g["cover"] and cross_groups(g)], key=lambda g: -g["popularity"])[:12]
    full = [g for g in current if {"pc", "ps5", "xseries", "switch"} <= {k for gr in g["groups"] for k in gr["platforms"]}
            and any({"pc", "ps5", "xseries", "switch"} <= set(gr["platforms"]) for gr in g["groups"])]
    full.sort(key=lambda g: -g["popularity"])
    recent = [x for x in log if x["title"] in slug_by_title][:6]
    opts = "".join(f'<option value="{f}">{e(FAMILIES[f][0])}</option>' for f in FAMILIES)
    pairs_json = e(json.dumps({s: True for s, *_ in pair_links}))
    tg = []
    for g in sorted(current, key=lambda g: -g["popularity"]):
        if g.get("verdict") or g["discontinued"]:
            continue
        groups = [[k for k in gr["platforms"] if k in CURRENT] for gr in g["groups"]]
        groups = [x for x in groups if x]
        if not groups:
            continue
        tg.append({"t": g["title"], "s": g["slug"], "c": 1 if g.get("audited") else 0, "f": 1 if g.get("f2p") else 0, "h": g["hubs"], "g": groups,
                   "q": sorted({k for gr in g["groups"] for k in gr["partial"]})})
    together_json = json.dumps({"base": url("/games/"), "games": tg}, separators=(",", ":"))
    pages["/who-can-i-play-with/"] = page(
        "/who-can-i-play-with/", "Who Can I Play With? Crossplay Games for Your Whole Group",
        "Pick each friend's platform (PS5, Xbox, Switch, PC or mobile) and see every game that puts all of you in the same lobby.",
        f'''<section class="hub-head"><h1>Who can I play with?</h1><p class="lede">Got friends on different consoles? Add
everyone's platform and we'll search {len(tg)} crossplay games for the ones that let all of you play together.</p></section>
{together_tool(None)}
<section class="prose"><h2>How the matching works</h2><p>A game shows up only if one crossplay group on its page includes every
platform you picked, so everyone can be in the same match. Games marked <strong>Checked</strong> were researched against official
sources; the others come from the community-maintained Wikipedia list. "With limits" means at least one platform only has partial
crossplay, such as some modes only. Always open the game's page for details like PC store and account requirements.</p></section>''',
        crumbs=[("Home", "/"), ("Who can I play with?", "/who-can-i-play-with/")])
    up = load_json("upcoming.json", {}).get("items", [])
    up.sort(key=lambda x: (x.get("sort") or x.get("date") or "9999", x["title"]))
    by_title = {g["title"]: g for g in games}
    KIND = {"adds": ("Crossplay coming", "yes"), "ends": ("Crossplay ending", "no"), "launch": ("New version", "partial")}
    rows = []
    for x in up:
        g = by_title.get(x["title"])
        label, cls = KIND.get(x.get("kind"), ("Change", "partial"))
        when = x.get("when") or nice_date(x["date"])
        passed = x.get("date") and x["date"] <= TODAY.isoformat()
        name = (f'<a href="{url("/games/" + g["slug"] + "/")}">{e(x["title"])}</a>' if g else e(x["title"]))
        rows.append(f'<li class="up"><div class="up-when"><time>{e(when)}</time>'
                    f'{"<span class=small> (due now, checking)</span>" if passed else ""}</div>'
                    f'<div class="up-body"><h3>{name} <span class="tag v-{cls}">{label}</span></h3><p>{e(x["what"])}</p></div></li>')
    pages["/coming-soon/"] = page(
        "/coming-soon/", "Crossplay Coming Soon: Upcoming Crossplay Updates and Launches",
        "Games getting crossplay soon, new versions joining crossplay, and crossplay that's ending, with dates where they're announced.",
        f'''<section class="hub-head"><h1>Crossplay coming soon</h1><p class="lede">Announced crossplay changes we're tracking:
games adding it, new versions joining it, and crossplay that's ending. We re-check each one when its date arrives and update
the game's page.</p></section>
<section><ul class="upcoming">{"".join(rows)}</ul>
<p class="small">Know about a change we've missed? <a href="{correction_link()}">Tell us</a>. Past changes are on the
<a href="{url('/updates/')}">recent changes</a> page.</p></section>''',
        crumbs=[("Home", "/"), ("Coming soon", "/coming-soon/")])
    checked_cross = [g for g in current if g.get("audited") and not g.get("verdict") and cross_groups(g)]
    def plays(g, a, b): return together(g, a, b) == "yes"
    BEST = [
        ("crossplay-games-ps5-pc", "Best Crossplay Games for PS5 and PC", "The best crossplay games for PS5 and PC",
         "Games where PlayStation 5 and PC players share the same matches, so you can play with friends on either.",
         [g for g in checked_cross if plays(g, "ps5", "pc")]),
        ("free-crossplay-games", "Best Free Crossplay Games (PC, PS5, Xbox, Switch)", "The best free crossplay games",
         "Free-to-play games with crossplay, so nobody in your group has to buy anything to join in. Online play in free "
         "games doesn't need PlayStation Plus or Game Pass.", [g for g in checked_cross if g.get("f2p")]),
        ("crossplay-co-op-games", "Best Crossplay Co-op Games", "The best crossplay co-op games",
         "Co-op games where friends on different platforms can team up instead of playing against each other.",
         [g for g in checked_cross if "co-op" in g["hubs"]]),
        ("crossplay-games-switch", "Best Crossplay Games for Nintendo Switch and Switch 2", "The best crossplay games on Switch",
         "Games where Switch or Switch 2 players can play with friends on PC, PlayStation or Xbox.",
         [g for g in checked_cross if any(("switch" in gr["platforms"] or "switch2" in gr["platforms"]) and len(gr["platforms"]) > 1 for gr in g["groups"])]),
    ]
    best_links = []
    for slug, title, h1, intro, best_games in BEST:
        if len(best_games) >= 5:
            pages[f"/best/{slug}/"] = best_page(f"/best/{slug}/", title, h1, intro, best_games,
                                                [("Home", "/"), (h1, f"/best/{slug}/")])
            best_links.append(f'<a class="pill" href="{url("/best/" + slug + "/")}">{e(h1[4:].capitalize())}</a>')
    pages["/"] = page("/", f"{config.SITE_NAME}: Is It Cross-Platform? Crossplay Checker for {len(current)} Games",
                      f"Check if a game has crossplay between PS5, Xbox, Switch, PC and mobile. "
                      f"{len(current)} games, checked daily, with sources.",
                      f"""
<section class="hero">
  <h1>Can you play together?</h1>
  <p class="lede">Check crossplay for {len(current)} games across PlayStation, Xbox, Switch, PC and mobile, with the
  sources, checked every day.</p>
  <form class="search big" role="search" onsubmit="return false">
    <input type="search" placeholder="Type a game, e.g. Fortnite" aria-label="Search games" autocomplete="off" data-search autofocus>
    <div class="results" data-results hidden></div>
  </form>
  <div class="pairpick" data-pairs='{pairs_json}' data-base="{url('/crossplay/')}">
    <span>Or show games for</span>
    <select data-fa aria-label="First platform">{opts}</select>
    <span>+</span>
    <select data-fb aria-label="Second platform">{opts.replace('value="playstation"', 'value="playstation" selected')}</select>
    <a class="btn" data-go href="{url('/crossplay/pc-and-playstation/')}">Show games</a>
  </div>
</section>
{together_tool()}
<section><h2>Popular crossplay games</h2>{grid(popular)}</section>
<section><h2>Works on PC, PlayStation, Xbox <em>and</em> Switch</h2>
<p>The full house: these games put every major platform in the same lobby.</p>{grid(full[:8])}
<p><a href="{url('/crossplay/playstation-and-switch/')}">More PlayStation + Switch games →</a></p></section>
<section><h2>Browse</h2>{"<nav class=pills>" + "".join(best_links) + "</nav>" if best_links else ""}<div class="plats">{pc}</div><nav class="pills" style="margin-top:1rem">{gl}</nav></section>
{"<section><h2>Recently changed</h2><ul class='log'>" + "".join(f'<li><time>{nice_date(x["date"])}</time> <a href="{url("/games/" + slug_by_title[x["title"]] + "/")}">{e(x["title"])}</a>: {e(x["what"])}</li>' for x in recent) + "</ul></section>" if recent else ""}
{signup_box("home")}
<section class="how"><h2>How this works</h2><p>We research the most-played games from publishers' own announcements,
and every night we re-read the community-maintained crossplay list, match each game to its official details and
rebuild these pages. Each game page links the announcements and
patch notes behind it. <a href="{url('/about/')}">More on how we check →</a></p></section>""",
                      [{"@context": "https://schema.org", "@type": "WebSite", "name": config.SITE_NAME,
                        "url": abs_url("/")}])

    # Write
    if OUT.exists():
        shutil.rmtree(OUT)
    for path, content in pages.items():
        f = OUT / (path.lstrip("/") if path.endswith(".html") else path.lstrip("/") + "index.html")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)
    shutil.copytree(HERE / "static", OUT / "static")
    index = [{"t": g["title"], "s": g["slug"], "d": g["discontinued"],
              "p": [PLATFORMS[k][1] for k in order({k for gr in g["groups"] for k in gr["platforms"]}) if k not in CLOUD][:6]}
             for g in sorted(games, key=lambda g: -g["popularity"])]
    (OUT / "static" / "together.json").write_text(together_json)
    (OUT / "static" / "search.json").write_text(json.dumps({"base": url("/games/"), "games": index}, separators=(",", ":")))
    urls = [p for p in pages if not p.endswith(".html") and p not in NOINDEX]
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                     + "".join(f"<url><loc>{abs_url(p)}</loc></url>\n" for p in sorted(urls)) + "</urlset>\n")
    robots = "User-agent: *\n" + ("Allow: /\n" if config.INDEXABLE else "Disallow: /\n") + f"Sitemap: {abs_url('/sitemap.xml')}\n"
    (OUT / "robots.txt").write_text(robots)
    (OUT / "newsletter.json").write_text(NEWSLETTER_JSON)
    if config.INDEXNOW_KEY:
        (OUT / f"{config.INDEXNOW_KEY}.txt").write_text(config.INDEXNOW_KEY)
    (OUT / "feed.xml").write_text(feed)
    (OUT / "social.xml").write_text(social_feed(games))
    (OUT / "og").mkdir(exist_ok=True)
    (OUT / "og" / "cards.json").write_text(json.dumps([og_card(g) for g in games], ensure_ascii=False))
    (OUT / ".nojekyll").write_text("")
    if config.DOMAIN:
        (OUT / "CNAME").write_text(config.DOMAIN + "\n")
    print(f"Built {len(pages)} pages ({len(games)} games, {len(plat_cards)} platform hubs, "
          f"{len(pair_links)} pair hubs, {len(genre_links)} genre hubs) → {OUT}")


# ---------------------------------------------------------------- social feed

SOCIAL_PER_DAY = 2
SOCIAL_MAX = 245  # the Metricool autolist cuts posts at 250 characters


def clip(text, n=SOCIAL_MAX):
    """Shorten to n characters, ending on a full sentence where possible."""
    if len(text) <= n:
        return text
    cut = text[:n].rfind(". ")
    return text[:cut + 1] if cut > n // 2 else text[:n - 1].rstrip() + "…"


def social_feed(games):
    """RSS for the social accounts (/social.xml, read by a Metricool autolist).

    Announces checked games when they first appear and changes that come with a `news` line in
    data/manual.json ({"date": ..., "text": ...}); silent data tweaks aren't posted. data/social.json
    remembers what was announced and holds a queue, so at most SOCIAL_PER_DAY items go out per day."""
    st = load_json("social.json", None)
    checked = {g["title"]: g for g in games if g.get("audited") and not g["discontinued"]}
    if st is None:  # first run: everything already on the site counts as announced
        st = {"seen": {t: (g.get("news") or {}).get("date", "") for t, g in checked.items()}, "queue": [], "out": []}
    for t, g in sorted(checked.items()):
        news = g.get("news") or {}
        link = abs_url("/games/" + g["slug"] + "/")
        if t not in st["seen"]:
            kind, word, summary = verdict(g)
            text = {"no": "❌ ", "yes": "✅ "}.get(kind, "") + summary
            st["queue"].append({"id": f"{TODAY}:{t}:added", "text": clip(f"🆕 Just checked: {t}\n\n{text}"), "link": link})
        elif news.get("date") and news["date"] != st["seen"][t]:
            st["queue"].append({"id": f"{news['date']}:{t}:news", "text": clip(f"🔄 Crossplay update: {t}\n\n{news['text']}"), "link": link})
        st["seen"][t] = news.get("date", "") if news else st["seen"].get(t, "")
    today = TODAY.isoformat()
    room = SOCIAL_PER_DAY - sum(1 for x in st["out"] if x["date"] == today)
    while room > 0 and st["queue"]:
        x = st["queue"].pop(0)
        x["date"] = today
        st["out"].append(x)
        room -= 1
    st["out"] = st["out"][-40:]
    save_json("social.json", st)
    items = "".join(
        f"<item><title>{e(x['text'])}</title><link>{e(x['link'])}</link><description>{e(x['text'])}</description>"
        f"<guid isPermaLink=\"false\">{e(x['id'])}</guid>"
        f"<pubDate>{datetime.datetime.combine(datetime.date.fromisoformat(x['date']), datetime.time(9)).strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate></item>"
        for x in reversed(st["out"]))
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>{e(config.SITE_NAME)}: social</title>'
            f'<link>{abs_url("/")}</link><description>New and updated crossplay answers.</description>'
            f'<language>en</language>{items}</channel></rss>\n')


def og_card(g):
    """What site/og.py needs to draw a game's 1200x630 share image."""
    kind, word, _ = verdict(g)
    cg = cross_groups(g)
    main = cg[0]["platforms"] if cg else order({k for gr in g["groups"] for k in gr["platforms"]})
    return {"slug": g["slug"], "title": g["title"], "kind": kind, "word": word,
            "platforms": [PLATFORMS[k][1] for k in main if k not in CLOUD][:8],
            "groups": len([gr for gr in g["groups"] if len(gr["platforms"]) >= 2])}


FIXGUIDE = """
<section class="hub-head"><h1>Crossplay not working? Check these settings</h1>
<p class="lede">The game says it has crossplay, but you and your friend still can't find each other. Work through
this list on both sides: most problems come from a console setting, a missing account link, or one player being on
an older version.</p></section>
<section class="prose">
<h2>1. Turn crossplay on in the game, on both sides</h2>
<p>Most games have their own crossplay setting, usually in the game's Settings or Options menu under Gameplay,
Online or Network. Both players need it on. In some games, players who turn it off only match with others who also
turned it off, and on consoles it's sometimes off by default. Some games only apply the change after a restart.
Each game page here has a "How to turn crossplay on or off" section when we know the exact menu.</p>

<h2>2. Check the Xbox cross-network setting</h2>
<p>On Xbox, a system setting can block crossplay in every game, whatever the game's own setting says. Press the
Xbox button, then go to <strong>Profile &amp; system &rarr; Settings &rarr; Account &rarr; Privacy &amp; online
safety &rarr; Xbox privacy &rarr; View details &amp; customize &rarr; Communication &amp; multiplayer</strong>, and
set <strong>You can join cross-network play</strong> to Allow. <strong>You can join multiplayer games</strong> has
to be allowed too. Voice and text chat with other platforms is a separate setting on the same screen.</p>
<p>For a child account, only the family organizer can change these, from the Xbox Family Settings app or
account.microsoft.com, and players report the change can take a while to reach the console. The Xbox app on PC uses
the same privacy settings for your Microsoft account.</p>

<h2>3. Check parental controls on PlayStation and Switch</h2>
<p>On PlayStation, crossplay is set inside each game, not in the system settings. On a child account, though, the
family manager can restrict communication with other players and content made by other players, which can block
chat or invites. Check it under <strong>Settings &rarr; Family and Parental Controls</strong>, or in Family
Management on the PlayStation website.</p>
<p>On Nintendo Switch, the Parental Controls app can restrict communication with other players for a child. If a
child's account can't invite or chat with friends on other platforms, check it there.</p>

<h2>4. Make sure everyone has the online subscription</h2>
<p>Online play in paid games needs PlayStation Plus on PlayStation, a Game Pass plan with online play on Xbox, and
Nintendo Switch Online on Switch. Free-to-play games such as Fortnite, Warzone and Apex Legends don't need PlayStation
Plus or Game Pass. A lapsed subscription on one side is a common reason a party invite silently fails.</p>

<h2>5. Link the publisher account</h2>
<p>A lot of crossplay runs through the publisher's own account rather than PlayStation Network, Xbox or Steam: for
example an EA account, an Epic Games account, Ubisoft Connect, an Activision or Battle.net account, a Bungie account or
an Embark ID. If one of you hasn't linked it (or linked a different one), you won't see each other. Check the
game's account or social menu on both sides.</p>

<h2>6. Add each other through the game, not the console</h2>
<p>Your PlayStation, Xbox, Switch or Steam friends list doesn't carry across platforms. Cross-platform friends are
added inside the game, usually by the publisher account name or a friend code. Party invites sent through the
console's own menus generally only reach friends on the same platform.</p>

<h2>7. Update everyone to the same version</h2>
<p>Patches sometimes land on PC a day or more before consoles (or the other way round). Players on different
versions can't join each other. Check for an update on every device and restart the game.</p>

<h2>8. Check you're on versions that actually play together</h2>
<p>Crossplay is often only between some platforms, modes or store versions. Some PC games only cross with Xbox in
the Microsoft Store version, not on Steam; some games keep PS4 and PS5, or ranked and casual, apart; some only mix
consoles. Look up the game here: the "Who can play with whom" section shows exactly which versions share players.</p>

<h2>9. Check your network</h2>
<p>A strict NAT type can stop you joining a friend's party even when matchmaking works. On PS5, run
<strong>Settings &rarr; Network &rarr; Connection Status &rarr; Test Internet Connection</strong>; on Xbox,
<strong>Settings &rarr; General &rarr; Network settings</strong> shows your NAT type. If it's strict, your router's
UPnP setting or your internet provider is the usual place to fix it.</p>

<h2>Still stuck?</h2>
<p>Some games have known crossplay bugs after a patch. The game's official support site, status page or Discord is
the fastest place to check. If our page for the game is wrong or out of date, <a href="{contact}">let us know</a>.</p>
<p class="small">Sources: <a href="https://www.playstation.com/en-gb/support/account/safety-parents-guide/">PlayStation
safety guide for parents</a>; <a href="https://support.rockstargames.com/articles/6oMA7pOtwFAzgFCmRK40BR/unable-to-enter-grand-theft-auto-online-on-the-xbox-app-on-pc">Rockstar
Support on Xbox app privacy settings</a>; <a href="https://www.videogameschronicle.com/news/xbox-live-gold-is-no-longer-required-to-play-free-to-play-multiplayer-games">VGC
on Xbox free-to-play online play</a>. Menu names can change with system updates.</p>
</section>
"""

FORDEVS = """
<section class="hub-head"><h1>For developers and publishers</h1>
<p class="lede">Make a crossplay game? Tell us how it works and we'll get it right on Crossplay Guide. Thinking about
reaching players who are looking for games to play with friends? Let's talk.</p></section>
<section class="prose">
<h2 id="add">Add or update your game</h2>
<p>Every game page here says which platforms play together, any limits, and whether progress carries over, with a
link to the source for each claim. If your game is missing, out of date or about to change, send us:</p>
<ul>
<li>The game's name and every platform it's on (including PC stores such as Steam, Epic, the Xbox app or your own
launcher).</li>
<li>Which platforms play together, and whether that differs by mode (co-op, PvP, ranked, custom lobbies).</li>
<li>Whether crossplay can be turned off, and where the setting is.</li>
<li>Whether progress, purchases or currency carry over between platforms, and what's needed (for example an account
link).</li>
<li>A public link that confirms it: patch notes, a support article, a store page or an official post.</li>
</ul>
<p>Listing and updates are free, and always will be. We only publish what a public source confirms, so if your
crossplay news is under embargo, tell us the date and we'll publish once it's out.</p>
<p><a class="btn" data-mail="{codes}" data-subject="Game submission: " href="#">Email us about your game</a></p>
<h2 id="partner">Sponsorships and partnerships</h2>
<p>Crossplay Guide covers {n} researched games, and people come here when they're deciding what to play with friends
on other platforms. We're open to:</p>
<ul>
<li>Sponsoring our weekly crossplay email.</li>
<li>Launch or update features for a crossplay game.</li>
<li>Other partnerships that help players find games they can play together.</li>
</ul>
<p>Paid placements are always labelled as sponsored. They never change what a game page says: crossplay facts come
from public sources and nobody can pay for a verdict (more on <a href="{about}">how we check</a>).</p>
<p><a class="btn" data-mail="{codes}" data-subject="Partnership: " href="#">Email us about a partnership</a></p>
<p class="small">Email: <span>{user} (at) {domain}</span></p>
</section>
"""

ABOUT = """
<section class="hub-head"><h1>About Crossplay Guide</h1>
<p class="lede">Short version: we track {n} games, re-check them every day, and show our sources on every page.</p></section>
<section class="prose">
<div class="author" id="who">
<img src="{photo}" width="160" height="160" alt="Mike Johnston">
<div><h2>Who runs this site</h2>
<p>Crossplay Guide is run by Mike Johnston. My day job is running the tech side of
<a href="https://www.thekitchenmagpie.com/">The Kitchen Magpie</a>, a food blog. I built this site because finding out
whether you can play with a friend on a different console usually means digging through forum threads and old patch
notes.</p>
<p>The site is independent. It isn't affiliated with any platform holder or publisher, and nobody pays for a
verdict.</p></div>
</div>
<h2>How a game gets researched</h2>
<p>For each game I go to the publisher's own announcements, patch notes and support pages, and write up which platforms
play together, any limits (for example only some modes, or an opt-in setting), and whether progress carries over. I use
AI tools to help find and read those sources, and every claim on a researched page links the source it came from so you
can check it yourself. Pages I've researched say "Researched by Mike Johnston" next to the date they were last
checked.</p>
<h2>Where the facts come from</h2>
<p>Games that haven't been researched yet come from Wikipedia's <a href="https://en.wikipedia.org/wiki/List_of_video_games_that_support_cross-platform_play">List
of video games that support cross-platform play</a>, which volunteers keep up to date and which cites the publisher
announcements, patch notes and support pages behind each entry. We link those citations on every game page so you
can check them yourself. The list is licensed CC BY-SA 4.0.</p>
<p>Release dates, developers, genres and multiplayer details (player counts, co-op, split screen) come from
<a href="https://www.igdb.com/">IGDB</a>.</p>
<h2>What "plays together" means</h2>
<p>A crossplay group is a set of platforms whose players share the same matchmaking or servers. Some games have more
than one group: for example, PlayStation and Xbox might play together while the Switch version is separate. Where a
game is on a platform that isn't in any group, we say so, because that usually means those players only meet each
other.</p>
<p>On PC, crossplay often depends on the store. We list which PC stores (Steam, Epic, the Xbox app, and so on) are part
of each group.</p>
<h2>How often we check</h2>
<p>Every night a script re-reads the sources, records anything that changed, and rebuilds the site. Changes show up on
the <a href="../updates/">recent changes</a> page. Last check: {fetched}.</p>
<h2>Corrections</h2>
<p>Crossplay changes with patches and new ports, and sources lag behind. If you spot something wrong,
<a href="{contact}">tell us</a> with a link to the official announcement and we'll fix it.</p>
</section>"""

PRIVACY_NEWSLETTER = """<h2>Weekly email</h2>
<p>If you subscribe, we store your email address with <a href="https://resend.com/legal/privacy-policy">Resend</a>,
the service that sends the email, and use it only to send the weekly email. We ask you to confirm by clicking a link
first. Every email has a one-click unsubscribe link, and we never sell or share the list.</p>"""

PRIVACY = """
<section class="hub-head"><h1>Privacy policy</h1><p class="lede">Last updated {date}.</p></section>
<section class="prose">
<p>{site} is a free, ad-supported website. We don't ask you to sign up, and we only have your email address if
you contact us or subscribe to the weekly email.</p>
{newsletter}
<h2>Advertising and cookies</h2>
<p>We may show ads from third-party advertising partners. They may use cookies and similar technologies to show ads
based on your visits to this and other websites, and to measure how ads perform. Where the law requires it, we ask for
your consent first, and you can change your choice at any time.</p>
<h2>Analytics</h2>
<p>We use Google Analytics, Clicky and Cloudflare Web Analytics to count visits and see which pages are useful. Google Analytics and Clicky set cookies; all three receive your IP address, browser details and the pages you view, and we only look at aggregated reports. Cloudflare Web Analytics sets no cookies. See <a href="https://policies.google.com/privacy">Google's</a>, <a href="https://clicky.com/terms/privacy">Clicky's</a> and <a href="https://www.cloudflare.com/privacypolicy/">Cloudflare's</a> privacy policies.</p>
<h2>Third-party content</h2>
<p>Game cover images and screenshots load from IGDB, trailer preview images load from YouTube, and fonts load from
Google Fonts. Those services receive your IP address when your browser fetches the files. Trailers only load the
YouTube player (which may set YouTube cookies) after you press play.</p>
{community}
<h2>Contact</h2>
<p>Questions about privacy? <a href="{contact}">Get in touch</a>.</p>
</section>"""

PRIVACY_COMMUNITY = """<h2>Player reports and tips</h2>
<p>If you tell us whether crossplay worked for you, or send a tip, we store what you sent, the time, and a one-way
hashed version of your IP address (so one person can't vote many times). We never store the IP address itself.
Tips are read by a person before they're published, and we publish only the name you typed (if any) and the tip.
Spam protection may use Cloudflare Turnstile.</p>"""


if __name__ == "__main__":
    build()
