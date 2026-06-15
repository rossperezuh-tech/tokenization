from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services.auth import verify_password, create_token, require_operator

router = APIRouter()


class LoginBody(BaseModel):
    password: str


@router.post("/login")
def login(body: LoginBody):
    if not verify_password(body.password):
        raise HTTPException(status_code=401, detail="Invalid password")
    return {"token": create_token(), "token_type": "bearer"}


@router.get("/me")
def me(_=Depends(require_operator)):
    return {"ok": True, "role": "operator"}
