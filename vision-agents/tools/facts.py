"""wikipedia_summary - background facts from Wikipedia via ``Wikipedia-API``.

The async client is used directly so the meeting's event loop is never blocked.
Wikipedia wants a descriptive User-Agent, so one is sent on every request.
"""

from __future__ import annotations

from .runtime import TTLCache, ToolContext, clip, fail, logger, ok

FACTS_DOC = """Look up a short factual summary on Wikipedia.

Use it for people, teams, places, organisations, historical events, sports
rules and general "what is X" questions. Prefer it over guessing; it is fast
and free.

Returns the article title, a short summary and the link."""

WIKI_USER_AGENT = "MivaAI-MeetingAgent/1.0 (meeting assistant; contact: support@miva.ai)"
WIKI_LANGUAGE = "en"
SUMMARY_CHARS = 1100

_wiki = None
_CACHE = TTLCache(ttl_seconds=3600.0)


def _client():
    """One shared Wikipedia client for the whole process."""
    global _wiki
    if _wiki is None:
        import wikipediaapi

        _wiki = wikipediaapi.AsyncWikipedia(
            user_agent=WIKI_USER_AGENT,
            language=WIKI_LANGUAGE,
            timeout=8.0,
        )
    return _wiki


async def run(ctx: ToolContext, topic: str) -> str:
    topic = clip(topic, 300)
    if not topic:
        return fail("empty topic")

    cached = _CACHE.get(topic)
    if cached is not None:
        return cached

    try:
        page = _client().page(topic)
        if not await page.exists():
            payload = fail(f"no wikipedia article found for {topic!r}")
        else:
            payload = ok(
                title=page.title,
                url=await page.fullurl,
                summary=clip(await page.summary, SUMMARY_CHARS),
            )
    except Exception as exc:
        logger.warning("wikipedia_summary failed: %s", exc)
        logger.debug("wikipedia_summary failure detail", exc_info=True)
        return fail(f"wikipedia lookup failed ({type(exc).__name__})")

    _CACHE.set(topic, payload)
    return payload
