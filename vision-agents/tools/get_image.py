"""search_images - photo links for the meeting chat.

Pixabay is the primary source; if it has nothing (no key, quota, outage) the
query falls back to Wikipedia's lead image, so the agent can still post a link.

This tool finds a *link*: the human-readable page, which is what the agent posts
into the meeting chat. Drawing the photo on a slide is a separate path
(``show_slide`` with ``image_query``) because Pixabay forbids hotlinking, so the
slide renderer downloads the bytes and embeds them.
"""

from __future__ import annotations

from . import pixabay, wiki_images
from .runtime import ToolContext, clamp, clip, fail, ok

IMAGE_DOC = """Find a royalty-free stock photo for a topic and get a link to it.

Use it when someone wants a link to keep or share, then post the returned
`page_url` with `post_link`. For a photo that should appear ON the slide itself,
call `show_slide` with `image_query` instead - that draws the picture directly.

`count` is how many photos to return, 1 to 5 (default 3)."""

MAX_PHOTOS = 5
DEFAULT_PHOTOS = 3


async def run(ctx: ToolContext, query: str, count: int = DEFAULT_PHOTOS) -> str:
    query = clip(query, 100)
    if not query:
        return fail("empty image query")

    count = clamp(count, 1, MAX_PHOTOS, DEFAULT_PHOTOS)

    # Primary: Pixabay (high-quality, royalty-free stock photos)
    photos = await pixabay.search(ctx.http, query, count)
    if photos:
        return ok(query=query, results=photos)

    # Fallback 1: Tavily web image search (better context match than Wikipedia)
    try:
        from tavily import AsyncTavilyClient
        client = AsyncTavilyClient(client=ctx.http)
        data = await client.search(query, include_images=True, max_results=count)
        urls: list[str] = data.get("images") or []
        if urls:
            return ok(query=query, results=[
                {"image_url": url, "page_url": "", "credit": f"Web image: {query}"}
                for url in urls[:count]
            ])
    except Exception:
        pass

    # Fallback 2: Wikipedia lead image
    lead = await wiki_images.search(ctx.http, query)
    if lead is None:
        return fail("no photos found for that query")

    return ok(
        query=query,
        results=[
            {
                "image_url": lead.image_url,
                "page_url": lead.page_url,
                "credit": lead.credit,
            }
        ],
    )