# Handoff: Crossplay Guide

Built overnight 2026-10-09/10. To carry on in Claude Code: open this repo and say
**"Read HANDOFF.md and carry on."**

## What exists

- **Preview:** https://bigfootsbestfriend.github.io/crossplay/ (noindex until reviewed)
- **376 pages:**
  - 327 game pages: 304 with current crossplay, 23 where crossplay has ended
  - 10 platform hubs
  - 15 platform-pair hubs (e.g. `/crossplay/playstation-and-switch/`)
  - 17 genre hubs (co-op, shooters, split screen, horror, …)
  - all-games A–Z, recent changes, about/methodology, privacy, 404, sitemap
- **Each game page has:**
  - a yes / partly / no answer
  - its crossplay groups and the PC stores they cover
  - a "check your two platforms" picker
  - quick answers for each platform pair
  - multiplayer facts from IGDB (player counts, co-op, split screen)
  - game details, cited sources, related games, and FAQ/VideoGame schema
- **Nightly GitHub Action** (08:41 UTC):
  1. re-reads Wikipedia
  2. matches new games on IGDB, and re-fetches every game's IGDB facts on Sundays
  3. commits `data/`, logs changes on /updates/
  4. rebuilds and deploys

## Decisions for Mike

1. **Name and domain.** The working name is "Crossplay Guide" and lives in `site/config.py`.
   - Available .com names when checked: crossplayguide, cancrossplay, iscrossplatform, crossplayfinder, crossplayable, crossplaylist.
   - Once bought at Namecheap:
     - set `DOMAIN` in config
     - add GitHub Pages DNS: A records 185.199.108–111.153, plus a CNAME record for www
     - set the custom domain in the repo's Pages settings
2. **Review, then go live.** Skim a dozen game pages, then set `INDEXABLE = True` and push.
   - Raptive and Google both expect real human oversight, which is why indexing is off until you've looked.
   - After going live:
     - submit the sitemap in Search Console and Bing
     - apply to Raptive and paste their script into `AD_SCRIPT`
3. **Corrections inbox.** Set `CONTACT_EMAIL`, e.g. a Namecheap forward. Until then, "Report a mistake" links to GitHub issues.

## Researched games (data/manual.json)

Wikipedia's list misses many of the most-played games, so we research those ourselves.

- `data/manual.json` holds researched entries: crossplay groups, platforms with no crossplay
  (`separate`), `crossplay: false` for games without it, notes, sources and a `checked` date.
  A researched entry replaces the Wikipedia row with the same title (or any title in `replaces`).
- `data/title_overrides.json` renames Wikipedia titles to what people search for
  (e.g. "Fortnite Battle Royale" becomes "Fortnite").
- `research/candidates_missing.json` is the to-do list: popular multiplayer games (IGDB play counts,
  Steam peak players, Twitch hours) that aren't covered yet, most popular first.
- Add or update entries with `research/add.py` (pipe a JSON list on stdin). Then run
  `collector/igdb_match.py` for covers and facts, and rebuild.
- `research/todo.md` lists games skipped because sources conflicted or a change was imminent.
- `research/stale.py [days]` lists entries not re-checked recently. Re-check them every 3 months.
- Sources: prefer the publisher's FAQ, support pages or patch notes; otherwise use reputable press.
  PCGamingWiki is CC BY-NC-SA (no commercial use), so don't copy from it.

## Known limits and next steps

- **Coverage:** about 94 researched games plus Wikipedia's list. Keep working down `candidates_missing.json`.
- **"Not confirmed" platforms** are ones IGDB says the game is on but no crossplay group includes, e.g. Terraria on Switch. The page words these carefully ("our sources don't list crossplay for that version") rather than saying "no".
- **The Wikipedia list has no Switch 2 column.** Switch 2 is assumed to share the Switch group.
- **Bad IGDB matches:** add `"Wikipedia title": igdb_id` (or `null`) to `data/igdb_overrides.json`.
- **Ideas:**
  - cross-progression facts
  - "best crossplay games" editorial pages, written or reviewed by a human
  - a Kit newsletter for crossplay news, using its own account, not Magpie's

## Gotchas

- **The repo is public,** so commits use the no-reply email 209829115+bigfootsbestfriend@users.noreply.github.com.
- **Secrets:** IGDB_CLIENT_ID and IGDB_CLIENT_SECRET are set as Actions secrets. The local `.env` is gitignored.
- **The site uses `/crossplay` as its base path** while on the github.io preview. Setting `DOMAIN` switches that to `/` and writes a CNAME file.
