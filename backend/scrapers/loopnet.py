"""
LoopNet scraper — finds NYC commercial listings with 90+ days on market.

Uses Playwright in headless mode to avoid bot detection.
Saves results via the same Lead model used by the Formspree poller.

Environment variables:
  LOOPNET_HEADLESS   — "false" to debug with a visible browser (default: true)
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from models.database import Lead, PriceHistory, LeadSource
from services.scoring import score_lead

logger = logging.getLogger(__name__)

LOOPNET_SEARCH_URL = (
    "https://www.loopnet.com/search/commercial-real-estate/new-york-ny/for-sale/"
    "?sk=5e2a1d9b4c7f3a2b1e6d8c4f&SqFt=1&ListingType=forsale&PropertyTypeId=All"
)

# Min days on market filter
MIN_DOM = 90


def _parse_price(text: str) -> Optional[float]:
    if not text:
        return None
    text = text.replace(",", "").replace("$", "").strip()
    m = re.search(r"([\d.]+)\s*([MK]?)", text, re.I)
    if not m:
        return None
    val = float(m.group(1))
    suffix = m.group(2).upper()
    if suffix == "M":
        val *= 1_000_000
    elif suffix == "K":
        val *= 1_000
    return val


def _parse_dom(text: str) -> Optional[int]:
    """Parse '127 days on market' → 127."""
    m = re.search(r"(\d+)\s*day", text, re.I)
    return int(m.group(1)) if m else None


def _parse_cap_rate(text: str) -> Optional[float]:
    m = re.search(r"([\d.]+)\s*%", text)
    return float(m.group(1)) if m else None


async def scrape_loopnet(db: Session) -> list[Lead]:
    """
    Scrape LoopNet for NYC commercial listings ≥90 DOM.
    Returns list of Lead objects saved to DB.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright not installed — run: pip install playwright && playwright install chromium")
        return []

    headless = os.environ.get("LOOPNET_HEADLESS", "true").lower() != "false"
    new_leads = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        try:
            await page.goto(LOOPNET_SEARCH_URL, timeout=30_000)
            await page.wait_for_selector(".placard-container", timeout=15_000)

            cards = await page.query_selector_all(".placard-container")
            logger.info("LoopNet: found %d listing cards", len(cards))

            for card in cards:
                try:
                    raw = {}

                    addr_el = await card.query_selector(".placard-title a, .property-address")
                    raw["address"] = (await addr_el.inner_text()).strip() if addr_el else None

                    price_el = await card.query_selector(".placard-price, .price")
                    raw["price"] = (await price_el.inner_text()).strip() if price_el else None

                    type_el = await card.query_selector(".placard-type, .property-type")
                    raw["property_type"] = (await type_el.inner_text()).strip() if type_el else None

                    dom_el = await card.query_selector("[class*='dom'], [class*='days']")
                    raw["dom"] = (await dom_el.inner_text()).strip() if dom_el else None

                    cap_el = await card.query_selector("[class*='cap']")
                    raw["cap_rate_text"] = (await cap_el.inner_text()).strip() if cap_el else None

                    link_el = await card.query_selector("a[href]")
                    raw["url"] = await link_el.get_attribute("href") if link_el else None

                    dom = _parse_dom(raw.get("dom") or "")
                    if dom is None or dom < MIN_DOM:
                        continue

                    address = raw.get("address") or "Unknown"
                    external_id = f"loopnet:{hash(address + (raw.get('url') or ''))}"

                    existing = db.query(Lead).filter(Lead.external_id == external_id).first()
                    price = _parse_price(raw.get("price") or "")
                    cap_rate = _parse_cap_rate(raw.get("cap_rate_text") or "")

                    if existing:
                        if price and existing.asking_price and price != existing.asking_price:
                            db.add(PriceHistory(lead=existing, price=price, source="loopnet_rescrape"))
                            existing.asking_price = price
                            existing.had_price_reduction = True
                        existing.days_on_market = dom
                        existing.last_scraped_at = datetime.utcnow()
                        # Re-score with updated DOM
                        bd = score_lead(
                            source=existing.source,
                            address=existing.address,
                            city=existing.city,
                            state=existing.state,
                            asking_price=existing.asking_price,
                            property_type=existing.property_type,
                            days_on_market=dom,
                            had_price_reduction=existing.had_price_reduction,
                            cap_rate=existing.cap_rate,
                            broker_name=existing.broker_name,
                            broker_email=existing.broker_email,
                        )
                        existing.score = bd.total
                        existing.score_breakdown = bd.to_json()
                        db.commit()
                        continue

                    bd = score_lead(
                        source=LeadSource.OUTBOUND_LOOPNET.value,
                        address=address,
                        city="New York",
                        state="NY",
                        asking_price=price,
                        property_type=raw.get("property_type"),
                        days_on_market=dom,
                        cap_rate=cap_rate,
                    )

                    lead = Lead(
                        source=LeadSource.OUTBOUND_LOOPNET.value,
                        external_id=external_id,
                        address=address,
                        city="New York",
                        state="NY",
                        property_type=raw.get("property_type"),
                        asking_price=price,
                        cap_rate=cap_rate,
                        days_on_market=dom,
                        last_scraped_at=datetime.utcnow(),
                        score=bd.total,
                        score_breakdown=bd.to_json(),
                        raw_data=json.dumps(raw),
                    )
                    db.add(lead)
                    if price:
                        db.add(PriceHistory(lead=lead, price=price, source="loopnet"))
                    db.commit()
                    db.refresh(lead)
                    new_leads.append(lead)
                    logger.info("LoopNet lead: %s (score=%d, dom=%d)", address, bd.total, dom)

                except Exception as exc:
                    logger.warning("Error parsing LoopNet card: %s", exc)

        except Exception as exc:
            logger.error("LoopNet scrape failed: %s", exc)
        finally:
            await browser.close()

    return new_leads
