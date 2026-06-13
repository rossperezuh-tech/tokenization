"""
LoopNet scraper (CoStar).

LoopNet has aggressive bot detection, so a plain request usually fails — this
uses a hardened Playwright browser (see scrapers/base.build_browser_context)
and, for tougher cases, a proxy via the SCRAPER_PROXY env var.

Extraction strategy (in order of reliability):
  1. JSON-LD          — LoopNet embeds <script type="application/ld+json">
     blocks describing each listing (schema.org). This survives CSS redesigns.
  2. EMBEDDED STATE   — CoStar stores a results object on window (digitalData /
     __INITIAL_STATE__); we try to read it.
  3. CSS SELECTORS    — placard cards as a last resort (brittle; verify after
     a real run since the live class names may differ).

Config (env):
  LOOPNET_SEARCH_URL  the search results URL to scrape (default: NYC for-sale)
  LOOPNET_MAX_PAGES   number of result pages to paginate (default 3)
  LOOPNET_HEADLESS    "false" to watch the browser
  SCRAPER_PROXY       optional proxy (recommended for LoopNet)
"""

import json
import logging
import os
from typing import Optional

from sqlalchemy.orm import Session

from models.database import LeadSource
from scrapers.base import (
    upsert_listing, build_browser_context, headless_from_env, parse_dom,
)

logger = logging.getLogger(__name__)

DEFAULT_SEARCH_URL = (
    "https://www.loopnet.com/search/commercial-real-estate/new-york-ny/for-sale/"
)
MIN_DOM = 90


# ── JSON-LD extraction ───────────────────────────────────────────────────

def _listings_from_jsonld(blocks: list[str]) -> list[dict]:
    """Parse schema.org JSON-LD blocks into loose listing dicts."""
    out = []
    for block in blocks:
        try:
            data = json.loads(block)
        except Exception:
            continue
        candidates = data if isinstance(data, list) else [data]
        # @graph wrapper is common
        for c in list(candidates):
            if isinstance(c, dict) and "@graph" in c:
                candidates.extend(c["@graph"])
        for item in candidates:
            if not isinstance(item, dict):
                continue
            typ = item.get("@type", "")
            if isinstance(typ, list):
                typ = " ".join(typ)
            if not any(t in str(typ) for t in ("Product", "Place", "Residence", "Offer", "RealEstateListing")):
                continue
            offers = item.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            addr = item.get("address", {})
            if isinstance(addr, dict):
                street = addr.get("streetAddress")
                city = addr.get("addressLocality")
                state = addr.get("addressRegion")
                zip_code = addr.get("postalCode")
            else:
                street, city, state, zip_code = addr, None, None, None
            geo = item.get("geo", {}) or {}
            out.append({
                "url": item.get("url"),
                "external_id": f"loopnet:{item.get('url') or item.get('name')}",
                "address": street or item.get("name"),
                "city": city, "state": state, "zip_code": zip_code,
                "latitude": geo.get("latitude"),
                "longitude": geo.get("longitude"),
                "property_type": item.get("category") or item.get("@type"),
                "asking_price": offers.get("price") if isinstance(offers, dict) else None,
                "raw": item,
            })
    return out


# ── CSS fallback ─────────────────────────────────────────────────────────

async def _parse_placard(card) -> dict:
    async def txt(sel):
        el = await card.query_selector(sel)
        return (await el.inner_text()).strip() if el else None
    link = await card.query_selector("a[href]")
    url = await link.get_attribute("href") if link else None
    return {
        "url": url,
        "address": await txt(".placard-title a, [class*='address'], .property-address"),
        "asking_price": await txt(".price, [class*='price']"),
        "property_type": await txt("[class*='type'], .property-type"),
        "days_on_market": await txt("[class*='days'], [class*='dom'], [class*='market']"),
        "cap_rate": await txt("[class*='cap']"),
        "sqft": await txt("[class*='sqft'], [class*='size']"),
        "broker_name": await txt("[class*='broker'], [class*='agent']"),
    }


async def scrape_loopnet(db: Session) -> list:
    """Public entry. Returns list of Lead objects saved/updated."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright not installed — run: pip install playwright && playwright install chromium")
        return []

    search_url = os.environ.get("LOOPNET_SEARCH_URL", DEFAULT_SEARCH_URL)
    max_pages = int(os.environ.get("LOOPNET_MAX_PAGES", "3"))
    headless = headless_from_env("LOOPNET_HEADLESS")
    new_leads = []

    async with async_playwright() as pw:
        browser, context = await build_browser_context(pw, headless=headless)
        page = await context.new_page()
        try:
            for page_num in range(1, max_pages + 1):
                url = search_url if page_num == 1 else f"{search_url.rstrip('/')}/{page_num}/"
                await page.goto(url, timeout=45_000, wait_until="domcontentloaded")
                await page.wait_for_timeout(2500)

                # Detect a block / captcha wall early
                title = (await page.title()).lower()
                if "access denied" in title or "are you a robot" in title or "blocked" in title:
                    logger.warning("LoopNet blocked on page %d (title=%r). Try SCRAPER_PROXY.", page_num, title)
                    break

                page_leads = await _extract_page(page, db)
                logger.info("LoopNet page %d: %d leads", page_num, len(page_leads))
                new_leads.extend(page_leads)
                if not page_leads:
                    break
        except Exception as exc:
            logger.error("LoopNet scrape failed: %s", exc)
        finally:
            await browser.close()

    return new_leads


async def _extract_page(page, db: Session) -> list:
    leads = []

    # 1) JSON-LD
    blocks = await page.eval_on_selector_all(
        "script[type='application/ld+json']",
        "els => els.map(e => e.textContent)"
    )
    listings = _listings_from_jsonld(blocks or [])

    # 2) Embedded state (best-effort)
    if not listings:
        state = await page.evaluate(
            "() => { try { return JSON.stringify(window.digitalData || window.__INITIAL_STATE__ || null); }"
            " catch(e){ return null; } }"
        )
        if state:
            try:
                blob = json.loads(state)
                listings = _listings_from_state(blob)
            except Exception:
                pass

    # 3) CSS placards
    if not listings:
        cards = await page.query_selector_all(
            ".placard-container, [class*='placard'], article[class*='listing']"
        )
        for card in cards:
            try:
                listings.append(await _parse_placard(card))
            except Exception:
                continue

    for listing in listings:
        dom = parse_dom(listing.get("days_on_market"))
        # JSON-LD often lacks DOM; keep those (filter applied when DOM known)
        if dom is not None and dom < MIN_DOM:
            continue
        lead = upsert_listing(listing, LeadSource.OUTBOUND_LOOPNET.value, db)
        if lead:
            leads.append(lead)
    return leads


def _listings_from_state(blob, _depth=0) -> list[dict]:
    """Best-effort: pull listing-like dicts out of an embedded state object."""
    found = []
    if _depth > 8:
        return found
    if isinstance(blob, list):
        for item in blob:
            found.extend(_listings_from_state(item, _depth + 1))
    elif isinstance(blob, dict):
        if any(k in blob for k in ("ListingId", "listingId", "PriceText", "Price")):
            found.append({
                "external_id": f"loopnet:{blob.get('ListingId') or blob.get('listingId')}",
                "url": blob.get("Url") or blob.get("url"),
                "address": blob.get("Address") or blob.get("address"),
                "city": blob.get("City"), "state": blob.get("State"),
                "asking_price": blob.get("Price") or blob.get("PriceText"),
                "property_type": blob.get("PropertyType") or blob.get("UseType"),
                "days_on_market": blob.get("DaysOnMarket"),
                "cap_rate": blob.get("CapRate"),
                "sqft": blob.get("BuildingSize") or blob.get("SquareFeet"),
                "raw": blob,
            })
        else:
            for v in blob.values():
                found.extend(_listings_from_state(v, _depth + 1))
    return found
