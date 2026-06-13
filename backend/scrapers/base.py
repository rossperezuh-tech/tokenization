"""
Shared scraper infrastructure.

This module centralizes the parts that are identical across LoopNet and Crexi
so the individual scrapers only describe *where the data lives*, not *how to
save and score it*.

Key pieces:
  - parse_price / parse_dom / parse_cap_rate / parse_sqft  — tolerant parsers
  - normalize_property_type                                 — map free text to our enum
  - upsert_listing                                          — dedupe, score, save, track price changes
  - build_browser_context                                   — anti-bot Playwright context (stealth + proxy)
  - PROXY env support

All scrapers emit a plain dict ("listing") with whatever fields they could
find; upsert_listing does the rest. Missing fields are fine — the scorer and
DB are tolerant of None.
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from models.database import Lead, PriceHistory
from services.scoring import score_lead

logger = logging.getLogger(__name__)


# ── Tolerant field parsers ───────────────────────────────────────────────

def parse_price(raw) -> Optional[float]:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().lower().replace(",", "").replace("$", "")
    m = re.search(r"([\d.]+)\s*([mk]?)", text)
    if not m:
        return None
    try:
        val = float(m.group(1))
    except ValueError:
        return None
    suffix = m.group(2)
    if suffix == "m":
        val *= 1_000_000
    elif suffix == "k":
        val *= 1_000
    return val


def parse_dom(raw) -> Optional[int]:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    m = re.search(r"(\d+)", str(raw))
    return int(m.group(1)) if m else None


def parse_cap_rate(raw) -> Optional[float]:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    m = re.search(r"([\d.]+)", str(raw))
    return float(m.group(1)) if m else None


def parse_sqft(raw) -> Optional[float]:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).lower().replace(",", "")
    m = re.search(r"([\d.]+)", text)
    return float(m.group(1)) if m else None


_TYPE_KEYWORDS = [
    ("multifamily", "Multifamily"), ("multi-family", "Multifamily"),
    ("apartment", "Multifamily"), ("industrial", "Industrial"),
    ("warehouse", "Industrial"), ("flex", "Industrial"),
    ("mixed", "Mixed-Use"), ("retail", "Retail"), ("storefront", "Retail"),
    ("office", "Office"),
]


def normalize_property_type(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    low = str(raw).lower()
    for kw, label in _TYPE_KEYWORDS:
        if kw in low:
            return label
    return str(raw).strip().title()[:60]


# ── Save / dedupe / score ────────────────────────────────────────────────

def upsert_listing(listing: dict, source: str, db: Session) -> Optional[Lead]:
    """
    Insert a new lead or update an existing one (by external_id).

    `listing` is a loose dict; recognized keys:
      external_id, url, address, city, state, zip_code, latitude, longitude,
      property_type, asking_price, sqft, cap_rate, noi, days_on_market,
      broker_name, broker_email, broker_phone, raw

    Returns the Lead (new or updated), or None if it couldn't be saved.
    Tracks price changes in price_history and flags had_price_reduction.
    """
    external_id = listing.get("external_id")
    if not external_id:
        addr = listing.get("address") or ""
        url = listing.get("url") or ""
        if not addr and not url:
            return None
        external_id = f"{source}:{abs(hash(addr + url))}"

    price = parse_price(listing.get("asking_price"))
    cap_rate = parse_cap_rate(listing.get("cap_rate"))
    dom = parse_dom(listing.get("days_on_market"))
    sqft = parse_sqft(listing.get("sqft"))
    prop_type = normalize_property_type(listing.get("property_type"))
    address = listing.get("address") or "Unknown Address"
    city = listing.get("city") or "New York"
    state = listing.get("state") or "NY"

    existing = db.query(Lead).filter(Lead.external_id == external_id).first()

    if existing:
        # Track price drop
        if price and existing.asking_price and price < existing.asking_price:
            db.add(PriceHistory(lead=existing, price=price, source=f"{source}_rescrape"))
            existing.had_price_reduction = True
            existing.asking_price = price
        elif price and not existing.asking_price:
            existing.asking_price = price
        if dom is not None:
            existing.days_on_market = dom
        if cap_rate is not None:
            existing.cap_rate = cap_rate
        existing.last_scraped_at = datetime.utcnow()
        _rescore(existing)
        db.commit()
        return existing

    bd = score_lead(
        source=source,
        address=address, city=city, state=state,
        asking_price=price, property_type=prop_type,
        days_on_market=dom, had_price_reduction=False,
        cap_rate=cap_rate, noi=listing.get("noi"),
        broker_name=listing.get("broker_name"),
        broker_email=listing.get("broker_email"),
        broker_phone=listing.get("broker_phone"),
    )

    lead = Lead(
        source=source,
        external_id=external_id,
        address=address, city=city, state=state,
        zip_code=listing.get("zip_code"),
        latitude=listing.get("latitude"),
        longitude=listing.get("longitude"),
        property_type=prop_type,
        asking_price=price,
        sqft=sqft,
        cap_rate=cap_rate,
        noi=listing.get("noi"),
        days_on_market=dom,
        broker_name=listing.get("broker_name"),
        broker_email=listing.get("broker_email"),
        broker_phone=listing.get("broker_phone"),
        last_scraped_at=datetime.utcnow(),
        score=bd.total,
        score_breakdown=bd.to_json(),
        raw_data=json.dumps(listing.get("raw", listing), default=str)[:8000],
    )
    db.add(lead)
    if price:
        db.add(PriceHistory(lead=lead, price=price, source=source))
    db.commit()
    db.refresh(lead)
    logger.info("[%s] saved: %s (score=%d, dom=%s)", source, address, bd.total, dom)
    return lead


def _rescore(lead: Lead):
    bd = score_lead(
        source=lead.source, address=lead.address, city=lead.city, state=lead.state,
        asking_price=lead.asking_price, property_type=lead.property_type,
        days_on_market=lead.days_on_market, had_price_reduction=lead.had_price_reduction,
        cap_rate=lead.cap_rate, noi=lead.noi,
        broker_name=lead.broker_name, broker_email=lead.broker_email,
        broker_phone=lead.broker_phone,
    )
    lead.score = bd.total
    lead.score_breakdown = bd.to_json()


# ── Anti-bot Playwright context ──────────────────────────────────────────

REALISTIC_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Minimal stealth: hides navigator.webdriver and a few other automation tells.
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = { runtime: {} };
"""


def _proxy_config() -> Optional[dict]:
    """Read proxy from SCRAPER_PROXY env, e.g. http://user:pass@host:port"""
    proxy = os.environ.get("SCRAPER_PROXY", "").strip()
    if not proxy:
        return None
    return {"server": proxy}


async def build_browser_context(pw, headless: bool = True):
    """
    Launch a hardened Chromium browser + context tuned to avoid trivial
    bot detection. Returns (browser, context).
    """
    launch_kwargs = {"headless": headless, "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"]}
    proxy = _proxy_config()
    if proxy:
        launch_kwargs["proxy"] = proxy
        logger.info("Using proxy for scrape: %s", proxy["server"].split("@")[-1])

    browser = await pw.chromium.launch(**launch_kwargs)
    context = await browser.new_context(
        user_agent=REALISTIC_UA,
        viewport={"width": 1440, "height": 900},
        locale="en-US",
        timezone_id="America/New_York",
    )
    await context.add_init_script(STEALTH_JS)
    return browser, context


def headless_from_env(var: str) -> bool:
    return os.environ.get(var, "true").lower() != "false"
