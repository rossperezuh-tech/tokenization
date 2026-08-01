"""SQLAlchemy database setup and all ORM models for the Vesta tokenization pipeline."""

from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean,
    DateTime, Text, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import enum
import os

def _build_engine():
    """Postgres when DATABASE_URL is set (Railway et al), SQLite otherwise."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        db_path = os.environ.get("VESTA_DB_PATH", "vesta.db")
        return create_engine(
            f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
        )

    # Heroku/Railway hand out the legacy "postgres://" scheme, which SQLAlchemy 2
    # no longer registers. psycopg2 also wants the explicit driver name.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]

    # pool_recycle keeps us ahead of Postgres/proxy idle timeouts; pool_pre_ping
    # discards connections the platform killed between requests.
    return create_engine(url, pool_pre_ping=True, pool_recycle=300)


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class LeadSource(str, enum.Enum):
    INBOUND = "Inbound - Motivated Seller"
    OUTBOUND_LOOPNET = "Outbound - LoopNet"
    OUTBOUND_CREXI = "Outbound - Crexi"


class PipelineStage(str, enum.Enum):
    NEW_LEAD = "New Lead"
    CONTACTED = "Contacted"
    INTERESTED = "Interested"
    LOI_SIGNED = "LOI Signed"
    DUE_DILIGENCE = "Due Diligence"
    TOKEN_OFFERING = "Token Offering"
    CLOSED = "Closed"


class PropertyType(str, enum.Enum):
    MULTIFAMILY = "Multifamily"
    INDUSTRIAL = "Industrial"
    MIXED_USE = "Mixed-Use"
    RETAIL = "Retail"
    OFFICE = "Office"
    OTHER = "Other"


class OutreachStatus(str, enum.Enum):
    SENT = "sent"
    OPENED = "opened"
    REPLIED = "replied"
    BOOKED_CALL = "booked_call"


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)

    # Source tracking
    source = Column(String(60), nullable=False)
    external_id = Column(String(120), unique=True, nullable=True)  # Formspree submission ID or listing URL

    # Property details
    address = Column(String(300), nullable=False)
    city = Column(String(100))
    state = Column(String(50))
    zip_code = Column(String(20))
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    property_type = Column(String(60))
    asking_price = Column(Float, nullable=True)
    sqft = Column(Float, nullable=True)
    cap_rate = Column(Float, nullable=True)   # percentage, e.g. 6.5 means 6.5%
    noi = Column(Float, nullable=True)        # net operating income

    # Market data
    days_on_market = Column(Integer, nullable=True)
    had_price_reduction = Column(Boolean, default=False)

    # Seller / broker contact
    seller_name = Column(String(200))
    seller_email = Column(String(200))
    seller_phone = Column(String(50))
    reason_for_selling = Column(Text)

    broker_name = Column(String(200))
    broker_email = Column(String(200))
    broker_phone = Column(String(50))

    # Scoring
    score = Column(Integer, default=0)
    score_breakdown = Column(Text)  # JSON blob with per-category scores

    # Pipeline
    pipeline_stage = Column(String(60), default=PipelineStage.NEW_LEAD.value)
    in_pipeline = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_scraped_at = Column(DateTime, nullable=True)

    # Raw data blob for anything we didn't explicitly parse
    raw_data = Column(Text)

    # Relationships
    outreach_records = relationship("Outreach", back_populates="lead", cascade="all, delete-orphan")
    price_history = relationship("PriceHistory", back_populates="lead", cascade="all, delete-orphan")
    pipeline_record = relationship("Pipeline", back_populates="lead", uselist=False, cascade="all, delete-orphan")


class Outreach(Base):
    __tablename__ = "outreach"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)

    email_type = Column(String(60))   # "cold_broker" | "cold_owner" | "inbound_followup"
    recipient_email = Column(String(200))
    subject = Column(String(500))
    body = Column(Text)
    status = Column(String(40), default=OutreachStatus.SENT.value)

    sent_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    replied_at = Column(DateTime, nullable=True)
    booked_call_at = Column(DateTime, nullable=True)

    # Follow-up scheduling
    followup_7d_due = Column(DateTime, nullable=True)
    followup_14d_due = Column(DateTime, nullable=True)
    followup_7d_sent = Column(Boolean, default=False)
    followup_14d_sent = Column(Boolean, default=False)

    resend_message_id = Column(String(200))   # Resend.com message ID for tracking

    created_at = Column(DateTime, default=datetime.utcnow)
    lead = relationship("Lead", back_populates="outreach_records")


class Pipeline(Base):
    __tablename__ = "pipeline"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), unique=True, nullable=False)

    stage = Column(String(60), default=PipelineStage.NEW_LEAD.value)
    deal_value = Column(Float, nullable=True)     # our projected token raise amount
    notes = Column(Text)

    stage_entered_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lead = relationship("Lead", back_populates="pipeline_record")


class TokenOffering(Base):
    """An on-chain offering created for a pipeline deal that reached the
    Token Offering stage. Links a Lead to its deployed contracts so the
    investor app can show live offerings sourced from the Vesta pipeline."""
    __tablename__ = "token_offerings"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), unique=True, nullable=False)

    # Marketing
    name = Column(String(200))
    symbol = Column(String(20))
    summary = Column(Text)
    image_url = Column(String(500))

    # Token economics
    chain = Column(String(40), default="base")             # base | base-sepolia
    token_address = Column(String(80))
    sale_address = Column(String(80))
    distribution_vault_address = Column(String(80))
    secondary_market_address = Column(String(80))
    usdc_address = Column(String(80))

    total_tokens = Column(Float)            # whole tokens offered
    sale_tokens = Column(Float)             # tokens available to investors
    token_price_usdc = Column(Float)        # price per token in USD
    target_raise_usd = Column(Float)
    projected_yield = Column(Float)         # annual %, for display

    status = Column(String(40), default="open")  # open | funded | closed
    is_live = Column(Boolean, default=False)      # visible in investor app

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lead = relationship("Lead")


class Investor(Base):
    """An investor wallet and its KYC/accreditation status. Verification is
    performed by the licensed transfer agent; this table mirrors that status so
    the app/website can gate buying. The on-chain ComplianceRegistry remains the
    hard enforcement point."""
    __tablename__ = "investors"

    id = Column(Integer, primary_key=True, index=True)
    wallet_address = Column(String(80), unique=True, index=True, nullable=False)

    full_name = Column(String(200))
    email = Column(String(200))
    phone = Column(String(50))
    country = Column(String(80))

    # Status: pending | approved | rejected
    kyc_status = Column(String(40), default="pending")
    accredited = Column(Boolean, default=False)
    accreditation_method = Column(String(120))   # e.g. "income", "net_worth", "third_party_letter"

    transfer_agent_id = Column(String(120))       # the TA's investor reference
    lockup_until = Column(DateTime, nullable=True)
    onchain_whitelisted = Column(Boolean, default=False)

    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Document(Base):
    """Data-room document. Two scopes:
      - "offering": deal docs (PPM, operating agreement, appraisal) visible to
        investors on the offering page
      - "investor": per-investor docs (K-1s, countersigned subscription
        agreements) delivered via an unguessable download token
    """
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    offering_id = Column(Integer, ForeignKey("token_offerings.id"), nullable=True)
    investor_wallet = Column(String(80), nullable=True, index=True)

    scope = Column(String(20), default="offering")   # offering | investor
    title = Column(String(300), nullable=False)
    doc_type = Column(String(60))                    # ppm | operating_agreement | appraisal | k1 | subscription | other
    filename = Column(String(300))
    content_type = Column(String(120))
    file_path = Column(String(500))                  # on-disk path
    sha256 = Column(String(64))
    download_token = Column(String(64), unique=True, index=True)  # capability URL

    created_at = Column(DateTime, default=datetime.utcnow)


class Subscription(Base):
    """A signed subscription agreement (clickwrap e-sign). The investor signs
    the generated agreement text; we store the exact document hash they signed,
    their typed signature, and timestamps. The operator countersigns to accept."""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    offering_id = Column(Integer, ForeignKey("token_offerings.id"), nullable=False)
    wallet_address = Column(String(80), index=True, nullable=False)

    investor_name = Column(String(200))
    investor_email = Column(String(200))
    token_amount = Column(Float)
    usd_amount = Column(Float)

    agreement_sha256 = Column(String(64))    # hash of the exact text signed
    signature_name = Column(String(200))     # typed legal name
    consent = Column(Boolean, default=False)

    status = Column(String(30), default="signed")  # signed | countersigned | cancelled
    signed_at = Column(DateTime, default=datetime.utcnow)
    countersigned_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    offering = relationship("TokenOffering")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)

    price = Column(Float, nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow)
    source = Column(String(60))

    lead = relationship("Lead", back_populates="price_history")


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
