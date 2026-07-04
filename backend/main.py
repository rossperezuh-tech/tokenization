"""Vesta Tokenization Pipeline — FastAPI entry point.

Run:  uvicorn main:app --reload --port 8000
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

from models.database import init_db
from api import leads, pipeline, outreach, analytics, offerings, investors, auth, documents, subscriptions
from services.auth import require_operator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(title="Vesta Tokenization Pipeline", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public: operator login + investor-facing catalogue / KYC (protected per-endpoint inside)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(offerings.router, prefix="/api/offerings", tags=["offerings"])
app.include_router(investors.router, prefix="/api/investors", tags=["investors"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["subscriptions"])

# Operator-only: entire routers gated behind a valid operator token
_op = [Depends(require_operator)]
app.include_router(leads.router, prefix="/api/leads", tags=["leads"], dependencies=_op)
app.include_router(pipeline.router, prefix="/api/pipeline", tags=["pipeline"], dependencies=_op)
app.include_router(outreach.router, prefix="/api/outreach", tags=["outreach"], dependencies=_op)
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"], dependencies=_op)

# Serve built React frontend
_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="static")


@app.on_event("startup")
async def startup():
    init_db()
    _start_scheduler()


def _start_scheduler():
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger
        from services.formspree_poller import poll_formspree
        from services.alerts import send_daily_digest, send_weekly_report, check_price_drops
        from scrapers.loopnet import scrape_loopnet
        from scrapers.crexi import scrape_crexi
        from models.database import SessionLocal

        scheduler = AsyncIOScheduler()

        async def _run_formspree():
            db = SessionLocal()
            try:
                leads_found = poll_formspree(db)
                # SMS alert for hot inbound leads
                from services.alerts import alert_hot_inbound
                for lead in leads_found:
                    if "Inbound" in lead.source and lead.score >= 70:
                        alert_hot_inbound(lead)
            finally:
                db.close()

        async def _run_scrapers():
            db = SessionLocal()
            try:
                await scrape_loopnet(db)
                await scrape_crexi(db)
                check_price_drops(db)
            finally:
                db.close()

        async def _daily_digest():
            db = SessionLocal()
            try:
                send_daily_digest(db)
            finally:
                db.close()

        async def _weekly_report():
            db = SessionLocal()
            try:
                send_weekly_report(db)
            finally:
                db.close()

        scheduler.add_job(_run_formspree, IntervalTrigger(hours=1), id="formspree_poll")
        scheduler.add_job(_run_scrapers, CronTrigger(hour=6, minute=0), id="daily_scrape")
        scheduler.add_job(_daily_digest, CronTrigger(hour=7, minute=0), id="daily_digest")
        scheduler.add_job(_weekly_report, CronTrigger(day_of_week="mon", hour=8, minute=0), id="weekly_report")

        scheduler.start()
        logging.getLogger(__name__).info("Scheduler started")
    except ImportError as exc:
        logging.getLogger(__name__).warning("APScheduler not installed — scheduler disabled: %s", exc)


@app.get("/health")
def health():
    return {"status": "ok", "service": "vesta-pipeline"}
