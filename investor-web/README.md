# Vesta Invest — investor website

The investor-facing website, matching the Nexus private-bank dashboard design.
A single self-contained `index.html` (no build step) — host it anywhere static.

## What's live vs. illustrative

- **Current offerings** — fetched live from the Vesta backend
  (`GET /api/offerings`). Deals you publish at the Token Offering stage of the
  pipeline appear here automatically.
- Portfolio value, holdings table, distributions coupon rail, and secondary
  market order book currently use sample data — wire these to a connected
  wallet / on-chain reads (see `investor-app`) when you're ready.

## Configure

Set these before the page scripts run (e.g. via a small inline script, your
host's env injection, or by editing the constants in `index.html`):

```html
<script>
  window.VESTA_API_URL = "https://api.yourdomain.com";   // your backend
  window.VESTA_INVEST_URL = "https://invest.yourdomain.com/property"; // app/web deep link
</script>
```

Defaults: `http://localhost:8000` for the API, `vesta://property` for invest links.

## Run locally

```bash
# from repo root, with the backend running on :8000
cd investor-web
python -m http.server 8090
# open http://localhost:8090
```

The "View & invest" buttons deep-link to the investor app (`investor-app/`),
which handles wallet connect and the on-chain purchase.
