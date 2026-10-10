"""Build the static site from data/*.json into _site/.

    python3 site/build.py

Pages: home, one page per game, platform hubs, platform-pair hubs, genre hubs, updates,
about/methodology, privacy, 404, sitemap and a small search index.
"""
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
from common import load_json, merged_games, norm, slugify, trailer_candidates  # noqa: E402

OUT = HERE.parent / "_site"
GA_TAG = (f'<script async src="https://www.googletagmanager.com/gtag/js?id={config.GA_ID}"></script>\n'
          f"<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}"
          f"gtag('js',new Date());gtag('config','{config.GA_ID}');</script>\n") if config.GA_ID else ""
CLICKY_TAG = (f'<script async data-id="{config.CLICKY_ID}" src="https://static.getclicky.com/js"></script>\n'
              if config.CLICKY_ID else "")
# Cache-busting: a short hash of each file's contents, so browsers refetch the moment it changes.
ASSET_V = {n: __import__("hashlib").sha1((HERE / "static" / n).read_bytes()).hexdigest()[:10]
           for n in ("style.css", "site.js")}
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
    for w in merged:
        ig = igdb.get(w["igdb_key"]) or {}
        key = w["title"] + (" (discontinued)" if w["discontinued"] else "")
        slug = slugify(w["title"])
        if slug in slugs:
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
            "crossprog": w.get("crossprog"), "audited": w.get("audited"),
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


def pc_note(g):
    stores = sorted({s for gr in g["groups"] if "pc" in gr["platforms"] for s in gr["pc_stores"]})
    if not stores:
        return ""
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


def page(path, title, desc, body, schema=None, crumbs=None, noindex=False):
    canonical = abs_url(path)
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
<link rel="icon" href="{url('/static/favicon.svg')}" type="image/svg+xml">
<link rel="apple-touch-icon" href="{url('/static/apple-touch-icon.png')}">
<link rel="alternate" type="application/rss+xml" title="{e(config.SITE_NAME)} updates" href="{url('/feed.xml')}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{url('/static/style.css')}?v={ASSET_V['style.css']}">
{config.AD_SCRIPT}
{GA_TAG}{CLICKY_TAG}{ld}</head>
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
      <a href="{url('/updates/')}">Recent changes</a>
      <a href="{url('/feed.xml')}">RSS feed</a>
      <a href="{url('/privacy/')}">Privacy</a>
      <a href="{correction_link()}">Report a mistake</a>
    </nav>
  </div>
</footer>
<script src="{url('/static/site.js')}?v={ASSET_V['site.js']}" defer></script>
</body>
</html>
"""


def correction_link(title=None):
    subject = f"Correction: {title}" if title else "Correction"
    if config.CONTACT_EMAIL:
        return f"mailto:{config.CONTACT_EMAIL}?subject={e(subject)}"
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
    if g["crossprog"]:
        w_, why = CROSSPROG[g["crossprog"]]
        xprog = f'<p class="xprog"><span class="tag x-{g["crossprog"]}">Cross-progression: {w_}</span> {e(why[0].upper() + why[1:])}</p>'
    parts.append(f"""
<section class="answer v-{kind}">
  <div class="answer-cover">{cover(g)}</div>
  <div class="answer-body">
    <p class="kicker">Is {e(t)} cross-platform?</p>
    <h1>{e(t)} crossplay</h1>
    <p class="verdict"><span class="badge v-{kind}">{e(word)}</span> {e(summary)}</p>
    {"".join(f'<p>{e(x)}</p>' for x in extra)}
    {xprog}
    <p class="checked">{byline}Last checked {nice_date(g["checked"])}
    {f' · Details last changed {nice_date(g["history"]["changed"])}' if g["history"].get("changed") and g["history"]["changed"] != g["history"].get("first_seen") else ''}</p>
  </div>
</section>""")

    # Groups
    rows = []
    for i, gr in enumerate(g["groups"], 1):
        label = (PLATFORMS[gr["platforms"][0]][1] + " only" if len(gr["platforms"]) == 1 and not gr["pc_stores"]
                 and len(g["groups"]) > 1 else f"Group {i}" if len(g["groups"]) > 1 else "Plays together")
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
    heading = "Who can play with whom" if len(g["groups"]) > 1 or g["outside"] else "Platforms that play together"
    parts.append(f'<section><h2>{heading}</h2><div class="pools">{"".join(rows)}</div></section>')

    # Checker + pair table
    items = []
    avail = [k for k in g["available"] if k in CURRENT or any(k in gr["platforms"] for gr in g["groups"])]
    avail = [k for k in avail if k not in CLOUD]
    pairs = []
    for i, a in enumerate(avail):
        for b in avail[i + 1:]:
            pairs.append((a, b, together(g, a, b)))
    if len(avail) >= 2 and not g["discontinued"]:
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
<section class="community" data-community='{e(cdata)}' hidden>
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
        parts.append('<section class="two"><div>' +
                     ('<h2>Multiplayer at a glance</h2><dl class="facts">' +
                      "".join(f"<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>" for a, b in mp) +
                      '</dl><p class="small">From IGDB\'s multiplayer data; modes can differ by platform.</p>'
                      if mp else "") +
                     '</div><div><h2>Game details</h2><dl class="facts">' +
                     "".join(f"<div><dt>{e(a)}</dt><dd>{b if isinstance(b, Raw) else e(b)}</dd></div>" for a, b in facts) +
                     "</dl></div></section>")

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
                noindex=not g.get("audited"))


def list_table(games, show=None):
    rows = []
    for g in games:
        kind, word, _ = verdict(g)
        plats = order({k for gr in cross_groups(g) or g["groups"] for k in gr["platforms"] if k not in CLOUD})
        rows.append(f'<tr><td class="t"><a href="{url("/games/" + g["slug"] + "/")}">{cover(g, "t_thumb", 45, 60, "thumb")}'
                    f'<span>{e(g["title"])}</span></a></td>'
                    f'<td><span class="tag v-{kind}">{e(word)}</span></td>'
                    f'<td class="chips">{"".join(chip(k) for k in plats)}</td>'
                    f'<td class="y">{g["year"] or ""}</td></tr>')
    return ('<div class="tablewrap"><table class="list"><thead><tr><th>Game</th><th>Crossplay</th>'
            '<th>Plays together</th><th>Year</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")


def hub_page(path, title, h1, intro, games, crumbs, extra=""):
    games = sorted(games, key=lambda g: -g["popularity"])
    body = (f'<section class="hub-head"><h1>{e(h1)}</h1><p class="lede">{intro}</p></section>'
            + (f'<section><h2>Most popular</h2>{grid(games[:8])}</section>' if len(games) > 8 else "")
            + f'<section><h2>All {len(games)} games</h2>{list_table(games)}</section>' + extra)
    schema = [{"@context": "https://schema.org", "@type": "ItemList", "name": h1, "numberOfItems": len(games),
               "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": g["title"],
                                    "url": abs_url("/games/" + g["slug"] + "/")} for i, g in enumerate(games[:50])]}]
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
                              f'every game daily. Last check: {nice_date(fetched)}.</p></section><section>{upd}</section>',
                              crumbs=[("Home", "/"), ("Updates", "/updates/")])

    # RSS feed of the updates log
    feed_items = "".join(
        f"<item><title>{e(x['title'])}: {e(x['what'])}</title>"
        f"<link>{abs_url('/games/' + slug_by_title[x['title']] + '/') if x['title'] in slug_by_title else abs_url('/updates/')}</link>"
        f"<guid isPermaLink=\"false\">{e(x['date'] + ':' + x['title'] + ':' + x['what'])}</guid>"
        f"<pubDate>{datetime.datetime.combine(datetime.date.fromisoformat(x['date']), datetime.time(9)).strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate></item>"
        for x in log[:50])
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
    pages["/privacy/"] = page("/privacy/", "Privacy Policy", "How this site handles your data.",
                              PRIVACY.format(site=e(config.SITE_NAME), contact=correction_link(), date=nice_date(TODAY),
                                             community=PRIVACY_COMMUNITY if config.API_URL else ""),
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
<section><h2>Popular crossplay games</h2>{grid(popular)}</section>
<section><h2>Works on PC, PlayStation, Xbox <em>and</em> Switch</h2>
<p>The full house: these games put every major platform in the same lobby.</p>{grid(full[:8])}
<p><a href="{url('/crossplay/playstation-and-switch/')}">More PlayStation + Switch games →</a></p></section>
<section><h2>Browse</h2><div class="plats">{pc}</div><nav class="pills" style="margin-top:1rem">{gl}</nav></section>
{"<section><h2>Recently changed</h2><ul class='log'>" + "".join(f'<li><time>{nice_date(x["date"])}</time> <a href="{url("/games/" + slug_by_title[x["title"]] + "/")}">{e(x["title"])}</a>: {e(x["what"])}</li>' for x in recent) + "</ul></section>" if recent else ""}
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
    (OUT / "static" / "search.json").write_text(json.dumps({"base": url("/games/"), "games": index}, separators=(",", ":")))
    urls = [p for p in pages if not p.endswith(".html") and p not in NOINDEX]
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                     + "".join(f"<url><loc>{abs_url(p)}</loc></url>\n" for p in sorted(urls)) + "</urlset>\n")
    robots = "User-agent: *\n" + ("Allow: /\n" if config.INDEXABLE else "Disallow: /\n") + f"Sitemap: {abs_url('/sitemap.xml')}\n"
    (OUT / "robots.txt").write_text(robots)
    (OUT / "feed.xml").write_text(feed)
    (OUT / ".nojekyll").write_text("")
    if config.DOMAIN:
        (OUT / "CNAME").write_text(config.DOMAIN + "\n")
    print(f"Built {len(pages)} pages ({len(games)} games, {len(plat_cards)} platform hubs, "
          f"{len(pair_links)} pair hubs, {len(genre_links)} genre hubs) → {OUT}")


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

PRIVACY = """
<section class="hub-head"><h1>Privacy policy</h1><p class="lede">Last updated {date}.</p></section>
<section class="prose">
<p>{site} is a free, ad-supported website. We don't ask you to sign up and we don't collect your name or email
address unless you contact us.</p>
<h2>Advertising and cookies</h2>
<p>We may show ads from third-party advertising partners. They may use cookies and similar technologies to show ads
based on your visits to this and other websites, and to measure how ads perform. Where the law requires it, we ask for
your consent first, and you can change your choice at any time.</p>
<h2>Analytics</h2>
<p>We use Google Analytics and Clicky to count visits and see which pages are useful. They set cookies and receive your IP address, browser details and the pages you view; we only look at aggregated reports. See <a href="https://policies.google.com/privacy">Google's</a> and <a href="https://clicky.com/terms/privacy">Clicky's</a> privacy policies.</p>
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
