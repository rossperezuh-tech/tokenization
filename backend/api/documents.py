"""
Data-room documents API.

- Operator uploads offering docs (PPM, operating agreement) or per-investor
  docs (K-1s).
- Investors list an offering's docs publicly; every file downloads via an
  unguessable capability token, so investor docs are shareable only by their
  exact link (delivered to that investor in-app).
"""

import hashlib
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from models.database import Document, TokenOffering, get_db
from services.auth import require_operator

router = APIRouter()

DOCS_DIR = os.environ.get("VESTA_DOCS_DIR", os.path.join(os.path.dirname(__file__), "..", "uploads"))


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

    os.makedirs(DOCS_DIR, exist_ok=True)
    token = uuid.uuid4().hex
    safe_name = os.path.basename(file.filename or "document")
    path = os.path.join(DOCS_DIR, f"{token}_{safe_name}")

    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)

    doc = Document(
        offering_id=offering_id,
        investor_wallet=investor_wallet.lower() if investor_wallet else None,
        scope=scope,
        title=title,
        doc_type=doc_type,
        filename=safe_name,
        content_type=file.content_type,
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
    """Public: the data room for one offering (offering-scope docs only)."""
    docs = (
        db.query(Document)
        .filter(Document.offering_id == offering_id, Document.scope == "offering")
        .order_by(Document.created_at.desc())
        .all()
    )
    return {"documents": [_fmt(d) for d in docs]}


@router.get("/investor/{wallet_address}")
def list_investor_documents(wallet_address: str, db: Session = Depends(get_db)):
    """Per-investor docs (K-1s, countersigned agreements). Listing returns
    titles + capability URLs; files themselves are only reachable via the
    unguessable token."""
    docs = (
        db.query(Document)
        .filter(Document.investor_wallet == wallet_address.lower(), Document.scope == "investor")
        .order_by(Document.created_at.desc())
        .all()
    )
    return {"documents": [_fmt(d) for d in docs]}


@router.get("/download/{token}")
def download_document(token: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.download_token == token).first()
    if not doc or not doc.file_path or not os.path.isfile(doc.file_path):
        raise HTTPException(status_code=404, detail="Document not found")
    return FileResponse(doc.file_path, media_type=doc.content_type or "application/octet-stream", filename=doc.filename)
