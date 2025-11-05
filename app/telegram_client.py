import asyncio
import os
from typing import Dict, Optional, List
from pyrogram import Client, enums
from pyrogram.types import Message as PyroMessage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from .models import User, Chat, Message, FilterSetting
from .filters import passes as filter_passes
from .ws_manager import ws_manager

API_ID_ENV = "TELEGRAM_API_ID"
API_HASH_ENV = "TELEGRAM_API_HASH"
SESSION_DIR_ENV = "SESSION_DIR"

class ClientEntry:
    def __init__(self, user_id: int, client: Client):
        self.user_id = user_id
        self.client = client
        self.task: Optional[asyncio.Task] = None

class TelegramClientManager:
    def __init__(self):
        self._clients: Dict[int, ClientEntry] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, db: AsyncSession, user: User) -> Client:
        async with self._lock:
            if user.id in self._clients:
                return self._clients[user.id].client
            api_id = int(os.getenv(API_ID_ENV, "0"))
            api_hash = os.getenv(API_HASH_ENV, "")
            session_dir = os.getenv(SESSION_DIR_ENV, "./data/sessions")
            os.makedirs(session_dir, exist_ok=True)
            session_name = os.path.join(session_dir, f"user_{user.id}")
            # Use existing session_path if present
            session_path = user.session_path or session_name
            app = Client(name=session_path, api_id=api_id, api_hash=api_hash, workdir=os.path.dirname(session_path))
            entry = ClientEntry(user.id, app)
            self._clients[user.id] = entry
            await app.start()
            # ensure we saved path
            if not user.session_path:
                user.session_path = session_path
                await db.commit()
            # launch listener
            entry.task = asyncio.create_task(self._listen_loop(user.id, db))
            return app

    async def sign_out(self, user_id: int):
        async with self._lock:
            entry = self._clients.get(user_id)
            if entry:
                try:
                    await entry.client.stop()
                except Exception:
                    pass
                self._clients.pop(user_id, None)

    async def _listen_loop(self, user_id: int, db: AsyncSession):
        client = self._clients[user_id].client
        # A polling-like loop using client.get_updates is not available; we register a handler.
        # Since handlers are sync to client's own loop, we just idle.
        @client.on_message()
        async def _handler(_, msg: PyroMessage):
            # Fetch selected chats for this user
            try:
                # Refresh filter and chat selection from DB
                from sqlalchemy import select as _select
                res = await db.execute(_select(Chat).where(Chat.user_id == user_id, Chat.selected == True, Chat.chat_id == msg.chat.id))
                chat_row = res.scalars().first()
                if not chat_row:
                    return
                # Filter
                fres = await db.execute(_select(FilterSetting).where(FilterSetting.user_id == user_id))
                fset = fres.scalars().first()
                text = msg.text or msg.caption or ""
                if fset and not filter_passes(text, fset.include_keywords or "", fset.exclude_keywords or ""):
                    return
                # Store message
                m = Message(
                    user_id=user_id,
                    chat_id=chat_row.id,
                    tg_chat_id=msg.chat.id,
                    tg_message_id=msg.id,
                    date=msg.date,
                    sender_name=(msg.from_user.first_name if msg.from_user else (msg.sender_chat.title if msg.sender_chat else "Unknown")),
                    text=text,
                    raw_json=str(msg)
                )
                db.add(m)
                await db.commit()
                await db.refresh(m)
                # Push via WS
                await ws_manager.broadcast(user_id, {
                    "type": "message",
                    "id": m.id,
                    "chat_id": chat_row.id,
                    "chat_title": chat_row.title,
                    "sender": m.sender_name,
                    "text": m.text,
                    "date": m.date.isoformat() if m.date else ""
                })
            except Exception as e:
                # Best-effort; don't crash the handler
                print("handler error:", e)

        # Keep the client alive
        try:
            await client.idle()
        except Exception as e:
            print("idle error:", e)

    async def fetch_dialogs(self, client: Client):
        dialogs = []
        async for dialog in client.get_dialogs():
            if dialog.chat.type not in (enums.ChatType.BOT,):
                dialogs.append(dialog)
        return dialogs

    async def send_message(self, user_id: int, chat_id: int, text: str):
        entry = self._clients.get(user_id)
        if not entry:
            raise RuntimeError("Client not started")
        # chat_id here is Telegram chat id
        await entry.client.send_message(chat_id, text)

tg_clients = TelegramClientManager()
