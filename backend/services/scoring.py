"""
Unified tokenization scoring engine (1-100).

Three categories:
  - Motivation Signals  (40 pts max)
  - Tokenization Fit    (40 pts max)
  - Deal Quality        (20 pts max)
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional


NYC_METRO_KEYWORDS = {
    "new york", "nyc", "brooklyn", "queens", "bronx", "manhattan",
    "staten island", "hoboken", "jersey city", "newark", "yonkers",
    "stamford", "long island", "astoria", "flushing", "harlem",
}

MOTIVATION_KEYWORDS = {"divorce", "estate", "retiring", "retirement", "probate", "foreclosure"}


@dataclass
class ScoreBreakdown:
    # Motivation Signals (max 40)
    inbound_submission: int = 0
    days_on_market_score: int = 0
    price_reduction_score: int = 0
    motivation_keywords_score: int = 0

    # Tokenization Fit (max 40)
    price_score: int = 0
    property_type_score: int = 0
    location_score: int = 0
    cap_rate_score: int = 0

    # Deal Quality (max 20)
    broker_contact_score: int = 0
    financials_score: int = 0
    address_score: int = 0

    @property
    def motivation_total(self) -> int:
        return min(40, self.inbound_submission + self.days_on_market_score +
                   self.price_reduction_score + self.motivation_keywords_score)

    @property
    def tokenization_fit_total(self) -> int:
        return min(40, self.price_score + self.property_type_score +
                   self.location_score + self.cap_rate_score)

    @property
    def deal_quality_total(self) -> int:
        return min(20, self.broker_contact_score + self.financials_score + self.address_score)

    @property
    def total(self) -> int:
        return min(100, self.motivation_total + self.tokenization_fit_total + self.deal_quality_total)

    def to_dict(self) -> dict:
        return {
            "motivation": {
                "inbound_submission": self.inbound_submission,
                "days_on_market": self.days_on_market_score,
                "price_reduction": self.price_reduction_score,
                "motivation_keywords": self.motivation_keywords_score,
                "subtotal": self.motivation_total,
            },
            "tokenization_fit": {
                "price": self.price_score,
                "property_type": self.property_type_score,
                "location": self.location_score,
                "cap_rate": self.cap_rate_score,
                "subtotal": self.tokenization_fit_total,
            },
            "deal_quality": {
                "broker_contact": self.broker_contact_score,
                "financials": self.financials_score,
                "address": self.address_score,
                "subtotal": self.deal_quality_total,
            },
            "total": self.total,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


def score_lead(
    source: str,
    address: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    asking_price: Optional[float] = None,
    property_type: Optional[str] = None,
    days_on_market: Optional[int] = None,
    had_price_reduction: bool = False,
    reason_for_selling: Optional[str] = None,
    cap_rate: Optional[float] = None,
    noi: Optional[float] = None,
    broker_name: Optional[str] = None,
    broker_email: Optional[str] = None,
    broker_phone: Optional[str] = None,
) -> ScoreBreakdown:
    bd = ScoreBreakdown()

    # --- Motivation Signals ---
    if "Inbound" in source:
        bd.inbound_submission = 20

    if days_on_market is not None:
        if days_on_market >= 365:
            bd.days_on_market_score = 30
        elif days_on_market >= 180:
            bd.days_on_market_score = 20
        elif days_on_market >= 90:
            bd.days_on_market_score = 10

    if had_price_reduction:
        bd.price_reduction_score = 10

    reason_text = (reason_for_selling or "").lower()
    if any(kw in reason_text for kw in MOTIVATION_KEYWORDS):
        bd.motivation_keywords_score = 10

    # --- Tokenization Fit ---
    if asking_price is not None:
        if 1_000_000 <= asking_price <= 5_000_000:
            bd.price_score = 20
        elif 5_000_000 < asking_price <= 20_000_000:
            bd.price_score = 15
        elif asking_price < 1_000_000:
            bd.price_score = 5

    prop = (property_type or "").lower()
    if "multifamily" in prop or "multi-family" in prop or "multi family" in prop:
        bd.property_type_score = 20
    elif "industrial" in prop:
        bd.property_type_score = 15
    elif "mixed" in prop:
        bd.property_type_score = 15
    elif "retail" in prop:
        bd.property_type_score = 10
    elif "office" in prop:
        bd.property_type_score = 5

    location_text = " ".join(filter(None, [address, city, state])).lower()
    if any(kw in location_text for kw in NYC_METRO_KEYWORDS):
        bd.location_score = 10

    if cap_rate is not None and cap_rate >= 5.0:
        bd.cap_rate_score = 10

    # --- Deal Quality ---
    has_broker = any([broker_name, broker_email, broker_phone])
    if has_broker:
        bd.broker_contact_score = 10

    has_financials = (cap_rate is not None) or (noi is not None)
    if has_financials:
        bd.financials_score = 10

    if address and len(address.strip()) > 5:
        bd.address_score = 5

    return bd


def heat_label(score: int) -> str:
    if score >= 80:
        return "HOT"
    elif score >= 50:
        return "WARM"
    return "COLD"


def heat_emoji(score: int) -> str:
    if score >= 80:
        return "🔴"
    elif score >= 50:
        return "🟡"
    return "🟢"
