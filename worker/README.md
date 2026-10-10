# Community API (Cloudflare Worker + D1)

Powers "Did crossplay work for you?" votes and moderated player tips on game pages. Free tier is plenty.

## First deploy
```sh
cd worker
npx wrangler login                                   # opens the browser once
npx wrangler d1 create crossplay-community           # paste the printed database_id into wrangler.toml
npx wrangler d1 execute crossplay-community --remote --file schema.sql
npx wrangler secret put ADMIN_PASSWORD               # password for /admin (user name: admin)
npx wrangler secret put HASH_SALT                    # any long random string
npx wrangler deploy                                  # prints https://crossplay-community.<account>.workers.dev
```
Then set `API_URL` in `site/config.py` to that URL and push. Optional: create a Turnstile widget in the
Cloudflare dashboard, put its site key in `TURNSTILE_SITEKEY` and its secret in `npx wrangler secret put TURNSTILE_SECRET`.

## Moderating
Open `<worker url>/admin`. Tips stay hidden until approved; reports ("this page is wrong") go in the same queue,
marked in red. The page also lists games where players report crossplay *not* working, which are the ones to re-research.

## Local testing
```sh
printf 'ADMIN_PASSWORD=localtest\nHASH_SALT=x\n' > .dev.vars
npx wrangler d1 execute crossplay-community --local --file schema.sql
npx wrangler dev --local --port 8787
# in another shell, from the repo root:
CROSSPLAY_API_URL=http://localhost:8787 python3 site/build.py
```
