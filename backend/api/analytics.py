from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.database import Lead, Pipeline, PipelineStage, get_db

router = APIRouter()

STAGES = [s.value for s in PipelineStage]


@router.get("/")
def get_analytics(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    total_leads = db.query(func.count(Lead.id)).scalar()
    inbound_total = db.query(func.count(Lead.id)).filter(Lead.source.ilike("%Inbound%")).scalar()
    outbound_total = total_leads - inbound_total

    inbound_week = db.query(func.count(Lead.id)).filter(
        Lead.source.ilike("%Inbound%"), Lead.created_at >= week_ago
    ).scalar()
    outbound_week = db.query(func.count(Lead.id)).filter(
        Lead.source.ilike("%Outbound%"), Lead.created_at >= week_ago
    ).scalar()

    inbound_month = db.query(func.count(Lead.id)).filter(
        Lead.source.ilike("%Inbound%"), Lead.created_at >= month_ago
    ).scalar()
    outbound_month = db.query(func.count(Lead.id)).filter(
        Lead.source.ilike("%Outbound%"), Lead.created_at >= month_ago
    ).scalar()

    avg_score_inbound = db.query(func.avg(Lead.score)).filter(Lead.source.ilike("%Inbound%")).scalar()
    avg_score_outbound = db.query(func.avg(Lead.score)).filter(Lead.source.ilike("%Outbound%")).scalar()

    # Score distribution
    hot = db.query(func.count(Lead.id)).filter(Lead.score >= 80).scalar()
    warm = db.query(func.count(Lead.id)).filter(Lead.score >= 50, Lead.score < 80).scalar()
    cold = db.query(func.count(Lead.id)).filter(Lead.score < 50).scalar()

    # Pipeline stage counts + total value
    stage_data = []
    total_pipeline_value = 0.0
    for stage in STAGES:
        count = db.query(func.count(Pipeline.id)).filter(Pipeline.stage == stage).scalar()
        val = db.query(func.sum(Pipeline.deal_value)).filter(Pipeline.stage == stage).scalar() or 0.0
        total_pipeline_value += val
        stage_data.append({"stage": stage, "count": count, "value": val})

    # Property type breakdown
    prop_rows = (
        db.query(Lead.property_type, func.count(Lead.id), func.avg(Lead.score))
        .group_by(Lead.property_type)
        .all()
    )
    property_breakdown = [
        {"type": r[0] or "Unknown", "count": r[1], "avg_score": round(r[2] or 0, 1)}
        for r in prop_rows
    ]
    property_breakdown.sort(key=lambda x: x["avg_score"], reverse=True)

    # Leads over time (last 30 days, daily)
    daily_rows = (
        db.query(
            func.date(Lead.created_at).label("day"),
            func.count(Lead.id).label("count"),
        )
        .filter(Lead.created_at >= month_ago)
        .group_by(func.date(Lead.created_at))
        .order_by(func.date(Lead.created_at))
        .all()
    )
    daily_leads = [{"date": str(r.day), "count": r.count} for r in daily_rows]

    return {
        "totals": {
            "all_leads": total_leads,
            "inbound": inbound_total,
            "outbound": outbound_total,
            "in_pipeline": db.query(func.count(Lead.id)).filter(Lead.in_pipeline == True).scalar(),
        },
        "this_week": {"inbound": inbound_week, "outbound": outbound_week},
        "this_month": {"inbound": inbound_month, "outbound": outbound_month},
        "avg_score": {
            "inbound": round(avg_score_inbound or 0, 1),
            "outbound": round(avg_score_outbound or 0, 1),
        },
        "heat_distribution": {"hot": hot, "warm": warm, "cold": cold},
        "pipeline": {
            "total_value": total_pipeline_value,
            "by_stage": stage_data,
        },
        "property_breakdown": property_breakdown,
        "daily_leads": daily_leads,
    }
