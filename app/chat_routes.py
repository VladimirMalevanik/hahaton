from typing import List, Optional
from fastapi import APIRouter, Depends, Request, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from .db import get_db
from .models import User, Chat, Message, FilterSetting
from .schemas import ChatOut, MessageOut, FilterIn, SendMessageIn
from .telegram_client import tg_clients
from .ws_manager import ws_manager
from .filters import passes as filter_passes

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

def require_login(request: Request) -> int:
    uid = request.session.get("user_id")
    if not uid:
        raise RedirectResponse("/", status_code=303)
    return uid

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    uid = request.session.get("user_id")
    if not uid:
        return RedirectResponse("/", status_code=303)
    res = await db.execute(select(User).where(User.id == uid))
    user = res.scalars().first()
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})

@router.get("/select_chats", response_class=HTMLResponse)
async def select_chats_page(request: Request, db: AsyncSession = Depends(get_db)):
    uid = request.session.get("user_id")
    if not uid:
        return RedirectResponse("/", status_code=303)
    # Ensure client
    res = await db.execute(select(User).where(User.id == uid))
    user = res.scalars().first()
    client = await tg_clients.get_or_create(db, user)
    # Fetch dialogs
    dialogs = await tg_clients.fetch_dialogs(client)
    # Upsert chats into DB
    from sqlalchemy import select as _select
    res2 = await db.execute(_select(Chat).where(Chat.user_id == uid))
    existing = {c.chat_id: c for c in res2.scalars().all()}
    for d in dialogs:
        cid = d.chat.id
        title = d.chat.title or (d.chat.first_name or "")
        ctype = str(d.chat.type)
        if cid in existing:
            row = existing[cid]
            row.title = title
            row.chat_type = ctype
        else:
            db.add(Chat(user_id=uid, chat_id=cid, title=title, chat_type=ctype, selected=False))
    await db.commit()
    res3 = await db.execute(_select(Chat).where(Chat.user_id == uid))
    chats = res3.scalars().all()
    return templates.TemplateResponse("select_chats.html", {"request": request, "chats": chats})

@router.post("/select_chats")
async def save_selected_chats(request: Request, db: AsyncSession = Depends(get_db)):
    uid = request.session.get("user_id")
    if not uid:
        return RedirectResponse("/", status_code=303)
    form = await request.form()
    selected_ids = set(int(v) for k, v in form.items() if k.startswith("chat_"))
    # Reset all to False
    await db.execute(update(Chat).where(Chat.user_id == uid).values(selected=False))
    if selected_ids:
        await db.execute(update(Chat).where(Chat.user_id == uid, Chat.id.in_(selected_ids)).values(selected=True))
    await db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)

@router.get("/feed", response_class=HTMLResponse)
async def feed(request: Request, db: AsyncSession = Depends(get_db)):
    uid = request.session.get("user_id")
    if not uid:
        return RedirectResponse("/", status_code=303)
    # Grab recent messages
    from sqlalchemy import select as _select
    res = await db.execute(_select(Message).where(Message.user_id == uid).order_by(Message.id.desc()).limit(100))
    msgs = list(reversed(res.scalars().all()))
    return templates.TemplateResponse("feed.html", {"request": request, "messages": msgs})

@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    # Expect cookie-based session user_id in query ?user_id=
    params = dict(websocket.query_params)
    uid = int(params.get("user_id", "0"))
    await ws_manager.connect(uid, websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep alive / ignore
    except WebSocketDisconnect:
        ws_manager.disconnect(uid, websocket)

@router.post("/api/send_message")
async def api_send_message(request: Request, chat_id: int = Form(...), text: str = Form(...), db: AsyncSession = Depends(get_db)):
    uid = request.session.get("user_id")
    if not uid:
        return RedirectResponse("/", status_code=303)
    # Resolve Chat row to tg_chat_id
    from sqlalchemy import select as _select
    res = await db.execute(_select(Chat).where(Chat.id == chat_id, Chat.user_id == uid))
    chat = res.scalars().first()
    if not chat:
        return JSONResponse({"ok": False, "error": "chat not found"}, status_code=400)
    await tg_clients.send_message(uid, chat.chat_id, text)
    return RedirectResponse(url="/feed", status_code=303)

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: AsyncSession = Depends(get_db)):
    uid = request.session.get("user_id")
    if not uid:
        return RedirectResponse("/", status_code=303)
    from sqlalchemy import select as _select
    res = await db.execute(_select(FilterSetting).where(FilterSetting.user_id == uid))
    f = res.scalars().first()
    if not f:
        f = FilterSetting(user_id=uid, include_keywords="", exclude_keywords="")
        db.add(f)
        await db.commit()
        await db.refresh(f)
    return templates.TemplateResponse("settings.html", {"request": request, "f": f})

@router.post("/settings")
async def save_settings(request: Request, include_keywords: str = Form(default=""), exclude_keywords: str = Form(default=""), db: AsyncSession = Depends(get_db)):
    uid = request.session.get("user_id")
    if not uid:
        return RedirectResponse("/", status_code=303)
    from sqlalchemy import select as _select
    res = await db.execute(_select(FilterSetting).where(FilterSetting.user_id == uid))
    f = res.scalars().first()
    if not f:
        from .models import FilterSetting as FS
        f = FS(user_id=uid, include_keywords=include_keywords, exclude_keywords=exclude_keywords)
        db.add(f)
    else:
        f.include_keywords = include_keywords
        f.exclude_keywords = exclude_keywords
    await db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)
