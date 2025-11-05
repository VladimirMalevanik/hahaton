from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid
from .db import get_db
from .models import User
from .telegram_client import tg_clients
import os

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.post("/start_login")
async def start_login(request: Request, phone: str = Form(...), db: AsyncSession = Depends(get_db)):
    # Create or find user
    res = await db.execute(select(User).where(User.phone == phone))
    user = res.scalars().first()
    if not user:
        user = User(phone=phone)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # Prepare a client (not started)
    from pyrogram import Client
    api_id = int(os.getenv("TELEGRAM_API_ID", "0"))
    api_hash = os.getenv("TELEGRAM_API_HASH", "")
    session_dir = os.getenv("SESSION_DIR", "./data/sessions")
    os.makedirs(session_dir, exist_ok=True)
    session_name = os.path.join(session_dir, f"user_{user.id}_login")
    app = Client(name=session_name, api_id=api_id, api_hash=api_hash, workdir=os.path.dirname(session_name))
    await app.connect()
    sent = await app.send_code(phone)
    request.session["pending_user_id"] = user.id
    request.session["login_session_name"] = session_name
    await app.disconnect()
    return RedirectResponse(url="/verify_code", status_code=303)

@router.get("/verify_code", response_class=HTMLResponse)
async def verify_code_page(request: Request):
    if not request.session.get("pending_user_id"):
        return RedirectResponse(url="/")
    return templates.TemplateResponse("verify_code.html", {"request": request})

@router.post("/finish_login")
async def finish_login(request: Request, code: str = Form(...), password: str = Form(default=""), db: AsyncSession = Depends(get_db)):
    user_id = request.session.get("pending_user_id")
    session_name = request.session.get("login_session_name")
    if not user_id or not session_name:
        return RedirectResponse(url="/")
    from pyrogram import Client
    api_id = int(os.getenv("TELEGRAM_API_ID", "0"))
    api_hash = os.getenv("TELEGRAM_API_HASH", "")
    app = Client(name=session_name, api_id=api_id, api_hash=api_hash, workdir=os.path.dirname(session_name))
    await app.connect()
    # sign in
    try:
        await app.sign_in(phone_number=None, code=code)
    except SessionPasswordNeeded:
        if not password:
            await app.disconnect()
            return RedirectResponse(url="/verify_code", status_code=303)
        await app.check_password(password=password)
    except PhoneCodeInvalid:
        await app.disconnect()
        return RedirectResponse(url="/verify_code", status_code=303)

    me = await app.get_me()
    # Move/rename session to permanent name
    from pathlib import Path
    session_dir = os.getenv("SESSION_DIR", "./data/sessions")
    perm = os.path.join(session_dir, f"user_{user_id}")
    # Pyrogram stores .session (and maybe .session-journal) — keep basename stable
    # We'll just keep folder path (workdir) and basename same
    # For simplicity, keep session_name as permanent
    await app.disconnect()

    # Persist user
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalars().first()
    user.tg_user_id = me.id
    user.first_name = me.first_name or ""
    user.last_name = me.last_name or ""
    user.session_path = session_name
    await db.commit()

    # Open long-running client with handlers
    await tg_clients.get_or_create(db, user)

    # Set logged-in session cookie
    request.session.pop("pending_user_id", None)
    request.session.pop("login_session_name", None)
    request.session["user_id"] = user.id
    return RedirectResponse(url="/dashboard", status_code=303)

@router.get("/logout")
async def logout(request: Request):
    uid = request.session.get("user_id")
    request.session.clear()
    if uid:
        await tg_clients.sign_out(uid)
    return RedirectResponse(url="/")
