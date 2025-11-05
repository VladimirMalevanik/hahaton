from typing import Dict, Set
from fastapi import WebSocket

class WSManager:
    def __init__(self) -> None:
        self._conns: Dict[int, Set[WebSocket]] = {}

    async def connect(self, user_id: int, ws: WebSocket):
        await ws.accept()
        self._conns.setdefault(user_id, set()).add(ws)

    def disconnect(self, user_id: int, ws: WebSocket):
        try:
            self._conns.get(user_id, set()).discard(ws)
        except Exception:
            pass

    async def broadcast(self, user_id: int, payload: dict):
        dead = []
        for ws in list(self._conns.get(user_id, set())):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._conns.get(user_id, set()).discard(ws)

ws_manager = WSManager()
