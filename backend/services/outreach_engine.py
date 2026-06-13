"""
Outreach email generator.

Two email types:
  - cold_broker  : for LoopNet/Crexi outbound leads with broker contact
  - cold_owner   : for outbound leads with direct seller contact
  - inbound_followup : warm response to someone who filled the form
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from models.database import Lead, Outreach, OutreachStatus, get_db

logger = logging.getLogger(__name__)


def _price_str(price: Optional[float]) -> str:
    if not price:
        return "the property"
    if price >= 1_000_000:
        return f"${price/1_000_000:.2f}M"
    return f"${price:,.0f}"


def _dom_phrase(dom: Optional[int]) -> str:
    if not dom:
        return "some time"
    if dom >= 365:
        return f"over a year ({dom} days)"
    return f"{dom} days"


def generate_cold_broker_email(lead: Lead) -> dict:
    price = _price_str(lead.asking_price)
    dom = _dom_phrase(lead.days_on_market)
    prop_type = lead.property_type or "commercial property"
    address = lead.address

    subject = f"Alternative exit for {address} — cash offer + tokenization"
    body = f"""Hi {lead.broker_name or 'there'},

I came across your listing at {address} and noticed it's been on the market for {dom}. I wanted to reach out about two liquidity options that may be worth exploring for your seller.

**Option 1 — Direct Cash Offer**
My firm acquires commercial properties off-market. We can close in 21 days, no contingencies, and we pay all closing costs. Given the {price} ask, I'd want to run quick numbers — could we get on a 15-minute call this week?

**Option 2 — Tokenization**
If your seller wants closer to full value but needs a faster close than a traditional sale, we structure real estate tokenizations through Vesta Capital. We raise capital from accredited investors, close in 45–60 days, and the seller participates in upside if they want to retain a stake.

The {prop_type} in {lead.city or 'this market'} fits our acquisition criteria well.

Would either path be worth exploring? Happy to send an offer letter within 24 hours of a quick call.

Best,
[YOUR NAME]
Vesta Capital
[YOUR PHONE]"""

    return {"subject": subject, "body": body, "email_type": "cold_broker"}


def generate_cold_owner_email(lead: Lead) -> dict:
    price = _price_str(lead.asking_price)
    dom = _dom_phrase(lead.days_on_market)
    prop_type = lead.property_type or "commercial property"
    address = lead.address

    subject = f"Your property at {address} — two cash solutions"
    body = f"""Hi there,

I noticed your {prop_type} at {address} has been listed for {dom} at {price}.

My name is [YOUR NAME] with Vesta Capital. We specialize in helping commercial property owners create liquidity when the traditional sales process stalls. We have two approaches:

1. **Fast cash purchase** — We can close in as little as 3 weeks, as-is, no realtor fees, no contingencies.

2. **Tokenized sale** — If you want closer to market value but need speed, we structure your property as a tokenized offering and bring in accredited investors. You keep equity if you want it and close in 45 days.

Both options are no-obligation. I'm happy to present a written offer within 24 hours just to see where numbers land.

Would you be open to a quick 15-minute call?

Best,
[YOUR NAME]
Vesta Capital
[YOUR PHONE]"""

    return {"subject": subject, "body": body, "email_type": "cold_owner"}


def generate_inbound_followup_email(lead: Lead) -> dict:
    price = _price_str(lead.asking_price)
    prop_type = lead.property_type or "property"
    address = lead.address
    seller = lead.seller_name or "there"
    first_name = seller.split()[0] if seller != "there" else seller

    price_line = f"We saw you're asking {price} — that's squarely in our acquisition range.\n" if lead.asking_price else ""
    reason_snippet = lead.reason_for_selling[:100] if lead.reason_for_selling else ""
    reason_line = (
        'I noticed you mentioned: "' + reason_snippet + '" — we\'ve helped many owners in similar situations.\n'
        if lead.reason_for_selling else ""
    )

    subject = f"Re: Your {prop_type} at {address} — next steps"
    body = (
        f"Hi {first_name},\n\n"
        f"Thank you for reaching out about your {prop_type} at {address}. "
        f"We received your information and I wanted to personally follow up.\n\n"
        + price_line + "\n"
        "Here's what happens next:\n\n"
        "1. **Within 24 hours** — I'll review the property details and run our internal analysis.\n"
        "2. **Written offer** — If the numbers work, I'll send you a no-obligation cash offer.\n"
        "3. **Fast close** — We can close in as little as 21 days, pay all closing costs, and purchase as-is.\n\n"
        "If you'd prefer to talk first, just reply with your best time and I'll call you directly.\n\n"
        + reason_line + "\n"
        "Looking forward to connecting.\n\n"
        "Best,\n[YOUR NAME]\nVesta Capital\n[YOUR PHONE]"
    )

    return {"subject": subject, "body": body, "email_type": "inbound_followup"}


def generate_email_for_lead(lead: Lead) -> dict:
    if "Inbound" in lead.source:
        return generate_inbound_followup_email(lead)
    if lead.broker_email or lead.broker_name:
        return generate_cold_broker_email(lead)
    return generate_cold_owner_email(lead)


def save_outreach(lead: Lead, email_data: dict, db: Session) -> Outreach:
    recipient = (
        lead.seller_email or lead.broker_email
        if email_data["email_type"] == "inbound_followup"
        else lead.broker_email or lead.seller_email
    )
    now = datetime.utcnow()
    record = Outreach(
        lead_id=lead.id,
        email_type=email_data["email_type"],
        recipient_email=recipient,
        subject=email_data["subject"],
        body=email_data["body"],
        status=OutreachStatus.SENT.value,
        sent_at=now,
        followup_7d_due=now + timedelta(days=7),
        followup_14d_due=now + timedelta(days=14),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def send_via_resend(to_email: str, subject: str, body: str, resend_message_id_ref: list) -> bool:
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        logger.warning("RESEND_API_KEY not set — skipping email send")
        return False
    try:
        import resend
        resend.api_key = api_key
        resp = resend.Emails.send({
            "from": "Vesta Capital <deals@vestacapital.com>",
            "to": to_email,
            "subject": subject,
            "text": body,
        })
        resend_message_id_ref.append(resp.get("id", ""))
        return True
    except Exception as exc:
        logger.error("Resend send failed: %s", exc)
        return False
