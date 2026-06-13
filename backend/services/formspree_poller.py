"""
Formspree API poller — fetches new form submissions from the CRE buyer site
and upserts them into the leads table.

Environment variables required:
  FORMSPREE_FORM_ID   — form hash from your Formspree URL
  FORMSPREE_API_KEY   — Formspree API key (account → API keys)
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from models.database import Lead, PriceHistory, LeadSource
from services.scoring import score_lead

logger = logging.getLogger(__name__)

FORMSPREE_API_BASE = "https://formspree.io/api/0"

# Flexible field name mapping — Formspree field names vary by form config
FIELD_MAP = {
    "seller_name":       ["name", "seller_name", "your_name", "full_name"],
    "seller_email":      ["email", "_replyto", "seller_email", "your_email"],
    "seller_phone":      ["phone", "phone_number", "seller_phone", "mobile"],
    "address":           ["address", "property_address", "prop_address", "location"],
    "asking_price":      ["price", "asking_price", "list_price", "asking price"],
    "property_type":     ["type", "property_type", "prop_type", "property type"],
    "reason_for_selling":["reason", "reason_for_selling", "why_selling", "message", "notes"],
}


def _extract_field(submission: dict, field_key: str) -> Optional[str]:
    """Try multiple possible Formspree field name variants."""
    data = submission.get("data", submission)  # Formspree wraps fields in "data"
    for candidate in FIELD_MAP.get(field_key, [field_key]):
        for key, value in data.items():
            if key.lower().replace("-", "_").replace(" ", "_") == candidate.replace("-", "_"):
                return str(value).strip() if value else None
    return None


def _parse_price(raw: Optional[str]) -> Optional[float]:
    if not raw:
        return None
    cleaned = re.sub(r"[^\d.]", "", raw.replace(",", ""))
    try:
        val = float(cleaned)
        # If someone typed "2.5" meaning $2.5M, normalise
        if val < 10_000 and val > 0:
            val *= 1_000_000
        return val
    except ValueError:
        return None


def fetch_submissions(form_id: str, api_key: str, after: Optional[str] = None) -> list[dict]:
    """
    Fetch form submissions from Formspree.
    `after` is an ISO timestamp — only return submissions newer than this.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{FORMSPREE_API_BASE}/forms/{form_id}/submissions"
    params = {"page_size": 100}
    if after:
        params["after"] = after

    try:
        resp = httpx.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("submissions", [])
    except httpx.HTTPStatusError as exc:
        logger.error("Formspree API error %s: %s", exc.response.status_code, exc.response.text)
        return []
    except Exception as exc:
        logger.error("Formspree fetch failed: %s", exc)
        return []


def upsert_inbound_lead(submission: dict, db: Session) -> Optional[Lead]:
    """Parse a Formspree submission and upsert into the leads table."""
    submission_id = submission.get("id") or submission.get("submissionId")
    if not submission_id:
        return None

    external_id = f"formspree:{submission_id}"

    existing = db.query(Lead).filter(Lead.external_id == external_id).first()
    if existing:
        return existing  # already processed

    address = _extract_field(submission, "address") or "Unknown Address"

    bd = score_lead(
        source=LeadSource.INBOUND.value,
        address=address,
        asking_price=_parse_price(_extract_field(submission, "asking_price")),
        property_type=_extract_field(submission, "property_type"),
        reason_for_selling=_extract_field(submission, "reason_for_selling"),
    )

    lead = Lead(
        source=LeadSource.INBOUND.value,
        external_id=external_id,
        address=address,
        seller_name=_extract_field(submission, "seller_name"),
        seller_email=_extract_field(submission, "seller_email"),
        seller_phone=_extract_field(submission, "seller_phone"),
        asking_price=_parse_price(_extract_field(submission, "asking_price")),
        property_type=_extract_field(submission, "property_type"),
        reason_for_selling=_extract_field(submission, "reason_for_selling"),
        score=bd.total,
        score_breakdown=bd.to_json(),
        raw_data=json.dumps(submission),
    )
    db.add(lead)

    if lead.asking_price:
        db.add(PriceHistory(lead=lead, price=lead.asking_price, source="formspree"))

    db.commit()
    db.refresh(lead)
    logger.info("Inbound lead saved: %s (score=%d)", address, bd.total)
    return lead


def poll_formspree(db: Session, after: Optional[str] = None) -> list[Lead]:
    """
    Main entry point for the hourly poll.
    Returns list of newly created Lead objects.
    """
    form_id = os.environ.get("FORMSPREE_FORM_ID", "")
    api_key = os.environ.get("FORMSPREE_API_KEY", "")
    if not form_id or not api_key:
        logger.warning("FORMSPREE_FORM_ID / FORMSPREE_API_KEY not set — skipping poll")
        return []

    submissions = fetch_submissions(form_id, api_key, after=after)
    new_leads = []
    for sub in submissions:
        lead = upsert_inbound_lead(sub, db)
        if lead:
            new_leads.append(lead)
    return new_leads
