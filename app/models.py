from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(32), unique=True, index=True, nullable=False)
    tg_user_id = Column(BigInteger, unique=True, index=True, nullable=True)
    first_name = Column(String(128), nullable=True)
    last_name = Column(String(128), nullable=True)
    session_path = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    chats = relationship("Chat", back_populates="user", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    filter = relationship("FilterSetting", uselist=False, back_populates="user", cascade="all, delete-orphan")

class Chat(Base):
    __tablename__ = "chats"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    chat_id = Column(BigInteger, index=True)
    title = Column(String(255))
    chat_type = Column(String(50))
    selected = Column(Boolean, default=False)

    user = relationship("User", back_populates="chats")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    tg_chat_id = Column(BigInteger, index=True)
    tg_message_id = Column(BigInteger, index=True)
    date = Column(DateTime(timezone=True))
    sender_name = Column(String(255))
    text = Column(Text)
    raw_json = Column(Text)

    user = relationship("User", back_populates="messages")
    chat = relationship("Chat", back_populates="messages")

class FilterSetting(Base):
    __tablename__ = "filter_settings"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    include_keywords = Column(Text, default="")  # comma-separated
    exclude_keywords = Column(Text, default="")

    user = relationship("User", back_populates="filter")
