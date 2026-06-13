from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from models.database import Lead, Outreach, get_db
from services.outreach_engine import (
    generate_email_for_lead,
    save_outreach,
    send_via_resend,
)

router = APIRouter()


@router.get("/generate/{lead_id}")
def generate_email(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    email_data = generate_email_for_lead(lead)
    recipient = lead.seller_email or lead.broker_email or ""
    return {**email_data, "recipient": recipient, "lead_id": lead_id}


@router.post("/send/{lead_id}")
def send_email(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    email_data = generate_email_for_lead(lead)
    recipient = lead.seller_email or lead.broker_email
    if not recipient:
        raise HTTPException(status_code=400, detail="No recipient email on this lead")

    record = save_outreach(lead, email_data, db)
    msg_id_ref: list = []
    sent = send_via_resend(recipient, email_data["subject"], email_data["body"], msg_id_ref)

    if sent and msg_id_ref:
        record.resend_message_id = msg_id_ref[0]
        db.commit()

    return {
        "ok": True,
        "sent": sent,
        "outreach_id": record.id,
        "recipient": recipient,
        "subject": email_data["subject"],
    }


@router.get("/history/{lead_id}")
def outreach_history(lead_id: int, db: Session = Depends(get_db)):
    records = (
        db.query(Outreach)
        .filter(Outreach.lead_id == lead_id)
        .order_by(Outreach.sent_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "email_type": r.email_type,
            "recipient_email": r.recipient_email,
            "subject": r.subject,
            "status": r.status,
            "sent_at": r.sent_at.isoformat() if r.sent_at else None,
        }
        for r in records
    ]
