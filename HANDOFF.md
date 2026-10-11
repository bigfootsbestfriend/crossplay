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

## Status and decisions for Mike (as of 2026-10-11)

- **Live and indexable** at crossplayguide.com (DNS on Cloudflare, HTTPS). Only audited games and hubs are in the
  sitemap; unaudited games stay noindex. Search check-in is on the calendar for 2026-11-24.
- **Still open:** apply to Raptive and paste their script into `AD_SCRIPT`; confirm the About bio wording; switch the
  weekly email from draft to send in the newsletter repo's sites.json.

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

## Search-quality guardrails (2026-10-10)
- Only game pages whose manual.json entry has `"audited"` are indexable and in the sitemap (see research/audit.md);
  everything else gets `noindex` via `page(..., noindex=True)`.
- Researched pages carry a "Researched by {config.AUTHOR}" byline linking to /about/#who (photo: static/mike-johnston.jpg).
- The About page discloses that AI tools help find and read sources.

## Group features and email prompts (2026-10-10/11)

- **Your group** box in every game's answer: visitors tap their group's platforms once (localStorage `together`, shared
  with /who-can-i-play-with/) and each game says whether they can all play together. One-tap "did it work?" vote posts
  to the community Worker /api/vote; the tally shows there from 3 votes.
- **Group finder:** "Share this group" makes `?p=ps5,pc,switch2` links; Switch 2 now matches Switch crossplay groups.
- **Email prompts:** "Tell me if X gets crossplay" button in the answer, signup box after the platform groups, one
  dismissible bottom bar (14-day cooldown), footer link.

## Social feed (/social.xml)

- Built by `social_feed()` in site/build.py; a Metricool autolist reads it and posts to X, Bluesky and Threads.
- Announces a checked (audited) game the first time it appears, and an update only when its manual.json entry
  gets a new `news` line: `"news": {"date": "2026-10-15", "text": "Crossplay is live: ..."}`. Add one whenever a
  verdict or platform list changes for real. At most 2 items a day (autolist slots 12:30 and 7:30 PM MT); extras wait in data/social.json's queue.
- Instagram and Facebook posts are scheduled in batches (Metricool + GRO comment-for-DM queue), never from the feed,
  because every IG/FB post uses up the next queued GRO automation.

## Share images (og:image)

- site/build.py writes _site/og/cards.json; site/og.py (Pillow, run by the workflow after the build) draws a
  1200x630 verdict card per game at /og/<slug>.png plus /og/default.png for every other page. Fonts and the logo
  are in site/og_assets (Space Grotesk + Inter, OFL). Locally: `pip install pillow && python3 site/og.py`.
- New researched games need `collector/igdb_match.py` (IGDB keys in .env) before they build, especially
  "no crossplay" entries, whose platform list comes from IGDB.
