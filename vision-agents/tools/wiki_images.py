"""Lead images from Wikipedia - the free fallback when Pixabay has nothing.

The MediaWiki API needs no key, and articles about people, places, landmarks,
animals and shapes already carry a lead image, which makes this the natural
second choice for a slide photo.

Only the rendered ``thumbnail`` is used, never the ``original``: originals are
often SVG (or huge TIFF), while the thumbnail is always a raster JPEG/PNG that
Pillow can read and re-encode.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from .runtime import clip

logger = logging.getLogger("miva.wiki_images")

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_USER_AGENT = "MivaAI-MeetingAgent/1.0 (meeting assistant; contact: support@miva.ai)"
THUMB_SIZE = 1280
MIN_WIDTH = 420
TIMEOUT_SECONDS = 3.5


@dataclass(frozen=True)
class LeadImage:
    image_url: str
    page_url: str
    credit: str
    title: str = ""


async def search(http: httpx.AsyncClient, query: str) -> LeadImage | None:
    """Return the best lead image for ``query``, or ``None``. Never raises."""
    terms = clip(" ".join((query or "").split()), 100)
    if not terms:
        return None

    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "generator": "search",
        "gsrsearch": terms,
        "gsrnamespace": "0",
        "gsrlimit": "5",
        "prop": "pageimages",
        "piprop": "thumbnail",
        "pithumbsize": str(THUMB_SIZE),
        "redirects": "1",
    }

    try:
        response = await http.get(
            WIKI_API,
            params=params,
            headers={"User-Agent": WIKI_USER_AGENT, "Accept": "application/json"},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        pages = (response.json().get("query") or {}).get("pages") or []
    except Exception as exc:
        logger.warning("wikipedia image search failed: %s", exc)
        logger.debug("wikipedia image search detail", exc_info=True)
        return None

    # ``index`` keeps the search engine's relevance order.
    candidates = sorted(
        (page for page in pages if _usable(page)),
        key=lambda page: page.get("index", 0),
    )
    if not candidates:
        return None

    page = candidates[0]
    title = str(page.get("title", "")).strip()
    thumb = page.get("thumbnail") or {}

    return LeadImage(
        image_url=str(thumb.get("source", "")),
        page_url="https://en.wikipedia.org/wiki/"
        + quote(title.replace(" ", "_"), safe=""),
        credit=f"Image: {clip(title, 60) or 'Wikipedia'} / Wikipedia",
        title=title,
    )


def _usable(page: dict) -> bool:
    """A thumbnail we can actually put on a slide."""
    thumb = page.get("thumbnail") or {}
    source = str(thumb.get("source", ""))
    if not source.startswith("https://"):
        return False
    if source.lower().endswith(".svg"):
        return False
    return int(thumb.get("width") or 0) >= MIN_WIDTH