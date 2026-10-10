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

## Media, Game Pass, cross-progression, community (added 2026-10-10)

- `collector/media.py` (nightly): picks a playable YouTube trailer per game from IGDB videos (`data/trailers.json`
  caches oEmbed checks) and pulls the Xbox Game Pass PC and console catalogues (`data/gamepass.json`; free-to-play
  games are flagged and ignored). Game pages show a click-to-load trailer (no YouTube cookies until play), up to 4
  IGDB screenshots, and a "Game Pass" fact; `/game-pass/` lists crossplay games on Game Pass.
- `crossprog` ("yes" | "partial" | "no") on researched entries shows a cross-progression tag in the answer box.
- `/feed.xml` is an RSS feed of the updates log.
- Community features live in `worker/` (see worker/README.md). They're hidden until `API_URL` is set in config.
- Discovery signals for future research: Xbox store products carry `XblCrossPlatformMultiPlayer` (crossplay with
  *something*, not which platforms) and Steam has a "Cross-Platform Multiplayer" category. RAWG's API is free for
  commercial use under 500k page views/month with a link back; Giant Bomb's API is non-commercial; MobyGames' is paid.
- Community API is LIVE at https://crossplay-community.crossplayguide.workers.dev (Cloudflare account
  Mike@thekitchenmagpie.com, D1 `crossplay-community`). Moderate at /admin (user `admin`). Deploy creds:
  API token in ~/.config/kitchen-magpie/cloudflare.env; admin password and IP-hash salt in
  ~/.config/kitchen-magpie/crossplay-admin.env (never commit either).
