# Crossplay research brief (2026-10-26)

You research crossplay facts for crossplayguide.com. Accuracy is everything: Mike has approved publishing
this batch WITHOUT his manual review, because every entry gets researched once and then independently
re-checked by a second agent. Never guess. If you can't confirm something from a source, leave it out or
say plainly in the note that it is unconfirmed.

## Read first
- /home/mike/Work/crossplay/research/audit.md (the deep audit checklist: follow every item)
- /home/mike/Work/crossplay/data/manual.json (look at 3-4 entries, e.g. "7 Days to Die", "Dying Light",
  "Brotato", "A Way Out", to copy the exact format and the note style)
- /home/mike/Work/crossplay/research/todo.md (earlier notes on some of these games)

## Entry format (one JSON object per game)
- `title`: the name people search for. `igdb_id`: null (filled in later by a script).
- Crossplay games: `groups` = list of `{"platforms": {key: "yes"|"partial"}, "pc_stores": [...]}`; each group
  is a set of platforms that play together. Platforms with their own separate pool can be their own group.
  Platform keys: pc, mac, linux, ps4, ps5, xone, xseries, switch, switch2, ios, android, quest, xcloud,
  geforcenow, luna. Use "partial" only when the note explains the limit.
- No crossplay: `"crossplay": false` plus a `verdict` {kind:"no", word:"No", summary:"one sentence"} when the
  reason needs explaining (e.g. local co-op only, single-player only, PC only). `separate`: list of platform
  keys that each play only among themselves (optional).
- `notes`: 1-4 short plain-English sentences/paragraphs in our own words (never copied). Cover modes,
  cross-gen, PC stores, accounts needed, opt-out settings, dates of changes. No em dashes or en dashes.
- `sources`: 2+ items {title, url}. Prefer official (publisher support, patch notes, official blogs,
  PlayStation Blog, Xbox Wire, store pages), then reputable press. Every claim in notes must be backed by
  at least one listed source. NEVER use PCGamingWiki (licence). Avoid Reddit/Fandom unless you say it's a
  player report. Use real URLs you actually opened (WebFetch them).
- Optional: `crossprog` ("yes"|"partial"|"no", only when sourced), `progress` (list of 1 sentence about
  cross-progression), `toggle` (list of 1 sentence: where the crossplay setting is), `f2p`: true if free.
- `checked`: "2026-10-26".
- Watch for changes in 2025-2026: crossplay added/removed by patch, new ports (Switch 2, PS5, Xbox Series),
  shutdowns. Today is 2026-10-26; your search results may be older, so look for the newest info.
- If a game is unreleased or its crossplay is genuinely unknowable right now, output
  {"title":..., "skip": "reason"} instead of an entry.

## Output
Write a JSON array to the file path given in your task (only that file; do not edit anything else in the
repo). Then reply with a one-line summary per game (verdict + confidence).
