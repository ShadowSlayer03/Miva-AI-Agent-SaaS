"""Shared Pixabay client.

Two consumers need it: ``search_images`` (posts a link into chat) and the
slide renderer (draws the photo on screen). Both go through this module so the
query cleaning and the 24-hour response cache exist in exactly one place.

Pixabay's terms: cache API responses for 24 hours, and never hotlink an image
URL in an application - download it instead.
"""

from __future__ import annotations

import logging
import os

import httpx

from .runtime import TTLCache, clip

logger = logging.getLogger("miva.pixabay")

PIXABAY_URL = "https://pixabay.com/api/"
CACHE_TTL_SECONDS = 86400.0
PER_PAGE = 5

_CACHE = TTLCache(ttl_seconds=CACHE_TTL_SECONDS)

# Words that describe the *slide* rather than the photo. Pixabay matches tags,
# so "simple triangle diagram drawing" throws the search off while "triangle
# geometry" finds the right pictures.
_NOISE = frozenset(
    """
    a an the of for with and on in to
    simple basic easy clear nice good real
    image images picture pictures photo photos
    diagram diagrams drawing drawings illustration illustrations
    outline sketch graphic graphics visual clip art vector
    """.split()
)


class Photo(dict):
    """A Pixabay hit. A dict so it serialises straight into a tool result."""

    @property
    def image_url(self) -> str:
        return self.get("image_url", "")

    @property
    def page_url(self) -> str:
        return self.get("page_url", "")

    @property
    def credit(self) -> str:
        return self.get("credit", "")


def search_terms(query: str) -> str:
    """Turn a model-written phrase into Pixabay-friendly keywords."""
    cleaned = "".join(ch if ch.isalnum() or ch in " -'" else " " for ch in query or "")
    words = cleaned.split()
    kept = [word for word in words if word.lower() not in _NOISE]
    return " ".join(kept or words)[:100].strip()


async def search(
    http: httpx.AsyncClient, query: str, count: int = 3
) -> list[Photo]:
    """Return up to ``count`` horizontal photos. Never raises."""
    api_key = os.getenv("PIXABAY_API_KEY", "").strip()
    if not api_key:
        logger.info("pixabay search skipped: PIXABAY_API_KEY is unset")
        return []

    terms = search_terms(query)
    if not terms:
        return []

    cached = _CACHE.get(terms)
    if cached is not None:
        return cached[:count]

    params = {
        "key": api_key,
        "q": terms,
        "lang": "en",
        "image_type": "photo",
        "orientation": "horizontal",
        "safesearch": "true",
        "min_width": 1000,
        "order": "popular",
        "per_page": PER_PAGE,
    }

    try:
        response = await http.get(PIXABAY_URL, params=params, timeout=6.0)
        if response.status_code == 429:
            logger.info("pixabay search rate limited")
            return []
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.warning("pixabay search failed: %s", exc)
        logger.debug("pixabay search failure detail", exc_info=True)
        return []

    photos = [
        Photo(
            image_url=hit.get("largeImageURL") or hit.get("webformatURL", ""),
            page_url=hit.get("pageURL", ""),
            credit=f"Photo: {clip(hit.get('user'), 60) or 'Pixabay'} / Pixabay",
        )
        for hit in (data.get("hits") or [])
        if hit.get("largeImageURL") or hit.get("webformatURL")
    ]

    # Cache the full page of hits so a later, larger request is still free.
    _CACHE.set(terms, photos)
    return photos[:count]


async def download(http: httpx.AsyncClient, url: str) -> bytes:
    """Download one photo. Returns b"" on any failure."""
    if not url:
        return b""
    try:
        response = await http.get(url, timeout=12.0, follow_redirects=True)
        response.raise_for_status()
        return response.content
    except Exception as exc:
        logger.warning("pixabay download failed: %s", exc)
        logger.debug("pixabay download failure detail", exc_info=True)
        return b""