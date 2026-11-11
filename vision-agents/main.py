import asyncio
import logging
import os
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from slides import (
    SlidePublisher,
    SlideSpec,
    close_renderer,
    get_renderer,
    register_visual_tools,
    renderer_ready,
)
from tools import ToolContext, build_chat_poster, init_tools
from vision_agents.core import Agent, User
from vision_agents.core.utils.audio_filter import AudioFilter
from vision_agents.plugins import getstream, openai

load_dotenv()
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("miva.agent")

for _noisy in ("httpx", "httpcore", "wikipediaapi", "tavily"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

AGENT_BUILD = "tools+slides-images+tavily-news-2026-11-01"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Start the slide renderer once for the whole process.

    One headless Chromium is shared by every meeting this worker handles. If it
    cannot start (Chromium not installed, no network for the JS libs), the
    server still boots and the agent simply runs without visuals.
    """
    logger.info("Miva agent build %s starting", AGENT_BUILD)
    try:
        await get_renderer()
        logger.info("Slide renderer warmed up")
    except Exception:
        logger.exception(
            "Slide renderer unavailable - agents will run without visuals"
        )
    yield
    try:
        await close_renderer()
    except Exception:
        logger.debug("failed to stop the slide renderer", exc_info=True)


app = FastAPI(
    title="Miva AI Vision Agent Runner", debug=True, lifespan=lifespan
)

IDLE_TIMEOUT_SECONDS = float(os.getenv("AGENT_IDLE_TIMEOUT_SECONDS", "30"))
IDLE_POLL_SECONDS = 5.0


class PassThroughAudioFilter(AudioFilter):
    """Let every participant's audio reach the realtime model.

    vision-agents 0.6.9 builds a FirstSpeakerWinsFilter by default, but that
    filter needs Silero VAD warmup which the direct ``Agent(...)`` path never
    performs (only ``AgentLauncher`` does). The first time a second
    participant's audio reaches the consumer it raises
    ``RuntimeError: warmup() must be called before process_audio()``, and the
    generic handler in ``_consume_incoming_audio`` then ends the loop - so the
    agent stays in the call but goes permanently deaf.

    Forwarding every participant's audio is also the right behaviour here:
    OpenAI Realtime runs its own turn detection, and the agent's instructions
    already tell it to answer only when addressed by name.
    """

    async def process_audio(self, pcm, participant):
        return pcm

    def clear(self, participant=None):
        return None


class StartAgentRequest(BaseModel):
    meeting_id: str
    agent_id: str
    agent_name: str
    instructions: str
    voice: str = "alloy"


# meeting_id -> asyncio.Task, so duplicate webhook deliveries do not make
# two agents join the same call.
_sessions: dict[str, asyncio.Task] = {}

# meeting_id -> what happened to the visuals for that session. Surfaced by
# /health so "why is there no video track?" is answerable without log diving.
_session_visuals: dict[str, dict] = {}


def build_instructions(agent_name: str, base_instructions: str) -> str:
    return f"""
You are {agent_name}, an AI voice assistant inside a live multi-participant meeting.

## Strict domain restriction — you MUST obey this
Your expertise and purpose are defined below. Respond ONLY to questions within
this scope. When someone asks anything outside it, say:

"I'm {agent_name}, and I'm specifically here to help with questions related to
my area of expertise. I can't assist with that — sorry!"

Do not make exceptions. Do not stretch your domain to accommodate a question.
Do not answer out-of-domain questions even if you know the answer. If you are
unsure whether a question falls within your domain, ask yourself: "Was I
created for this?" If the answer is no, refuse.

Your domain / purpose:
{base_instructions}

## Participation rules
You only participate when you are directly addressed. Specifically:
- Listen to the entire conversation and do not respond to statements that are
  not directed at you.
- Speak only when someone calls you by your name ({agent_name}) or explicitly
  asks for your opinion, answer, or help.
- Never interrupt people, never answer on someone else's behalf, and never
  comment on side conversations.
- When you do speak, ground your answer in the conversation so far, use earlier
  context to stay coherent, and answer concisely.
- If a request is ambiguous, ask a short clarifying question before answering.

## Visuals — ALWAYS draw a slide
You MUST call `show_slide` for EVERY substantive answer you give. The only
times you may skip it:
- A one-word or single-sentence yes / no reply.
- Someone explicitly says "don't show a slide", "no visual", "without a slide"
  or something clearly telling you to skip the visual.
- A clarifying question where you have not answered yet.

For everything else — explanations, facts, comparisons, steps, lists, diagrams,
code, formulas — call `show_slide` FIRST, then speak. The slide must appear
before or alongside your spoken answer, never after it.

Choosing the content format:
- If the subject exists in the real world and you would point at it → photo
  (`image_query` plus 1-3 bullets). This covers shapes, animals, plants, people,
  places, landmarks, buildings, objects, tools, food, vehicles, products, sport
  and art. Do not skip the photo — people want to see the thing while you talk.
- Systems, flows, architecture, APIs, data models → `mermaid`.
- Mathematics, formulas, derivations → `latex`.
- Source code → `code` plus `language` (e.g. python, tsx).
- Nothing visual to show → `bullets`: 3 to 5 short lines, at most 8 words each.

## Image accuracy — never show the wrong picture
When you use `image_query`, the query MUST be the EXACT subject you are talking
about — not a broader category or a related but different thing. Examples:
- Discussing football tactics → `image_query` "football", NOT "sports" or "hockey"
- Discussing golden retrievers → `image_query` "golden retriever", NOT "dog"
- Discussing Eiffel Tower history → `image_query` "eiffel tower", NOT "tower"
- Discussing the actor → `image_query` the person's full name, NOT just the movie

Be specific. Pick the most precise, unambiguous term. If the slide result says
"no photo found", retry ONCE with a shorter version (1-2 words).

`image_query` is subject words only, 1 to 3 words: "hexagon", "golden retriever",
"eiffel tower". Never include "photo of", "image of", "diagram of", "drawing of",
"simple" or "outline" — those words break the search.

## Looking things up
You have research tools:
- `web_search` — live web results (Tavily). Use it for anything recent, changing
  or that you are unsure about: prices, scores, people, companies, products. For
  news and headlines set `topic` to "news".
- `wikipedia_summary` — background on a person, team, place, event or rule.
- `search_images` — finds photos and returns links for the meeting chat.

Rules for look-ups:
- Look it up instead of guessing. There is no separate news tool: everything,
  including the latest news, goes through `web_search` (Tavily). Use
  `topic="news"` for anything that happened recently.
- Prefer `wikipedia_summary` for background on a person or thing, and
  `web_search` for anything that may have changed since you were trained.
- After a look-up, draw the slide from what you found: put the real names,
  dates and numbers on it, and set `caption` to the source ("Wikipedia",
  "the Guardian"). A look-up that ends without a slide is wasted.
- Say what you are doing in one short sentence before you look it up.
- Cite sources by name ("according to Wikipedia", "the Guardian reports"), never
  by reading a URL out loud. Post useful links with `post_link` instead.
- If a tool returns an error, never mention the tool or the error. Answer from
  what you know and keep the conversation flowing.

## Slide rules
- One idea per slide. Never read the slide out loud line by line; explain it.
- Call `hide_slides` when the topic moves on or the visual stops being relevant.
- If `show_slide` fails, keep talking. Never mention tools, slides or errors.
- `mermaid`: valid Mermaid 12 syntax. Quote labels that contain spaces. Keep it
  small: at most 12 nodes, at most 15 edges.
- `latex`: plain LaTeX without $$ delimiters, e.g. \\frac{{a}}{{b}} = c.
- `code` slide: include the language name so syntax highlighting works.
""".strip()


def build_realtime_llm(voice: str) -> "openai.Realtime":
    kwargs: dict = {"voice": voice}

    model = os.getenv("OPENAI_REALTIME_MODEL", "").strip()
    if model:
        kwargs["model"] = model

    # The previous Node bridge was audio-only. Keep that behaviour unless
    # VISION_AGENT_SEND_VIDEO is explicitly enabled.
    if os.getenv("VISION_AGENT_SEND_VIDEO", "false").lower() not in {
        "1",
        "true",
        "yes",
    }:
        kwargs["send_video"] = False

    return openai.Realtime(**kwargs)


async def leave_when_alone(agent: Agent, meeting_id: str) -> None:
    """Leave the call once the agent has been the only participant for a while.

    Stream only ends a call when its last participant leaves. Without this the
    agent keeps the call alive after the human leaves, so `call.session_ended`
    never fires and the meeting stays "active" in the database forever.
    """
    while not agent.closed:
        await asyncio.sleep(IDLE_POLL_SECONDS)
        idle_for = agent.idle_for()
        if idle_for >= IDLE_TIMEOUT_SECONDS:
            logger.info(
                "Agent alone for %.0fs in meeting %s; leaving call",
                idle_for,
                meeting_id,
            )
            await agent.close()
            return


async def show_branded_idle(renderer, publisher: SlidePublisher, agent_name: str) -> None:
    """Render the branded 'listening' card, then show it.

    Falls back to the Pillow card if the browser cannot render it, so the agent
    always has something on screen instead of a blank track.
    """
    try:
        spec = SlideSpec(
            title=agent_name,
            kicker="listening",
            caption="Ask a question and I will sketch the answer",
            layout="idle",
        ).normalized()
        png, _ = await renderer.render(spec)
        await publisher.set_idle_png(png)
    except Exception:
        logger.exception("Could not render the idle card, using the fallback")
    try:
        await publisher.show_idle()
    except Exception:
        logger.exception("Could not put the idle card on the video track")


async def run_agent_session(req: StartAgentRequest) -> None:
    """Create the agent, join the Stream call and keep it alive until the call ends."""
    logger.info(
        "Starting agent %s (%s) in meeting %s [multi-speaker: pass-through]",
        req.agent_name,
        req.agent_id,
        req.meeting_id,
    )

    llm = build_realtime_llm(req.voice)
    processors: list = []
    state: dict = {"visuals": "starting", "tools": []}
    _session_visuals[req.meeting_id] = state

    ctx = ToolContext(
        meeting_id=req.meeting_id,
        agent_id=req.agent_id,
        agent_name=req.agent_name,
        http=httpx.AsyncClient(timeout=10.0),
        chat=build_chat_poster(req.meeting_id, req.agent_id, req.agent_name),
    )
    try:
        state["tools"] = init_tools(llm, ctx)
        logger.info(
            "Agent tools for meeting %s: %s", req.meeting_id, state["tools"]
        )
    except Exception as exc:
        state["tools_error"] = f"{type(exc).__name__}: {exc}"
        logger.exception("Tool registration failed for meeting %s", req.meeting_id)

    # Visuals are optional. If Chromium is unavailable we still run a normal
    # voice agent instead of failing the meeting.
    try:
        renderer = await get_renderer()
        publisher = SlidePublisher(agent_name=req.agent_name)
        register_visual_tools(llm, publisher, renderer, http=ctx.http)
        processors.append(publisher)
        state["visuals"] = "enabled"
        logger.info("Visuals enabled for meeting %s", req.meeting_id)
        await show_branded_idle(renderer, publisher, req.agent_name)
    except Exception as exc:
        state["visuals"] = "disabled"
        state["error"] = f"{type(exc).__name__}: {exc}"
        logger.exception("Visuals disabled for meeting %s", req.meeting_id)
        processors.clear()

    agent = Agent(
        edge=getstream.Edge(),
        agent_user=User(id=req.agent_id, name=req.agent_name),
        instructions=build_instructions(req.agent_name, req.instructions),
        llm=llm,
        processors=processors,
        multi_speaker_filter=PassThroughAudioFilter(),
    )

    state["publish_video"] = agent.publish_video
    state["video_track"] = (
        type(agent._video_track).__name__ if agent._video_track else "none"
    )
    logger.info(
        "Agent for meeting %s: visuals=%s, video track=%s",
        req.meeting_id,
        state["visuals"],
        state["video_track"],
    )

    try:
        call = await agent.create_call("default", req.meeting_id)
        async with agent.join(call):
            logger.info("Agent joined meeting %s", req.meeting_id)

            finish_task = asyncio.create_task(
                agent.finish(), name=f"finish-{req.meeting_id}"
            )
            idle_task = asyncio.create_task(
                leave_when_alone(agent, req.meeting_id),
                name=f"idle-{req.meeting_id}",
            )

            try:
                await asyncio.wait(
                    {finish_task, idle_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
            finally:
                for task in (finish_task, idle_task):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(
                    finish_task, idle_task, return_exceptions=True
                )

            logger.info("Agent finished meeting %s", req.meeting_id)
    except asyncio.CancelledError:
        logger.info("Agent session cancelled for meeting %s", req.meeting_id)
        raise
    except Exception:
        logger.exception("Agent session failed for meeting %s", req.meeting_id)
    finally:
        _sessions.pop(req.meeting_id, None)
        try:
            await ctx.aclose()
        except Exception:
            logger.debug("failed to close tool context", exc_info=True)
        logger.info("Agent session closed for meeting %s", req.meeting_id)


@app.post("/agent/start")
async def start_agent(req: StartAgentRequest):
    existing = _sessions.get(req.meeting_id)
    if existing and not existing.done():
        logger.info("Agent already running for meeting %s", req.meeting_id)
        return {"status": "already_running", "meeting_id": req.meeting_id}

    # Run detached from the HTTP request: the webhook must return within ms.
    _sessions[req.meeting_id] = asyncio.create_task(run_agent_session(req))
    return {"status": "starting", "meeting_id": req.meeting_id}


@app.delete("/agent/{meeting_id}")
async def stop_agent(meeting_id: str):
    task = _sessions.get(meeting_id)
    if not task or task.done():
        return {"status": "not_running", "meeting_id": meeting_id}

    task.cancel()
    return {"status": "cancelling", "meeting_id": meeting_id}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "build": AGENT_BUILD,
        "renderer_ready": renderer_ready(),
        "sessions": _session_visuals,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "true").lower() == "true",
    )
