"""Registration of the agent's general-purpose tools.

``init_tools`` must run before ``agent.join()``: the OpenAI Realtime plugin
snapshots the function registry in ``connect()`` when it builds the session
configuration, so anything registered later is invisible to the model.
"""

from __future__ import annotations

from . import chat, facts, get_image, web_search
from .runtime import ToolContext

__all__ = ["init_tools"]


def init_tools(llm, ctx: ToolContext) -> list[str]:
    """Register every general-purpose tool on a Realtime LLM.

    Returns the registered tool names, so the caller can log them and surface
    them in ``/health``.
    """

    @llm.register_function(name="web_search", description=web_search.WEB_SEARCH_DOC)
    async def web_search_tool(query: str, topic: str = "general") -> str:
        """Search the live web (Tavily); topic="news" for headlines."""
        return await web_search.run(ctx, query, topic)

    @llm.register_function(name="wikipedia_summary", description=facts.FACTS_DOC)
    async def wikipedia_summary_tool(topic: str) -> str:
        """Summarise a Wikipedia article."""
        return await facts.run(ctx, topic)

    @llm.register_function(name="search_images", description=get_image.IMAGE_DOC)
    async def search_images_tool(query: str, count: int = 3) -> str:
        """Find royalty-free stock photos (Pixabay)."""
        return await get_image.run(ctx, query, count)

    @llm.register_function(name="post_link", description=chat.CHAT_DOC)
    async def post_link_tool(title: str, url: str, note: str = "") -> str:
        """Post a link into the meeting chat."""
        return await chat.run(ctx, title, url, note)

    return [
        "web_search",
        "wikipedia_summary",
        "search_images",
        "post_link",
    ]
