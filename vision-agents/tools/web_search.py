"""web_search - live web results through Tavily.

Everything that needs the outside world goes through this one tool: general
facts, prices, sports results, people, products and also breaking news. Tavily's
``topic="news"`` covers the news case, so a separate news tool is not needed.

Requires ``TAVILY_API_KEY``. One basic search costs one credit on the free plan,
so results are cached per query.
"""

from __future__ import annotations

from .runtime import TTLCache, ToolContext, clip, fail, logger, ok

WEB_SEARCH_DOC = """Search the live web for anything you are unsure about or that may have changed.

Use it for recent events, prices, sports results, product and company facts,
people, and any "look this up for me" request. This is also the tool for news
and "what happened with X lately": set `topic` to "news" for that.

`topic` is "general" (default) or "news". News results are limited to the last
week and include publication dates.

Returns a short direct answer when one is available, plus the top results as
title, url and snippet. Cite sources by name, never read a URL out loud."""

MAX_RESULTS = 4
# "basic" = 1 credit per search; "advanced" would cost 2.
SEARCH_DEPTH = "basic"
INCLUDE_ANSWER = True
TOPICS = ("general", "news")
NEWS_DAYS = 7

_CACHE = TTLCache(ttl_seconds=300.0)


async def run(ctx: ToolContext, query: str, topic: str = "general") -> str:
    query = clip(query, 300)
    if not query:
        return fail("empty search query")

    topic = (topic or "").strip().lower()
    if topic not in TOPICS:
        topic = "general"

    cache_key = f"{topic}:{query}"
    cached = _CACHE.get(cache_key)
    if cached is not None:
        return cached

    options: dict = {
        "search_depth": SEARCH_DEPTH,
        "max_results": MAX_RESULTS,
        "include_answer": INCLUDE_ANSWER,
        "timeout": 6,
    }
    if topic == "news":
        options["days"] = NEWS_DAYS

    try:
        from tavily import AsyncTavilyClient

        # Reuse the shared connection pool; the client reads TAVILY_API_KEY
        # from the environment.
        client = AsyncTavilyClient(client=ctx.http)
        data = await client.search(query, topic=topic, **options)
    except Exception as exc:
        logger.warning("web_search failed: %s", exc)
        logger.debug("web_search failure detail", exc_info=True)
        return fail(f"web search failed ({type(exc).__name__})")

    results = [
        {
            "title": clip(item.get("title"), 120),
            "url": item.get("url", ""),
            "date": clip(item.get("published_date"), 20),
            "snippet": clip(item.get("content"), 240),
        }
        for item in (data.get("results") or [])[:MAX_RESULTS]
    ]
    # Drop the empty date key on general searches to keep the payload small.
    if topic != "news":
        for item in results:
            item.pop("date", None)

    payload = ok(
        topic=topic,
        answer=clip(data.get("answer"), 500),
        results=results,
    )
    _CACHE.set(cache_key, payload)
    return payload