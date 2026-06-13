#!/usr/bin/env python
"""
Standalone scraper runner — run and tune the LoopNet/Crexi scrapers from the
command line on a machine that HAS internet (this is the iteration loop).

Examples:
  python run_scraper.py crexi                 # Crexi only (API-first)
  python run_scraper.py loopnet --headed      # LoopNet with a visible browser
  python run_scraper.py all --max-pages 5
  python run_scraper.py crexi --dump          # print parsed leads as JSON, don't filter

Environment (put these in backend/.env or export them):
  SCRAPER_PROXY=http://user:pass@host:port    # strongly recommended for LoopNet
  LOOPNET_SEARCH_URL=...                       # override the search URL
  CREXI_API_URL=...  CREXI_SEARCH_URL=...
  LOOPNET_MAX_PAGES / CREXI_MAX_PAGES
"""

import argparse
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

from models.database import init_db, SessionLocal
from scrapers.loopnet import scrape_loopnet
from scrapers.crexi import scrape_crexi


def _print_leads(leads, source_label):
    print(f"\n{'='*70}\n{source_label}: {len(leads)} leads saved/updated\n{'='*70}")
    for lead in sorted(leads, key=lambda l: l.score or 0, reverse=True):
        price = f"${lead.asking_price:,.0f}" if lead.asking_price else "N/A"
        print(f"  [{lead.score:>3}/100] {lead.address[:40]:<40} {lead.property_type or '?':<12} "
              f"{price:>14}  DOM:{lead.days_on_market or '?'}")
        if lead.broker_name or lead.broker_email:
            print(f"            broker: {lead.broker_name or ''} {lead.broker_email or ''} {lead.broker_phone or ''}")


async def main():
    ap = argparse.ArgumentParser(description="Run the Vesta outbound scrapers")
    ap.add_argument("source", choices=["loopnet", "crexi", "all"])
    ap.add_argument("--max-pages", type=int, help="Override max result pages")
    ap.add_argument("--headed", action="store_true", help="Show the browser (LoopNet/Crexi DOM path)")
    ap.add_argument("--dump", action="store_true", help="Print full raw_data JSON for the first 3 leads")
    args = ap.parse_args()

    if args.max_pages:
        os.environ["LOOPNET_MAX_PAGES"] = str(args.max_pages)
        os.environ["CREXI_MAX_PAGES"] = str(args.max_pages)
    if args.headed:
        os.environ["LOOPNET_HEADLESS"] = "false"
        os.environ["CREXI_HEADLESS"] = "false"

    init_db()
    db = SessionLocal()
    try:
        all_leads = []
        if args.source in ("crexi", "all"):
            leads = await scrape_crexi(db)
            _print_leads(leads, "CREXI")
            all_leads += leads
        if args.source in ("loopnet", "all"):
            leads = await scrape_loopnet(db)
            _print_leads(leads, "LOOPNET")
            all_leads += leads

        if not all_leads:
            print("\n⚠  No leads scraped. Likely causes:")
            print("   • The site blocked the request (set SCRAPER_PROXY).")
            print("   • The search URL returned 0 listings ≥90 DOM (adjust *_SEARCH_URL).")
            print("   • Selectors/field names changed — run with --dump and inspect raw_data.")
        elif args.dump:
            print("\n--- raw_data (first 3) ---")
            for lead in all_leads[:3]:
                print(json.dumps(json.loads(lead.raw_data or "{}"), indent=2, default=str)[:2000])
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
