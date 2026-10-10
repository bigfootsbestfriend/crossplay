#!/usr/bin/env python3
"""Upsert researched games into data/manual.json: pipe a JSON list of entries on stdin.

Entry: {"title", "igdb_id", "crossplay" (default true), "groups": [{"platforms": {"pc": "yes", ...},
"pc_stores": [...]}], "separate": [...], "notes": [...], "sources": [{"title", "url"}], "replaces": [...]}
"checked" defaults to today.
"""
import datetime, json, sys
from pathlib import Path
P = Path(__file__).resolve().parent.parent / "data" / "manual.json"
KEYS = {"pc", "mac", "linux", "ps5", "ps4", "xseries", "xone", "switch", "switch2", "ios", "android", "quest",
        "geforcenow", "xcloud", "luna"}
data = json.loads(P.read_text())
by = {g["title"]: g for g in data["games"]}
for g in json.load(sys.stdin):
    g.setdefault("checked", datetime.date.today().isoformat())
    assert g.get("sources"), g["title"]
    for gr in g.get("groups", []):
        bad = set(gr["platforms"]) - KEYS
        assert not bad, (g["title"], bad)
    assert not set(g.get("separate", [])) - KEYS, g["title"]
    print(("updated " if g["title"] in by else "added ") + g["title"])
    by[g["title"]] = g
data["games"] = sorted(by.values(), key=lambda g: g["title"].lower())
P.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
print(len(data["games"]), "researched games")
