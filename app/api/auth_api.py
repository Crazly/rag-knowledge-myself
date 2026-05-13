"""Auth API."""
import os

from fastapi import APIRouter, Form
from fastapi.responses import RedirectResponse
from starlette.responses import Response

router = APIRouter(prefix="/login", tags=["auth"])

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "")


@router.post("")
async def login(token: str = Form(...)):
    if ACCESS_TOKEN and token == ACCESS_TOKEN:
        resp = RedirectResponse("/", status_code=302)
        resp.set_cookie(key="kb_token", value=token, httponly=True, max_age=3600 * 24 * 30)
        return resp
    return RedirectResponse("/login?error=令牌错误", status_code=302)
