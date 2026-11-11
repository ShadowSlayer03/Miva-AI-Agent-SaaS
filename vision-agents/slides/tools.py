"""Realtime tools that let the voice model draw on the meeting stage.

The model never writes pixels. It calls ``show_slide`` with a short, mostly
textual description and we render it. Everything is kept to plain string
parameters on purpose: ``LLM.register_function`` infers the JSON schema from
type hints, and only primitive types map cleanly.
"""

from __future__ import annotations

import asyncio
import json
import logging

import httpx

from . import images
from .publisher import SlidePublisher
from .renderer import SlideRenderer
from .spec import SlideSpec

logger = logging.getLogger("miva.slides.tools")

IMAGE_TIMEOUT_SECONDS = 7.0

SHOW_SLIDE_DOC = """Draw a visual slide on the meeting screen so people can SEE what you explain.

You MUST call this for EVERY substantive answer. Skip only for one-word
yes/no, an explicit "no slide" request, or a clarifying question you have not
answered yet. When in doubt, draw.

Choose exactly one content field:
- image_query: a real thing that belongs on the slide as a photo. Use it for
  shapes, animals, plants, people, places, landmarks, objects, food, vehicles,
  products, sport and art. The query MUST be the exact subject — never a broader
  category. "football" not "sports", "golden retriever" not "dog",
  "eiffel tower" not "tower". 1 to 3 words, bare nouns, no "photo of",
  "diagram of", "simple" or "outline". Add 1-3 bullets with key facts.
- mermaid: systems, flows, architecture, APIs, state machines (not photos)
- latex: mathematics, formulas, derivations
- code: source code, plus `language` (e.g. python, tsx)
- bullets: only when there is nothing visible to show -> 3 to 5 lines
  separated by newlines, at most 8 words each

Content rules:
- Prefer a photo over bullets whenever the subject exists in the world.
  A picture request must never be answered with bullets or a chat link.
- If the result says "no photo found", call `show_slide` again once with a
  shorter 1-2 word query, e.g. "hexagon" instead of "hexagon shape outline".
- mermaid: valid Mermaid 12 syntax. Quote labels with spaces. At most 12
  nodes, at most 15 edges.
- latex: plain LaTeX without $$ delimiters, e.g. \\frac{a}{b} = c.
- Never read the slide out loud word for word. Explain it in your own words."""

HIDE_SLIDES_DOC = """Remove the slide and return to the agent's idle card.

Use this when the conversation moves to a new topic, when the visual is no
longer relevant, or when someone asks you to stop presenting."""


async def _attach_image(
    http: httpx.AsyncClient | None, query: str
) -> tuple[images.SlideImage | None, list[str]]:
    """Fetch a slide photo, never letting a slow API stall the conversation."""
    query = " ".join((query or "").split())
    if not query:
        return None, []
    if http is None:
        return None, ["image search is unavailable"]

    try:
        found = await asyncio.wait_for(
            images.find_image(http, query), timeout=IMAGE_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        logger.info("slide image timed out for %r", query)
        return None, ["no photo found"]
    except Exception:
        logger.debug("slide image lookup failed", exc_info=True)
        return None, ["no photo found"]

    return found, [] if found else ["no photo found, using text"]


def register_visual_tools(
    llm,
    publisher: SlidePublisher,
    renderer: SlideRenderer,
    http: httpx.AsyncClient | None = None,
) -> None:
    """Register show_slide / hide_slides on a Realtime LLM.

    Must be called before ``agent.join()`` so the tools are part of the
    initial realtime session configuration. ``http`` is the session's shared
    client, used to fetch photos for ``image_query``.
    """

    @llm.register_function(name="show_slide", description=SHOW_SLIDE_DOC)
    async def show_slide(
        title: str,
        bullets: str = "",
        mermaid: str = "",
        latex: str = "",
        code: str = "",
        language: str = "",
        caption: str = "",
        image_query: str = "",
    ) -> str:
        warnings: list[str] = []
        photo = None

        if image_query.strip():
            photo, image_warnings = await _attach_image(http, image_query)
            warnings.extend(image_warnings)

        spec = SlideSpec.from_tool_args(
            title=title,
            bullets=bullets,
            mermaid=mermaid,
            latex=latex,
            code=code,
            language=language or "text",
            caption=caption,
            image=photo.data_uri if photo else "",
            credit=photo.credit if photo else "",
        )

        if not (spec.bullets or spec.mermaid or spec.latex or spec.code or spec.image):
            return json.dumps(
                {"ok": False, "error": "nothing to draw: pass bullets or image_query"}
            )

        try:
            png, render_warnings = await renderer.render(spec)
            await publisher.show_png(png)
            await publisher.announce(active=True, title=spec.title)
            logger.info(
                "slide on screen: %s%s",
                spec.title,
                " (with photo)" if spec.image else "",
            )
            warnings.extend(render_warnings)
            if warnings:
                logger.info("slide rendered with warnings: %s", warnings)
            return json.dumps(
                {"ok": True, "shown": spec.title, "warnings": warnings[:2]}
            )
        except Exception:
            # A failed visual must never break the conversation: fall back to a
            # bullets-only slide, and if even that fails keep the idle card.
            logger.exception("slide render failed; falling back to bullets")
            fallback = SlideSpec(
                title=spec.title or "Overview",
                kicker=spec.kicker,
                bullets=spec.bullets or ["See the explanation in the conversation"],
            ).normalized()
            try:
                png, _ = await renderer.render(fallback)
                await publisher.show_png(png)
                await publisher.announce(active=True, title=fallback.title)
                logger.info("slide on screen (fallback): %s", fallback.title)
            except Exception:
                logger.exception("fallback slide failed too; keeping idle card")
            return json.dumps(
                {"ok": True, "shown": fallback.title, "simplified": True}
            )

    @llm.register_function(name="hide_slides", description=HIDE_SLIDES_DOC)
    async def hide_slides() -> str:
        await publisher.show_idle()
        logger.info("slides hidden")
        return json.dumps({"ok": True, "presenting": False})