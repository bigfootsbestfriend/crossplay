# Crossplay pass 2: independent verification (2026-10-26)

A first agent researched these entries. Your job is to independently re-check EVERY claim before it goes
live without Mike's review. Be sceptical: assume pass 1 could be wrong or out of date.

Read /home/mike/Work/crossplay/research/batch/BRIEF.md and /home/mike/Work/crossplay/research/audit.md for
the format and rules.

For each entry in your input file:
1. Open every source URL (WebFetch). Check that it exists, says what the note claims, and isn't outdated.
2. Do your own fresh searches (WebSearch) for the game + "crossplay" / "cross-platform" / patch notes,
   looking especially for anything from 2025-2026 that changed the picture (crossplay added or removed,
   new ports such as Switch 2/PS5/Xbox Series, cross-gen, PC stores, shutdowns).
3. Check every platform in every group, every "separate"/"no crossplay" claim, crossprog/progress/toggle,
   f2p, and dates.
4. Fix anything wrong or unsupported: edit the entry, replace weak sources with better ones, remove claims
   you can't back up. If the overall verdict is genuinely uncertain (sources conflict and no official word),
   turn the entry into {"title":..., "skip":"reason"} rather than publish a guess.
5. Add to every entry a field "verify": {"result": "confirmed" | "corrected" | "skip", "what": "one line on
   what you checked/changed"}.

Notes: no em or en dashes; own words; never PCGamingWiki. Write the verified JSON array to the output path
in your task and nothing else in the repo. Reply with a one-line result per game.
