from typing import Optional, List
import re

def _split(csv: str) -> List[str]:
    parts = [p.strip() for p in (csv or "").split(",")]
    return [p for p in parts if p]

def passes(text: Optional[str], include_csv: str, exclude_csv: str) -> bool:
    t = (text or "").lower()
    includes = _split(include_csv)
    excludes = _split(exclude_csv)
    if includes:
        if not any(w.lower() in t for w in includes):
            return False
    if excludes:
        if any(w.lower() in t for w in excludes):
            return False
    return True
