#!/usr/bin/env python3
"""List researched games whose "checked" date is older than N days (default 90): ./research/stale.py [days]"""
import datetime, json, sys
from pathlib import Path
days = int(sys.argv[1]) if len(sys.argv) > 1 else 90
cutoff = datetime.date.today() - datetime.timedelta(days=days)
games = json.loads((Path(__file__).resolve().parent.parent / "data" / "manual.json").read_text())["games"]
old = sorted((g["checked"], g["title"]) for g in games if datetime.date.fromisoformat(g["checked"]) < cutoff)
for checked, title in old:
    print(checked, title)
print(f"{len(old)} of {len(games)} researched games last checked before {cutoff}")
