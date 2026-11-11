"""Shared plumbing for the agent's general-purpose tools.

Every tool obeys the same contract, because tool results are injected straight
back into the realtime conversation:

* arguments are flat primitives (``str``/``int``) - ``register_function`` infers
  the JSON schema from type hints and only primitives map cleanly;
* the result is a small JSON string, never more than about 1.2 KB, so the model
  stays fast and cheap;
* a tool never raises. A failure comes back as ``{"ok": false, "error": ...}``
  and the agent keeps talking.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx

logger = logging.getLogger("miva.tools")


def ok(**fields: Any) -> str:
    """A successful tool result."""
    return json.dumps({"ok": True, **fields}, ensure_ascii=False)


def fail(message: str, **fields: Any) -> str:
    """A failed tool result the model can read and recover from."""
    return json.dumps({"ok": False, "error": message, **fields}, ensure_ascii=False)


def clip(value: Any, limit: int) -> str:
    """Collapse whitespace and cut to ``limit`` characters."""
    return " ".join(str(value or "").split())[:limit]


def clamp(value: Any, low: int, high: int, default: int) -> int:
    """Coerce a model-supplied number into ``[low, high]``."""
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


class TTLCache:
    """Tiny in-process cache.

    Search and image APIs are billed per request and rate limited, so the same
    query inside one meeting (or across meetings) must be answered from memory.
    """

    def __init__(self, ttl_seconds: float = 600.0):
        self._ttl = ttl_seconds
        self._data: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._data.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at < time.monotonic():
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._data[key] = (value, time.monotonic() + self._ttl)


@dataclass
class ToolContext:
    """Everything the tools need that belongs to one meeting.

    ``http`` is a single connection pool shared by every tool; ``chat`` is a
    server-side Stream Chat writer (``None`` when the chat credentials are not
    configured), so posting a link degrades into a friendly error instead of
    crashing the session.
    """

    meeting_id: str
    agent_id: str
    agent_name: str
    http: httpx.AsyncClient
    chat: Any = None  # tools.chat.ChatPoster | None

    async def aclose(self) -> None:
        if self.chat is not None:
            await self.chat.aclose()
        await self.http.aclose()
