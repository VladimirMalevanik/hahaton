import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles

# ↓ добавь эти две строки
from dotenv import load_dotenv
load_dotenv()

from .db import engine, Base
from .auth_routes import router as auth_router
from .chat_routes import router as chat_router


app = FastAPI(title="TG Filter Web")

# Static & templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# CORS (adjust for prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sessions (cookie)
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax")

# Routers
app.include_router(auth_router)
app.include_router(chat_router)

@app.on_event("startup")
async def on_startup():
    # Init DB
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
