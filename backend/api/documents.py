"""
Data-room documents API.

- Operator uploads offering docs (PPM, operating agreement) or per-investor
  docs (K-1s).
- Offering docs are listed publicly for LIVE offerings.
- Per-investor docs (K-1s carry tax IDs) are listed only to that investor,
  who must be signed in with the matching wallet — or to the operator.
- Every file downloads via an unguessable capability token and is always sent
  as an attachment, never rendered inline.
"""

import hashlib
import os
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from models.database import Document, TokenOffering, get_db
from services.auth import require_operator, require_investor, assert_wallet, normalize_wallet

router = APIRouter()

DOCS_DIR = os.environ.get("VESTA_DOCS_DIR", os.path.join(os.path.dirname(__file__), "..", "uploads"))
MAX_UPLOAD_BYTES = int(os.environ.get("VESTA_MAX_UPLOAD_MB", "25")) * 1024 * 1024

# Extension -> the content type we will serve it as. Anything else is refused,
# and the browser-supplied content type is never trusted.
ALLOWED_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv",
    ".txt": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def _safe_filename(name: str) -> str:
    """Strip any path (either slash style) and reduce to a conservative charset."""
    base = re.split(r"[\\/]", name or "document")[-1]
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", base).strip(" .")
    return base[:120] or "document"


def _fmt(d: Document) -> dict:
    return {
        "id": d.id,
        "offering_id": d.offering_id,
        "scope": d.scope,
        "title": d.title,
        "doc_type": d.doc_type,
        "filename": d.filename,
        "content_type": d.content_type,
        "sha256": d.sha256,
        "download_url": f"/api/documents/download/{d.download_token}",
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@router.post("/upload", dependencies=[Depends(require_operator)])
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    scope: str = Form("offering"),
    doc_type: str = Form("other"),
    offering_id: Optional[int] = Form(None),
    investor_wallet: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    if scope not in ("offering", "investor"):
        raise HTTPException(status_code=400, detail="scope must be 'offering' or 'investor'")
    if scope == "offering" and not offering_id:
        raise HTTPException(status_code=400, detail="offering_id required for offering docs")
    if scope == "investor" and not investor_wallet:
        raise HTTPException(status_code=400, detail="investor_wallet required for investor docs")
    if offering_id and not db.query(TokenOffering).filter(TokenOffering.id == offering_id).first():
        raise HTTPException(status_code=404, detail="Offering not found")
    wallet = normalize_wallet(investor_wallet) if investor_wallet else None

    safe_name = _safe_filename(file.filename or "document")
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext or 'none'}' not allowed. Allowed: {', '.join(sorted(ALLOWED_TYPES))}",
        )

    # Read with a hard cap so an oversized upload can't exhaust memory or disk.
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large")
    if not content:
        raise HTTPException(status_code=400, detail="File is empty")

    os.makedirs(DOCS_DIR, exist_ok=True)
    token = uuid.uuid4().hex
    path = os.path.join(DOCS_DIR, f"{token}{ext}")
    with open(path, "wb") as f:
        f.write(content)

    doc = Document(
        offering_id=offering_id,
        investor_wallet=wallet,
        scope=scope,
        title=title[:300],
        doc_type=doc_type[:60],
        filename=safe_name,
        content_type=ALLOWED_TYPES[ext],
        file_path=path,
        sha256=hashlib.sha256(content).hexdigest(),
        download_token=token,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _fmt(doc)


@router.get("/offering/{offering_id}")
def list_offering_documents(offering_id: int, db: Session = Depends(get_db)):
    """Public: the data room for one LIVE offering (offering-scope docs only)."""
    offering = db.query(TokenOffering).filter(TokenOffering.id == offering_id).first()
    if not offering or not offering.is_live:
        return {"documents": []}
    docs = (
        db.query(Document)
        .filter(Document.offering_id == offering_id, Document.scope == "offering")
        .order_by(Document.created_at.desc())
        .all()
    )
    return {"documents": [_fmt(d) for d in docs]}


@router.get("/investor/{wallet_address}")
def list_investor_documents(
    wallet_address: str,
    token_wallet: str = Depends(require_investor),
    db: Session = Depends(get_db),
):
    """Per-investor docs (K-1s, countersigned agreements). Only the investor
    signed in with this wallet may list them."""
    addr = normalize_wallet(wallet_address)
    assert_wallet(token_wallet, addr)
    docs = (
        db.query(Document)
        .filter(Document.investor_wallet == addr, Document.scope == "investor")
        .order_by(Document.created_at.desc())
        .all()
    )
    return {"documents": [_fmt(d) for d in docs]}


@router.get("/admin/investor/{wallet_address}", dependencies=[Depends(require_operator)])
def admin_list_investor_documents(wallet_address: str, db: Session = Depends(get_db)):
    """Operator view of one investor's documents."""
    addr = normalize_wallet(wallet_address)
    docs = (
        db.query(Document)
        .filter(Document.investor_wallet == addr, Document.scope == "investor")
        .order_by(Document.created_at.desc())
        .all()
    )
    return {"documents": [_fmt(d) for d in docs]}


@router.get("/download/{token}")
def download_document(token: str, db: Session = Depends(get_db)):
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        raise HTTPException(status_code=404, detail="Document not found")
    doc = db.query(Document).filter(Document.download_token == token).first()
    if not doc or not doc.file_path or not os.path.isfile(doc.file_path):
        raise HTTPException(status_code=404, detail="Document not found")
    return FileResponse(
        doc.file_path,
        media_type=doc.content_type or "application/octet-stream",
        filename=doc.filename,                       # forces Content-Disposition: attachment
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )
