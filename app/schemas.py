from pydantic import BaseModel
from typing import List, Optional

class UserOut(BaseModel):
    id: int
    phone: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    class Config:
        from_attributes = True

class ChatOut(BaseModel):
    id: int
    chat_id: int
    title: str
    chat_type: str
    selected: bool
    class Config:
        from_attributes = True

class MessageOut(BaseModel):
    id: int
    tg_message_id: int
    tg_chat_id: int
    date: str
    sender_name: str
    text: str
    class Config:
        from_attributes = True

class FilterIn(BaseModel):
    include_keywords: str = ""
    exclude_keywords: str = ""

class SendMessageIn(BaseModel):
    chat_id: int
    text: str
