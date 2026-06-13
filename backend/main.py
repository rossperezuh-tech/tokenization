"""
Vesta Tokenization Pipeline — FastAPI entry point.

Run:  uvicorn main:app --reload --port 8000
"""

import asyncio
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from models.database import init_db

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
        from scrapers.loopnet import scrape_loopnet
        from scrapers.crexi import scrape_crexi
        from models.database import SessionLocal

        scheduler = AsyncIOScheduler()

        async def _run_formspree():
            db = SessionLocal()
            try:
                leads = poll_formspree(db)
                logging.getLogger(__name__).info("Formspree poll: %d new leads", len(leads))
            finally:
                db.close()

        async def _run_scrapers():
            db = SessionLocal()
            try:
                ln = await scrape_loopnet(db)
                cr = await scrape_crexi(db)
                logging.getLogger(__name__).info(
                    "Scrapers done: LoopNet=%d Crexi=%d new leads", len(ln), len(cr)
                )
            finally:
                db.close()

        # Formspree poll every hour
        scheduler.add_job(_run_formspree, IntervalTrigger(hours=1), id="formspree_poll")

        # Scrapers daily at 6am
        scheduler.add_job(_run_scrapers, CronTrigger(hour=6, minute=0), id="daily_scrape")

        scheduler.start()
        logging.getLogger(__name__).info("Scheduler started (Formspree hourly, scrapers daily 6am)")
    except ImportError:
        logging.getLogger(__name__).warning("APScheduler not installed — scheduler disabled")


@app.get("/health")
def health():
    return {"status": "ok", "service": "vesta-pipeline"}


# API routers are imported here (added in later build steps)
# from api import leads, pipeline, outreach, analytics
# app.include_router(leads.router, prefix="/api/leads")
# app.include_router(pipeline.router, prefix="/api/pipeline")
