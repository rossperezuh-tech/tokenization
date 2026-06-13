"""
Alert engine:
  - Instant SMS via Twilio when inbound lead scores 70+
  - Daily 7am email digest (new leads + follow-ups due + pipeline summary)
  - Weekly Monday 8am pipeline report
  - Price-drop alerts
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.database import Lead, Outreach, Pipeline, PipelineStage, get_db

logger = logging.getLogger(__name__)


# ── SMS ────────────────────────────────────────────────────────────────

def send_sms_alert(message: str) -> bool:
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_num = os.environ.get("TWILIO_FROM_NUMBER", "")
    to_num = os.environ.get("TWILIO_TO_NUMBER", "")
    if not all([sid, token, from_num, to_num]):
        logger.warning("Twilio env vars missing — SMS skipped")
        return False
    try:
        from twilio.rest import Client
        client = Client(sid, token)
        client.messages.create(body=message, from_=from_num, to=to_num)
        logger.info("SMS sent: %s…", message[:60])
        return True
    except Exception as exc:
        logger.error("Twilio SMS failed: %s", exc)
        return False


def alert_hot_inbound(lead: Lead):
    price_str = f"${lead.asking_price/1_000_000:.2f}M" if lead.asking_price else "N/A"
    msg = (
        f"🔴 HOT INBOUND LEAD ({lead.score}/100)\n"
        f"{lead.address}, {lead.city}\n"
        f"{lead.property_type} | {price_str}\n"
        f"Seller: {lead.seller_name or 'Unknown'} {lead.seller_phone or ''}\n"
        f"Reason: {(lead.reason_for_selling or '')[:80]}"
    )
    send_sms_alert(msg)


# ── Email digest ────────────────────────────────────────────────────────

def _send_email(to: str, subject: str, body: str):
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        logger.warning("RESEND_API_KEY not set — email skipped")
        return
    try:
        import resend
        resend.api_key = api_key
        resend.Emails.send({
            "from": "Vesta Pipeline <alerts@vestacapital.com>",
            "to": to,
            "subject": subject,
            "text": body,
        })
    except Exception as exc:
        logger.error("Email alert failed: %s", exc)


def build_daily_digest(db: Session) -> str:
    now = datetime.utcnow()
    since = now - timedelta(hours=24)

    new_leads = db.query(Lead).filter(Lead.created_at >= since).order_by(Lead.score.desc()).all()
    followups_due = (
        db.query(Outreach)
        .filter(
            Outreach.followup_7d_due <= now,
            Outreach.followup_7d_sent == False,
        )
        .all()
    )
    pipeline_count = db.query(func.count(Pipeline.id)).scalar()
    pipeline_value = db.query(func.sum(Pipeline.deal_value)).scalar() or 0.0

    lines = [
        f"VESTA PIPELINE DAILY DIGEST — {now.strftime('%B %d, %Y')}",
        "=" * 50,
        "",
        f"NEW LEADS (last 24h): {len(new_leads)}",
    ]
    for l in new_leads[:10]:
        price = f"${l.asking_price/1_000_000:.2f}M" if l.asking_price else "N/A"
        lines.append(f"  [{l.score}/100] {l.address} — {l.property_type} {price} ({l.source})")
    if len(new_leads) > 10:
        lines.append(f"  … and {len(new_leads) - 10} more")

    lines += [
        "",
        f"FOLLOW-UPS DUE TODAY: {len(followups_due)}",
    ]
    for f in followups_due[:10]:
        lead = db.query(Lead).filter(Lead.id == f.lead_id).first()
        if lead:
            lines.append(f"  {lead.address} — sent {f.sent_at.strftime('%b %d') if f.sent_at else 'N/A'}")

    lines += [
        "",
        f"PIPELINE SUMMARY",
        f"  Active deals: {pipeline_count}",
        f"  Total value:  ${pipeline_value:,.0f}",
        "",
        "— Vesta Capital Pipeline System",
    ]
    return "\n".join(lines)


def send_daily_digest(db: Session):
    to = os.environ.get("ALERT_EMAIL", "")
    if not to:
        logger.warning("ALERT_EMAIL not set — digest skipped")
        return
    body = build_daily_digest(db)
    _send_email(to, f"Vesta Daily Digest — {datetime.utcnow().strftime('%b %d')}", body)
    logger.info("Daily digest sent to %s", to)


def build_weekly_report(db: Session) -> str:
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    new_leads = db.query(func.count(Lead.id)).filter(Lead.created_at >= week_ago).scalar()
    inbound = db.query(func.count(Lead.id)).filter(
        Lead.created_at >= week_ago, Lead.source.ilike("%Inbound%")
    ).scalar()
    outbound = new_leads - inbound
    pipeline_value = db.query(func.sum(Pipeline.deal_value)).scalar() or 0.0

    stage_lines = []
    for stage in PipelineStage:
        count = db.query(func.count(Pipeline.id)).filter(Pipeline.stage == stage.value).scalar()
        if count:
            stage_lines.append(f"  {stage.value}: {count}")

    lines = [
        f"VESTA WEEKLY PIPELINE REPORT — Week of {now.strftime('%B %d, %Y')}",
        "=" * 55,
        "",
        f"LEADS THIS WEEK:  {new_leads}  (Inbound: {inbound}  |  Outbound: {outbound})",
        "",
        f"PIPELINE VALUE:   ${pipeline_value:,.0f}",
        "",
        "PIPELINE BY STAGE:",
    ] + stage_lines + ["", "— Vesta Capital Pipeline System"]
    return "\n".join(lines)


def send_weekly_report(db: Session):
    to = os.environ.get("ALERT_EMAIL", "")
    if not to:
        return
    body = build_weekly_report(db)
    _send_email(to, f"Vesta Weekly Report — {datetime.utcnow().strftime('%b %d')}", body)
    logger.info("Weekly report sent to %s", to)


def check_price_drops(db: Session):
    """Alert on any leads whose asking_price dropped since last scrape."""
    from models.database import PriceHistory
    leads_with_drops = db.query(Lead).filter(Lead.had_price_reduction == True).all()
    to = os.environ.get("ALERT_EMAIL", "")
    if not to or not leads_with_drops:
        return
    lines = [f"PRICE DROP ALERT — {datetime.utcnow().strftime('%B %d, %Y')}", ""]
    for lead in leads_with_drops[:20]:
        prices = (
            db.query(PriceHistory)
            .filter(PriceHistory.lead_id == lead.id)
            .order_by(PriceHistory.recorded_at.desc())
            .limit(2)
            .all()
        )
        if len(prices) >= 2:
            drop = prices[1].price - prices[0].price
            lines.append(
                f"  {lead.address}: ${prices[1].price:,.0f} → ${prices[0].price:,.0f} "
                f"(↓${abs(drop):,.0f})"
            )
    _send_email(to, "Vesta: Price Drops Detected", "\n".join(lines))
