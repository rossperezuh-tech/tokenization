"""
Crexi scraper.

Strategy (in order of reliability):
  1. INTERNAL JSON API  — the Crexi web app fetches listings from
     https://api.crexi.com/assets with query params. Scraping this returns
     clean structured JSON (price, type, sqft, brokers, lat/lng) and is far
     more durable than parsing HTML. This is the PRIMARY path.
  2. PLAYWRIGHT DOM     — fallback if the API path is blocked or its shape
     changed. Reads the embedded Next.js __NEXT_DATA__ JSON blob, then falls
     back to CSS selectors.

Because field names on the internal API are not contractually stable, parsing
is defensive: every field tries several likely key names and we stash the raw
record in raw_data so you can inspect the true shape after a real run.

Config (env):
  CREXI_API_URL       override the API endpoint/query (default below)
  CREXI_SEARCH_URL    the human search URL for the DOM fallback
  CREXI_MAX_PAGES     how many pages of results to pull (default 3)
  CREXI_HEADLESS      "false" to watch the browser (DOM fallback only)
  SCRAPER_PROXY       optional proxy for both paths
"""

import logging
import os
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from models.database import LeadSource
from scrapers.base import (
    upsert_listing, build_browser_context, headless_from_env,
    REALISTIC_UA, parse_dom,
)

logger = logging.getLogger(__name__)

DEFAULT_API_URL = (
    "https://api.crexi.com/assets"
    "?pageSize=60&offset=0&searchRadius=0"
    "&geoLatitude=40.7128&geoLongitude=-74.0060&geoRadius=25"
    "&types[]=Multifamily&types[]=Industrial&types[]=Retail"
    "&types[]=Office&types[]=Mixed%20Use"
    "&sortDirection=Descending&sortOrder=Activated"
)
DEFAULT_SEARCH_URL = "https://www.crexi.com/properties?placeId=&mapZoom=11&types[]=Multifamily"
MIN_DOM = 90


def _first(d: dict, *keys, default=None):
    """Return the first present, non-null value among keys (supports a.b dotted paths)."""
    for k in keys:
        cur = d
        ok = True
        for part in k.split("."):
            if isinstance(cur, dict) and part in cur and cur[part] is not None:
                cur = cur[part]
            else:
                ok = False
                break
        if ok:
            return cur
    return default


def _map_api_record(rec: dict) -> dict:
    """Map one Crexi API asset record into our loose listing dict (defensive)."""
    asset_id = _first(rec, "id", "assetId", "urlSlug")
    brokers = _first(rec, "brokers", "brokerTeam", "contacts", default=[]) or []
    broker = brokers[0] if isinstance(brokers, list) and brokers else {}

    return {
        "external_id": f"crexi:{asset_id}" if asset_id else None,
        "url": _first(rec, "url", "detailsUrl", "urlSlug"),
        "address": _first(rec, "address", "fullAddress", "location.address", "name"),
        "city": _first(rec, "city", "location.city", default="New York"),
        "state": _first(rec, "state", "location.state", default="NY"),
        "zip_code": _first(rec, "zip", "zipCode", "location.zip"),
        "latitude": _first(rec, "latitude", "lat", "location.latitude"),
        "longitude": _first(rec, "longitude", "lng", "location.longitude"),
        "property_type": _first(rec, "type", "propertyType", "types.0", "assetType"),
        "asking_price": _first(rec, "askingPrice", "price", "listingPrice"),
        "sqft": _first(rec, "squareFeet", "sqft", "buildingSize", "rentableSqft"),
        "cap_rate": _first(rec, "capRate", "cap_rate"),
        "noi": _first(rec, "noi", "netOperatingIncome"),
        "days_on_market": _first(rec, "daysOnMarket", "activeDays", "daysActive"),
        "broker_name": _first(broker, "name", "fullName", "firstName"),
        "broker_email": _first(broker, "email", "emailAddress"),
        "broker_phone": _first(broker, "phone", "phoneNumber", "mobile"),
        "raw": rec,
    }


def _scrape_via_api(db: Session) -> Optional[list]:
    """Primary path: hit Crexi's internal JSON API. Returns list of Leads, or None if blocked."""
    url = os.environ.get("CREXI_API_URL", DEFAULT_API_URL)
    headers = {
        "User-Agent": REALISTIC_UA,
        "Accept": "application/json",
        "Origin": "https://www.crexi.com",
        "Referer": "https://www.crexi.com/",
    }
    proxy = os.environ.get("SCRAPER_PROXY") or None
    max_pages = int(os.environ.get("CREXI_MAX_PAGES", "3"))

    new_leads = []
    try:
        client_kwargs = {"headers": headers, "timeout": 20}
        if proxy:
            client_kwargs["proxies"] = proxy
        with httpx.Client(**client_kwargs) as client:
            for page in range(max_pages):
                paged = url.replace("offset=0", f"offset={page * 60}")
                resp = client.get(paged)
                if resp.status_code == 403 or resp.status_code == 401:
                    logger.warning("Crexi API blocked (HTTP %d) — falling back to DOM", resp.status_code)
                    return None
                resp.raise_for_status()
                payload = resp.json()
                records = (
                    payload.get("data")
                    or payload.get("assets")
                    or payload.get("results")
                    or (payload if isinstance(payload, list) else [])
                )
                if not records:
                    break
                for rec in records:
                    listing = _map_api_record(rec)
                    dom = parse_dom(listing.get("days_on_market"))
                    if dom is not None and dom < MIN_DOM:
                        continue
                    lead = upsert_listing(listing, LeadSource.OUTBOUND_CREXI.value, db)
                    if lead:
                        new_leads.append(lead)
        logger.info("Crexi API: %d leads (≥%d DOM)", len(new_leads), MIN_DOM)
        return new_leads
    except Exception as exc:
        logger.warning("Crexi API path failed (%s) — falling back to DOM", exc)
        return None


async def _scrape_via_dom(db: Session) -> list:
    """Fallback path: render the search page and read __NEXT_DATA__ / DOM cards."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright not installed — run: pip install playwright && playwright install chromium")
        return []

    search_url = os.environ.get("CREXI_SEARCH_URL", DEFAULT_SEARCH_URL)
    headless = headless_from_env("CREXI_HEADLESS")
    new_leads = []

    async with async_playwright() as pw:
        browser, context = await build_browser_context(pw, headless=headless)
        page = await context.new_page()
        try:
            await page.goto(search_url, timeout=45_000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            # Preferred: pull the embedded Next.js data blob
            next_data = await page.evaluate(
                "() => { const el = document.getElementById('__NEXT_DATA__');"
                " return el ? el.textContent : null; }"
            )
            if next_data:
                import json as _json
                try:
                    blob = _json.loads(next_data)
                    records = _find_assets_in_blob(blob)
                    for rec in records:
                        listing = _map_api_record(rec)
                        dom = parse_dom(listing.get("days_on_market"))
                        if dom is not None and dom < MIN_DOM:
                            continue
                        lead = upsert_listing(listing, LeadSource.OUTBOUND_CREXI.value, db)
                        if lead:
                            new_leads.append(lead)
                    if new_leads:
                        logger.info("Crexi DOM(__NEXT_DATA__): %d leads", len(new_leads))
                        return new_leads
                except Exception as exc:
                    logger.warning("Crexi __NEXT_DATA__ parse failed: %s", exc)

            # Last resort: CSS selectors (brittle — verify on a real run)
            cards = await page.query_selector_all(
                "[class*='property-tile'], [class*='PropertyTile'], [data-testid*='property']"
            )
            logger.info("Crexi DOM(css): %d cards", len(cards))
            for card in cards:
                try:
                    listing = await _parse_card(card)
                    dom = parse_dom(listing.get("days_on_market"))
                    if dom is not None and dom < MIN_DOM:
                        continue
                    lead = upsert_listing(listing, LeadSource.OUTBOUND_CREXI.value, db)
                    if lead:
                        new_leads.append(lead)
                except Exception as exc:
                    logger.debug("Crexi card parse error: %s", exc)
        except Exception as exc:
            logger.error("Crexi DOM scrape failed: %s", exc)
        finally:
            await browser.close()
    return new_leads


def _find_assets_in_blob(blob, _depth=0):
    """Recursively locate a list of asset-like dicts inside the Next.js blob."""
    if _depth > 8:
        return []
    if isinstance(blob, list):
        if blob and isinstance(blob[0], dict) and any(
            k in blob[0] for k in ("askingPrice", "price", "capRate", "address")
        ):
            return blob
        for item in blob:
            found = _find_assets_in_blob(item, _depth + 1)
            if found:
                return found
    elif isinstance(blob, dict):
        for key in ("assets", "data", "results", "properties", "listings"):
            if key in blob and isinstance(blob[key], list) and blob[key]:
                if isinstance(blob[key][0], dict):
                    return blob[key]
        for v in blob.values():
            found = _find_assets_in_blob(v, _depth + 1)
            if found:
                return found
    return []


async def _parse_card(card) -> dict:
    async def txt(sel):
        el = await card.query_selector(sel)
        return (await el.inner_text()).strip() if el else None
    link = await card.query_selector("a[href]")
    url = await link.get_attribute("href") if link else None
    return {
        "url": url,
        "address": await txt("[class*='address'], [class*='Address']"),
        "asking_price": await txt("[class*='price'], [class*='Price']"),
        "property_type": await txt("[class*='type'], [class*='Type']"),
        "days_on_market": await txt("[class*='days'], [class*='Days'], [class*='dom']"),
        "cap_rate": await txt("[class*='cap'], [class*='Cap']"),
        "sqft": await txt("[class*='sqft'], [class*='size'], [class*='Size']"),
    }


async def scrape_crexi(db: Session) -> list:
    """Public entry: API first, DOM fallback. Returns list of Lead objects."""
    leads = _scrape_via_api(db)
    if leads is not None:
        return leads
    return await _scrape_via_dom(db)
