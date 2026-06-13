"""
Demo script — seeds 5 sample leads (3 outbound + 2 inbound),
scores them, and prints a formatted terminal report.

Run from backend/ directory:
  python demo_leads.py
"""

import json
import os
import sys

# Make sure local modules are importable when run directly
sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("VESTA_DB_PATH", "/tmp/vesta_demo.db")

from models.database import init_db, SessionLocal, Lead, PriceHistory, LeadSource
from services.scoring import score_lead, heat_emoji, heat_label

SAMPLE_LEADS = [
    # --- OUTBOUND: LoopNet stale listings ---
    {
        "source": LeadSource.OUTBOUND_LOOPNET.value,
        "external_id": "loopnet:456123",
        "address": "182 Atlantic Ave",
        "city": "Brooklyn",
        "state": "NY",
        "zip_code": "11201",
        "property_type": "Mixed-Use",
        "asking_price": 3_250_000,
        "sqft": 4800,
        "cap_rate": 6.2,
        "noi": 201_500,
        "days_on_market": 214,
        "had_price_reduction": True,
        "broker_name": "David Kim",
        "broker_email": "dkim@nycrealty.com",
        "broker_phone": "718-555-0192",
    },
    {
        "source": LeadSource.OUTBOUND_LOOPNET.value,
        "external_id": "loopnet:789044",
        "address": "5501 Northern Blvd",
        "city": "Long Island City",
        "state": "NY",
        "zip_code": "11101",
        "property_type": "Industrial",
        "asking_price": 8_900_000,
        "sqft": 22_000,
        "cap_rate": 5.8,
        "noi": 516_200,
        "days_on_market": 412,
        "had_price_reduction": True,
        "broker_name": "Sandra Torres",
        "broker_email": "storres@lic-commercial.com",
        "broker_phone": "718-555-0341",
    },
    {
        "source": LeadSource.OUTBOUND_CREXI.value,
        "external_id": "crexi:991234",
        "address": "330 W 42nd St",
        "city": "New York",
        "state": "NY",
        "zip_code": "10036",
        "property_type": "Office",
        "asking_price": 12_500_000,
        "sqft": 18_500,
        "cap_rate": 4.1,
        "days_on_market": 97,
        "had_price_reduction": False,
        "broker_name": "Michael Chen",
        "broker_email": "mchen@midtownre.com",
        "broker_phone": "212-555-0771",
    },
    # --- INBOUND: Formspree submissions (motivated sellers) ---
    {
        "source": LeadSource.INBOUND.value,
        "external_id": "formspree:abc001",
        "address": "924 Flatbush Ave",
        "city": "Brooklyn",
        "state": "NY",
        "zip_code": "11226",
        "property_type": "Multifamily",
        "asking_price": 2_100_000,
        "seller_name": "Patricia Monroe",
        "seller_email": "pmonroe@gmail.com",
        "seller_phone": "917-555-0284",
        "reason_for_selling": "Going through a divorce and need to liquidate the property quickly",
        "days_on_market": None,
    },
    {
        "source": LeadSource.INBOUND.value,
        "external_id": "formspree:abc002",
        "address": "88 Myrtle Ave",
        "city": "Queens",
        "state": "NY",
        "zip_code": "11385",
        "property_type": "Retail",
        "asking_price": 975_000,
        "seller_name": "Frank Deluca",
        "seller_email": "fdeluca@hotmail.com",
        "seller_phone": "718-555-0619",
        "reason_for_selling": "Estate sale, inherited from father",
        "days_on_market": None,
    },
]


def seed_and_score(db):
    leads_out = []
    for data in SAMPLE_LEADS:
        existing = db.query(Lead).filter(Lead.external_id == data["external_id"]).first()
        if existing:
            db.delete(existing)
            db.commit()

        bd = score_lead(
            source=data["source"],
            address=data.get("address"),
            city=data.get("city"),
            state=data.get("state"),
            asking_price=data.get("asking_price"),
            property_type=data.get("property_type"),
            days_on_market=data.get("days_on_market"),
            had_price_reduction=data.get("had_price_reduction", False),
            reason_for_selling=data.get("reason_for_selling"),
            cap_rate=data.get("cap_rate"),
            noi=data.get("noi"),
            broker_name=data.get("broker_name"),
            broker_email=data.get("broker_email"),
            broker_phone=data.get("broker_phone"),
        )

        lead = Lead(
            source=data["source"],
            external_id=data["external_id"],
            address=data["address"],
            city=data.get("city"),
            state=data.get("state"),
            zip_code=data.get("zip_code"),
            property_type=data.get("property_type"),
            asking_price=data.get("asking_price"),
            sqft=data.get("sqft"),
            cap_rate=data.get("cap_rate"),
            noi=data.get("noi"),
            days_on_market=data.get("days_on_market"),
            had_price_reduction=data.get("had_price_reduction", False),
            seller_name=data.get("seller_name"),
            seller_email=data.get("seller_email"),
            seller_phone=data.get("seller_phone"),
            broker_name=data.get("broker_name"),
            broker_email=data.get("broker_email"),
            broker_phone=data.get("broker_phone"),
            reason_for_selling=data.get("reason_for_selling"),
            score=bd.total,
            score_breakdown=bd.to_json(),
        )
        db.add(lead)
        if data.get("asking_price"):
            db.add(PriceHistory(lead=lead, price=data["asking_price"], source=data["source"]))
        db.commit()
        db.refresh(lead)
        leads_out.append((lead, bd))
    return leads_out


def print_report(leads_with_bd):
    leads_with_bd.sort(key=lambda x: x[0].score, reverse=True)

    W = 90
    print()
    print("╔" + "═" * (W - 2) + "╗")
    print("║" + " VESTA TOKENIZATION PIPELINE — LEAD INBOX ".center(W - 2) + "║")
    print("╚" + "═" * (W - 2) + "╝")
    print()

    source_width = 30

    for rank, (lead, bd) in enumerate(leads_with_bd, 1):
        emoji = heat_emoji(lead.score)
        label = heat_label(lead.score)
        is_inbound = "Inbound" in lead.source
        source_tag = f"[{'INBOUND' if is_inbound else 'OUTBOUND'}]"
        price_str = f"${lead.asking_price:,.0f}" if lead.asking_price else "N/A"
        dom_str = f"{lead.days_on_market}d" if lead.days_on_market else "—"

        print(f"  #{rank}  {emoji} {label:<5}  Score: {lead.score:>3}/100   {source_tag:<12}  {lead.source}")
        print(f"       📍 {lead.address}, {lead.city}, {lead.state} {lead.zip_code or ''}")
        print(f"       🏢 {lead.property_type or 'Unknown'}   💰 {price_str}   ⏱  DOM: {dom_str}")

        if is_inbound and lead.seller_name:
            print(f"       👤 Seller: {lead.seller_name}  {lead.seller_phone or ''}  {lead.seller_email or ''}")
        elif lead.broker_name:
            print(f"       📞 Broker: {lead.broker_name}  {lead.broker_phone or ''}  {lead.broker_email or ''}")

        if lead.reason_for_selling:
            snippet = lead.reason_for_selling[:70] + ("…" if len(lead.reason_for_selling) > 70 else "")
            print(f"       💬 \"{snippet}\"")

        if lead.cap_rate:
            print(f"       📊 Cap Rate: {lead.cap_rate}%   NOI: ${lead.noi:,.0f}" if lead.noi else f"       📊 Cap Rate: {lead.cap_rate}%")

        # Score breakdown
        bdict = bd.to_dict()
        m = bdict["motivation"]
        t = bdict["tokenization_fit"]
        q = bdict["deal_quality"]
        print(f"       ┌─ Score Breakdown ─────────────────────────────────")
        print(f"       │  Motivation Signals : {m['subtotal']:>2}/40  "
              f"(inbound+{m['inbound_submission']} dom+{m['days_on_market']} "
              f"reduction+{m['price_reduction']} keywords+{m['motivation_keywords']})")
        print(f"       │  Tokenization Fit   : {t['subtotal']:>2}/40  "
              f"(price+{t['price']} type+{t['property_type']} "
              f"location+{t['location']} caprate+{t['cap_rate']})")
        print(f"       │  Deal Quality       : {q['subtotal']:>2}/20  "
              f"(broker+{q['broker_contact']} financials+{q['financials']} "
              f"address+{q['address']})")
        print(f"       └─ TOTAL: {lead.score}/100  {'★ RECOMMEND FOR PIPELINE' if lead.score >= 70 else ''}")
        print()

    print("─" * W)
    scores = [l.score for l, _ in leads_with_bd]
    inbound = [l for l, _ in leads_with_bd if "Inbound" in l.source]
    outbound = [l for l, _ in leads_with_bd if "Outbound" in l.source]
    print(f"  SUMMARY: {len(leads_with_bd)} leads | "
          f"Avg score: {sum(scores)/len(scores):.1f} | "
          f"Inbound: {len(inbound)} | Outbound: {len(outbound)}")
    hot = [l for l, _ in leads_with_bd if l.score >= 80]
    warm = [l for l, _ in leads_with_bd if 50 <= l.score < 80]
    cold = [l for l, _ in leads_with_bd if l.score < 50]
    print(f"  🔴 Hot (80+): {len(hot)}   🟡 Warm (50-79): {len(warm)}   🟢 Cold (<50): {len(cold)}")
    pipeline_candidates = [l for l, _ in leads_with_bd if l.score >= 70]
    total_value = sum(l.asking_price for l in pipeline_candidates if l.asking_price)
    print(f"  ★ Pipeline candidates (score ≥70): {len(pipeline_candidates)}  "
          f"| Combined ask: ${total_value:,.0f}")
    print("─" * W)
    print()


if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    try:
        leads_with_bd = seed_and_score(db)
        print_report(leads_with_bd)
    finally:
        db.close()
