# LoopNet & Crexi Scrapers — Operating Guide

This is the honest, practical guide to running the outbound scrapers. They are
built to be robust, but LoopNet (CoStar) and Crexi actively defend against
automated access, so **expect to do some tuning on first run** and occasional
maintenance as the sites change.

> The dev sandbox these were authored in has **no outbound internet**, so the
> selectors and API field names below are based on how these sites are
> structured — they could not be verified against the live sites here. The
> `--dump` flag exists precisely so you can confirm the real shapes on your
> first run and adjust.

---

## Quick start (on a machine with internet)

```bash
cd backend
pip install -r requirements.txt
playwright install chromium          # one-time: downloads the browser

cp .env.example .env                 # then fill in values (see below)

# Run them:
python run_scraper.py crexi              # Crexi only (API-first, fastest)
python run_scraper.py loopnet --headed   # LoopNet, visible browser to watch
python run_scraper.py all --max-pages 5
python run_scraper.py crexi --dump       # print raw JSON to inspect field names
```

Scraped leads are scored and written to the same `leads` table the dashboard
reads, so they show up in the UI immediately.

---

## How each scraper works

### Crexi — `scrapers/crexi.py`
1. **Primary: internal JSON API** (`api.crexi.com/assets`). The Crexi web app
   itself fetches listings from this endpoint. Pulling JSON directly is far more
   reliable than parsing HTML. Returns price, type, sqft, cap rate, broker
   contacts, and lat/lng.
2. **Fallback: Playwright DOM.** If the API returns 401/403, it renders the
   search page and reads the embedded `__NEXT_DATA__` JSON, then CSS selectors.

**Tuning:** field names in the API response are not contractually stable. Run
`python run_scraper.py crexi --dump` and compare the printed `raw` JSON against
the key lists in `_map_api_record()`. Add any new key names to the relevant
`_first(...)` call.

To capture the exact API URL your market uses: open crexi.com, DevTools →
Network → filter "assets", run your search, copy the request URL into
`CREXI_API_URL` in `.env`.

### LoopNet — `scrapers/loopnet.py`
Playwright only (no public API). Extraction order:
1. **JSON-LD** — `<script type="application/ld+json">` schema.org blocks. Most
   durable.
2. **Embedded state** — `window.digitalData` / `__INITIAL_STATE__`.
3. **CSS placards** — last resort; class names change, so verify with `--headed`.

**LoopNet will likely block a datacenter IP.** If you see "blocked"/"access
denied" in the logs, set `SCRAPER_PROXY` to a residential/rotating proxy.

---

## Configuration (`.env`)

| Var | Purpose |
|-----|---------|
| `SCRAPER_PROXY` | `http://user:pass@host:port` — residential proxy. **Needed for LoopNet.** |
| `LOOPNET_SEARCH_URL` | Search URL; copy from loopnet.com address bar for your market. |
| `LOOPNET_MAX_PAGES` | Result pages to paginate (default 3). |
| `LOOPNET_HEADLESS` | `false` to watch the browser. |
| `CREXI_API_URL` | Override the internal API endpoint/query. |
| `CREXI_SEARCH_URL` | DOM-fallback search URL. |
| `CREXI_MAX_PAGES` / `CREXI_HEADLESS` | As above. |

Only listings with **≥90 days on market** are kept (the `MIN_DOM` constant in
each file). Listings where DOM is unknown are kept and scored without the DOM
bonus.

---

## When a scrape returns 0 leads

The runner prints the likely causes. In order of probability:
1. **Blocked** — set `SCRAPER_PROXY`. Confirm with `--headed` (you'll see a
   captcha or "access denied" page).
2. **0 listings ≥90 DOM** for your search — widen `*_SEARCH_URL`.
3. **Markup/fields changed** — run with `--dump`, inspect `raw_data`, update the
   selector/key lists.

---

## The lower-maintenance alternative

Direct scraping of CoStar/Crexi is an ongoing arms race. If you want this to
"just work" without babysitting, point the scrapers at a managed scraping API
that handles proxies + captchas for you:

- **Apify** has off-the-shelf LoopNet and Crexi actors that return JSON.
- **Zyte / ScraperAPI / Bright Data** offer proxy + unblocking endpoints — set
  `SCRAPER_PROXY` to their proxy and the existing code works unchanged.

To use Apify instead of direct scraping, you'd swap the body of
`scrape_loopnet` / `scrape_crexi` to call the actor and map its JSON through the
same `upsert_listing(...)` helper — the scoring/DB/dashboard layers don't change.

---

## Legal note

Scraping LoopNet and Crexi is against their Terms of Service. This is intended
for your own authorized lead-generation research. Respect rate limits (the
default 3 pages + the built-in waits are deliberately gentle), and consider
whether a data-licensing or API arrangement fits your volume.
