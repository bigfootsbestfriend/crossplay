# Crossplay Guide

A static site that answers "is [game] cross-platform?" for every game on Wikipedia's crossplay list,
with platform hubs ("PlayStation and Switch crossplay games") and genre hubs. It rebuilds itself every night.

- `collector/wikipedia.py`: parses the Wikipedia list into `data/wikipedia.json` and logs changes in `data/history.json`
- `collector/igdb_match.py`: matches each game to IGDB (`data/igdb.json`); fix bad matches in `data/igdb_overrides.json`
- `site/build.py`: builds `_site/` (settings in `site/config.py`)
- `.github/workflows/nightly.yml`: refreshes the data, commits it and deploys to GitHub Pages

Local run: put `IGDB_CLIENT_ID` and `IGDB_CLIENT_SECRET` in `.env`, then
`python3 collector/wikipedia.py && python3 collector/igdb_match.py && python3 site/build.py`.

Data: Wikipedia (CC BY-SA 4.0, attributed on every page) and IGDB.
