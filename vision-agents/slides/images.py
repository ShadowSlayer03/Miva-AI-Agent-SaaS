"""Attach a real photo to a slide.

Pixabay forbids hotlinking, so nothing on the slide points at pixabay.com. The
photo is downloaded once, re-encoded into a compact JPEG and embedded in the
slide as a ``data:`` URI. The processed result is cached in memory and on disk
for 24 hours, which also satisfies Pixabay's API caching rule.

When Pixabay has no usable result (no key, quota, outage, an odd query) the
same query goes to Wikipedia's lead images, so a slide still gets a picture.

Everything here degrades quietly: no key, no network or a broken image simply
means ``find_image`` returns ``None`` and the slide renders without a picture.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from PIL import Image

from tools import pixabay, wiki_images

logger = logging.getLogger("miva.slides.images")

CACHE_TTL_SECONDS = 86400.0
CACHE_DIR = Path(__file__).resolve().parent.parent / ".slide-images"
MAX_WIDTH = 1600
MAX_HEIGHT = 1000
JPEG_QUALITY = 82

# The slide tool wraps find_image in a 7 s timeout, so each source gets a slice:
# a Pixabay that hangs must not eat the whole budget and lose the fallback.
PIXABAY_BUDGET_SECONDS = 4.0
WIKI_BUDGET_SECONDS = 2.8

# Pixabay's /get/ download host rate-limits aggressively (429) while the search
# API keeps answering 200. Once that happens, stop paying the round-trip on
# every slide and go straight to the fallback for a while.
PIXABAY_COOLDOWN_SECONDS = 900.0
_pixabay_cooldown_until = 0.0

TAVILY_BUDGET_SECONDS = 3.0


@dataclass(frozen=True)
class SlideImage:
    data_uri: str
    credit: str = ""
    page_url: str = ""


class _Cache:
    """Data-URI cache: memory for speed, disk so restarts stay free."""

    def __init__(self, root: Path = CACHE_DIR, ttl: float = CACHE_TTL_SECONDS):
        self.root, self.ttl = root, ttl
        self._memory: dict[str, tuple[SlideImage, float]] = {}

    def get(self, key: str) -> SlideImage | None:
        entry = self._memory.get(key)
        if entry is not None and entry[1] > time.monotonic():
            return entry[0]
        self._memory.pop(key, None)

        image_path = self.root / f"{key}.jpg"
        meta_path = self.root / f"{key}.json"
        try:
            if time.time() - image_path.stat().st_mtime > self.ttl:
                return None
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            raw = image_path.read_bytes()
        except (OSError, ValueError):
            return None

        image = SlideImage(
            data_uri="data:image/jpeg;base64,"
            + base64.b64encode(raw).decode("ascii"),
            credit=str(meta.get("credit", "")),
            page_url=str(meta.get("page_url", "")),
        )
        self._memory[key] = (image, time.monotonic() + self.ttl)
        return image

    def set(self, key: str, image: SlideImage, jpeg: bytes) -> SlideImage:
        self._memory[key] = (image, time.monotonic() + self.ttl)
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            (self.root / f"{key}.jpg").write_bytes(jpeg)
            (self.root / f"{key}.json").write_text(
                json.dumps(
                    {"credit": image.credit, "page_url": image.page_url},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except OSError:
            logger.debug("could not persist slide image", exc_info=True)
        return image


_CACHE = _Cache()


def _cache_key(terms: str) -> str:
    return hashlib.sha1(terms.lower().encode()).hexdigest()[:24]


def _reencode(raw: bytes) -> bytes:
    """Shrink the photo to something cheap to inline. Returns b"" on failure."""
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.mode in ("RGBA", "LA", "P") or "transparency" in source.info:
                # Logos, diagrams and Wikipedia PNGs often have transparency.
                # JPEG has no alpha, so composite onto white instead of black.
                rgba = source.convert("RGBA")
                image = Image.new("RGB", rgba.size, (255, 255, 255))
                image.paste(rgba, mask=rgba.split()[-1])
            else:
                image = source.convert("RGB")
            image.thumbnail((MAX_WIDTH, MAX_HEIGHT), Image.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            return buffer.getvalue()
    except Exception:
        logger.debug("could not re-encode slide image", exc_info=True)
        return b""


@dataclass(frozen=True)
class _Picked:
    raw: bytes
    credit: str
    page_url: str
    source: str


async def _with_budget(coro, seconds: float):
    """Await ``coro`` for at most ``seconds``; ``None`` on timeout or error."""
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except Exception:
        logger.debug("slide image source failed", exc_info=True)
        return None


async def _from_pixabay(http: httpx.AsyncClient, terms: str) -> _Picked | None:
    global _pixabay_cooldown_until

    if time.monotonic() < _pixabay_cooldown_until:
        return None

    photos = await pixabay.search(http, terms, count=1)
    if not photos:
        return None
    raw = await pixabay.download(http, photos[0].image_url)
    if not raw:
        _pixabay_cooldown_until = time.monotonic() + PIXABAY_COOLDOWN_SECONDS
        logger.info(
            "pixabay downloads unavailable, skipping them for %d s",
            int(PIXABAY_COOLDOWN_SECONDS),
        )
        return None
    return _Picked(raw, photos[0].credit, photos[0].page_url, "Pixabay")


async def _from_tavily(http: httpx.AsyncClient, terms: str) -> _Picked | None:
    """Search web images via Tavily. Fallback when Pixabay is rate-limited.

    Tavily returns contextually-relevant images from across the web, producing
    better matches than Wikipedia's single lead image. The search runs on the
    same shared connection pool (``ctx.http``) and respects the slide budget.
    """
    try:
        from tavily import AsyncTavilyClient

        client = AsyncTavilyClient(client=http)
        data = await client.search(
            terms,
            include_images=True,
            max_results=3,
            search_depth="basic",
            include_answer=False,
        )
        urls: list[str] = data.get("images") or []
        if not urls:
            return None

        response = await http.get(
            urls[0],
            timeout=8.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        raw = response.content
        if not raw:
            return None
        return _Picked(raw, f"Image search: {terms}", urls[0], "Tavily")
    except Exception:
        logger.debug("tavily image search failed", exc_info=True)
        return None


async def _from_wikipedia(http: httpx.AsyncClient, terms: str) -> _Picked | None:
    lead = await wiki_images.search(http, terms)
    if lead is None:
        return None
    try:
        response = await http.get(
            lead.image_url,
            timeout=6.0,
            follow_redirects=True,
            headers={"User-Agent": wiki_images.WIKI_USER_AGENT},
        )
        response.raise_for_status()
        raw = response.content
    except Exception as exc:
        logger.warning("wikipedia image download failed: %s", exc)
        return None
    if not raw:
        return None
    return _Picked(raw, lead.credit, lead.page_url, "Wikipedia")


async def find_image(http: httpx.AsyncClient, query: str) -> SlideImage | None:
    """Return a slide-ready photo for ``query``, or ``None``. Never raises."""
    terms = pixabay.search_terms(query)
    if not terms:
        return None

    key = _cache_key(terms)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    picked = await _with_budget(_from_pixabay(http, terms), PIXABAY_BUDGET_SECONDS)
    if picked is None:
        picked = await _with_budget(
            _from_tavily(http, terms), TAVILY_BUDGET_SECONDS
        )
    if picked is None:
        picked = await _with_budget(
            _from_wikipedia(http, terms), WIKI_BUDGET_SECONDS
        )
    if picked is None:
        return None

    jpeg = await asyncio.to_thread(_reencode, picked.raw)
    if not jpeg:
        return None

    image = SlideImage(
        data_uri="data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii"),
        credit=picked.credit,
        page_url=picked.page_url,
    )
    logger.info(
        "slide image ready: %s (%d KB, %s)", terms, len(jpeg) // 1024, picked.source
    )
    return _CACHE.set(key, image, jpeg)