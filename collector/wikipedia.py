"""Parse Wikipedia's "List of video games that support cross-platform play" into data/wikipedia.json.

Each table row is one crossplay group: the platforms marked {{yes|...}} can play together.
A game can have several rows (several separate groups). Rows with an empty title continue
the previous game.

Wikipedia text is CC BY-SA; we store facts (which platforms play together) plus the page URL
for attribution on every game page.
"""
import datetime
import hashlib
import json
import re
import sys

from common import http, load_json, merged_games, norm, save_json

PAGE = "List_of_video_games_that_support_cross-platform_play"
API = ("https://en.wikipedia.org/w/api.php?action=parse&page=" + PAGE +
       "&prop=wikitext&section={section}&format=json&formatversion=2")

# Column order of the platform cells after the title cell, per table.
COLUMNS = ["Linux", "Mac", "PC (GOG)", "PC (Steam)", "PC (Xbox app)", "PC (other store)",
           "iOS", "Android", "PS4", "Xbox One", "Switch", "PS5", "Xbox Series X|S"]
OLD_COLUMNS = ["Xbox 360", "Xbox One", "Xbox Series X|S", "Dreamcast", "Linux", "Mac", "PC",
               "PS2", "PS3", "PS4", "PS5", "PSP", "PS Vita", "Switch"]


def fetch(section):
    return http("GET", API.format(section=section))["parse"]["wikitext"]


def clean_title(cell):
    cell = re.sub(r"^[^|\[']*\|", "", cell) if "rowspan" in cell else cell  # drop 'rowspan="2" |'
    cell = re.sub(r"\[https?://\S+ ([^\]]+)\]", r"\1", cell)  # external link titles
    links = re.findall(r"\[\[((?:[^\[\]]|\[[^\[\]]*\])+)\]\]", cell)  # link text can contain "[st]"
    if links:
        text = re.sub(r"\[\[((?:[^\[\]]|\[[^\[\]]*\])+)\]\]",
                      lambda m: m.group(1).split("|")[-1], cell)
        return re.sub(r"''|<[^>]+>", "", text).strip(), links[-1].split("|")[0].strip()
    return re.sub(r"''|<[^>]+>|\{\{[^}]*\}\}", "", cell).strip(), None


# Cell labels name the platform/store reliably even when a row has a missing cell and the
# columns shift, so the label wins over the column position.
LABELS = {
    "linux": "linux", "mac": "mac", "ios": "ios", "android": "android", "ps4": "ps4", "ps5": "ps5",
    "xbo": "xone", "xbsx/xbss": "xseries", "switch": "switch", "switch 2": "switch2", "ps3": "ps3",
    "ps2": "ps2", "vita": "vita", "psp": "psp", "xb360": "x360", "dreamcast": "dreamcast",
    "wii u": "wiiu", "3ds": "3ds", "oq": "quest", "wp": "winphone", "stadia": "stadia", "luna": "luna",
    "geforce now": "geforcenow", "xbox cloud gaming": "xcloud",
}
PC_STORES = {"steam": "Steam", "gog": "GOG", "xbox": "Xbox app", "epic": "Epic", "battle.net": "Battle.net",
             "ea": "EA app", "riot": "Riot", "gfwl": "Games for Windows Live", "windows pc": "", "other": "",
             "steam only": "Steam"}
COLUMN_KEYS = {"Linux": "linux", "Mac": "mac", "iOS": "ios", "Android": "android", "PS4": "ps4", "PS5": "ps5",
               "Xbox One": "xone", "Xbox Series X|S": "xseries", "Switch": "switch", "PS3": "ps3", "PS2": "ps2",
               "PS Vita": "vita", "PSP": "psp", "Xbox 360": "x360", "Dreamcast": "dreamcast"}


def add_cell(group, col, cell):
    """Record a {{yes|LABEL}} cell into group; return False if the cell isn't a yes marker."""
    m = re.search(r"\{\{\s*(yes|partial|maybe|included)\s*\|?([^}]*)\}\}", cell, re.I)
    if not m:
        return False
    partial = m.group(1).lower() in ("partial", "maybe")
    for label in [x.strip() for x in m.group(2).split(",")] or [""]:
        key = label.lower()
        if key in LABELS:
            plat, store = LABELS[key], None
        elif key in PC_STORES:
            plat, store = "pc", PC_STORES[key]
            if col in ("Mac", "Linux") and key == "steam only":
                plat = COLUMN_KEYS[col]  # "Steam only" note on a Mac/Linux cell
        elif col in COLUMN_KEYS:
            plat, store = COLUMN_KEYS[col], None
        else:
            plat, store = "pc", label or None
        group["platforms"][plat] = "partial" if partial else "yes"
        if store:
            group["pc_stores"].append(store)
    return True


def split_others(text):
    out = []
    for part in re.split(r",|/| and ", text):
        part = part.strip()
        if part:
            out.append(LABELS.get(part.lower(), part))
    return out


def split_cells(row):
    cells = []
    for line in row.split("\n"):
        line = line.rstrip()
        if not line.startswith("|") or line.startswith("|-") or line.startswith("|}") or line.startswith("|+"):
            continue
        # A line can hold several cells separated by "||".
        cells += [c.strip() for c in line[1:].split("||")]
    return cells


def ref_urls(cell):
    return sorted(set(u.rstrip(".,") for u in re.findall(r"https?://[^\s|}\]<]+", cell)))


def parse(wikitext, columns, discontinued=False):
    table = wikitext[wikitext.find("{|"):]
    rows = table.split("\n|-")[1:]
    games, last = [], None
    for row in rows:
        if row.lstrip().startswith("!"):
            continue  # header rows
        row = re.sub(r"\[\[[^\]]*\]\]", lambda m: m.group(0).replace("\n", " "), row)  # links broken over lines
        cells = split_cells(row)
        if len(cells) < 1 + len(columns):
            continue
        title, link = clean_title(cells[0])
        group = {"platforms": {}, "pc_stores": [], "others": [], "refs": ref_urls("\n".join(cells[1:]))}
        for i, cell in enumerate(cells[1:]):
            col = columns[i] if i < len(columns) else ""
            if add_cell(group, col, cell) or "<ref" in cell or "align=" in cell or not cell:
                continue
            text = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", cell)
            group["others"] += split_others(re.sub(r"<[^>]+>|\{\{[^}]*\}\}", "", text))
        known = set(LABELS.values())
        for o in group["others"]:
            if o in known:
                group["platforms"].setdefault(o, "yes")
            elif o in PC_STORES.values():
                group["platforms"].setdefault("pc", "yes")
                group["pc_stores"].append(o)
        group["others"] = [o for o in group["others"] if o not in known and re.search(r"[A-Za-z0-9]", o)
                           and o not in PC_STORES.values()]
        group["pc_stores"] = sorted(set(group["pc_stores"]))
        if not group["platforms"] and not group["others"]:
            continue
        if title:
            last = {"title": title, "wiki_link": link, "groups": [], "discontinued": discontinued}
            games.append(last)
        if last is None:
            continue
        last["groups"].append(group)
    return games


def track_changes(games, today):
    """Keep data/history.json: when each game was first seen and when its crossplay facts last changed."""
    hist = load_json("history.json", {"games": {}, "log": []})
    first_run = not hist["games"]
    seen = set()
    for g in games:
        key = g["title"] + (" (discontinued)" if g["discontinued"] else "")
        seen.add(key)
        facts = [{k: gr[k] for k in ("platforms", "pc_stores", "others")} for gr in g["groups"]]
        h = hashlib.sha1(json.dumps(facts, sort_keys=True).encode()).hexdigest()[:12]
        old = hist["games"].get(key)
        if old is None:
            hist["games"][key] = {"first_seen": today, "changed": today, "hash": h}
            if not first_run:
                hist["log"].append({"date": today, "title": g["title"], "what": "added"})
        elif old["hash"] != h:
            old.update(changed=today, hash=h)
            hist["log"].append({"date": today, "title": g["title"], "what": "crossplay details changed"})
    # A title that only changed name (title_overrides.json, a manual "replaces", or punctuation such as
    # "Overcooked 2" -> "Overcooked! 2") wasn't removed: carry its history over and log nothing.
    renames = load_json("title_overrides.json", {})
    for m in load_json("manual.json", {"games": []})["games"]:
        for r in m.get("replaces", []):
            renames[r] = m["title"]
    by_norm = {norm(k): k for k in seen}
    for key in [k for k in hist["games"] if k not in seen]:
        old = hist["games"].pop(key)
        new = renames.get(key) if renames.get(key) in seen else by_norm.get(norm(renames.get(key, key)))
        if new:
            hist["games"][new]["first_seen"] = min(old["first_seen"], hist["games"][new]["first_seen"])
            hist["log"] = [x for x in hist["log"] if not (x["date"] == today and x["title"] == new
                                                          and x["what"] == "added")]
            continue
        hist["log"].append({"date": today, "title": key, "what": "removed from the source list"})
    hist["log"] = hist["log"][-300:]
    save_json("history.json", hist)


def main():
    games = parse(fetch(1), COLUMNS) + parse(fetch(2), OLD_COLUMNS, discontinued=True)
    if len(games) < 200:
        raise SystemExit(f"Only {len(games)} games parsed; the page layout probably changed. Keeping old data.")
    today = datetime.date.today().isoformat()
    save_json("wikipedia.json", {"source": "https://en.wikipedia.org/wiki/" + PAGE, "fetched": today, "games": games})
    track_changes(merged_games()[1], today)
    print(f"Wikipedia: {sum(not g['discontinued'] for g in games)} current, "
          f"{sum(g['discontinued'] for g in games)} discontinued")


if __name__ == "__main__":
    sys.exit(main())
