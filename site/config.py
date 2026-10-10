"""Site settings. Change the name or attach a domain here; everything else follows."""
import os

SITE_NAME = "Crossplay Guide"
LOGO_KICKER = "Can we play?"   # small mono line above the wordmark
LOGO_WORD = "Crossplay"
TAGLINE = "Can you play together? Crossplay checks for every platform."

# Leave DOMAIN empty for the GitHub Pages preview. Once a domain is bought and pointed at
# GitHub Pages, set it (e.g. "crossplayguide.com"): links drop the /crossplay prefix and a
# CNAME file is written.
DOMAIN = "crossplayguide.com"
PREVIEW_URL = "https://bigfootsbestfriend.github.io/crossplay"

# Keep False until a person has reviewed the site (Raptive and Google both expect real human
# oversight). False adds <meta name="robots" content="noindex"> to every page.
INDEXABLE = True

# Search engine ownership tags (content values only). Empty = no tag.
GOOGLE_VERIFY = ""
BING_VERIFY = "166ED942B039ECB32E7BF3985158FC36"
# IndexNow key (public by design: served at /<key>.txt so Bing and others accept URL pings).
INDEXNOW_KEY = "c24c67d2ddaa434f8deb5fe4c68c0578"

# Where readers send corrections. Empty = link to GitHub issues instead.
CONTACT_EMAIL = "hello@crossplayguide.com"

# Paste Raptive's site script here once the site is approved (it goes in <head>).
AD_SCRIPT = ""

if DOMAIN:
    BASE_URL, BASE_PATH = "https://" + DOMAIN, ""
else:
    BASE_URL, BASE_PATH = PREVIEW_URL, "/crossplay"

# Community features (player crossplay reports and moderated tips) need the Cloudflare Worker in worker/.
# Leave API_URL empty to hide them. TURNSTILE_SITEKEY is optional (Cloudflare's free anti-bot check).
API_URL = os.environ.get("CROSSPLAY_API_URL", "https://crossplay-community.crossplayguide.workers.dev")  # env override is for local previews
TURNSTILE_SITEKEY = ""

# Google Analytics 4 measurement ID (looks like "G-XXXXXXXXXX"). Empty = no analytics tag.
AUTHOR = "Mike Johnston"
GA_ID = "G-SQ13RNQQNR"
CLICKY_ID = "101513000"
