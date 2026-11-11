"""post_link - share a link in the meeting chat through Stream Chat.

The meeting's chat channel is ``messaging:<meeting_id>`` (the same channel the
web app renders next to the call). Messages are sent server-side as the agent's
own user, which is exactly what the Next.js webhook already does, so the agent
does not need to be a channel member.
"""

from __future__ import annotations

import asyncio
import os

from .runtime import ToolContext, clip, fail, logger, ok

CHAT_DOC = """Post a link into the meeting's chat for everyone in the call.

Use it to share something people should keep: a source you found, an article,
a photo's page. People can open it after the call.

`title` is what the link is, `url` must start with http, `note` is an optional
one-line comment. Do not read the link out loud."""

CHANNEL_TYPE = "messaging"


class ChatPoster:
    """Server-side Stream Chat writer for one meeting channel."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        meeting_id: str,
        agent_id: str,
        agent_name: str,
    ):
        from getstream import AsyncStream

        self._stream = AsyncStream(api_key=api_key, api_secret=api_secret)
        self._channel = self._stream.chat.channel(CHANNEL_TYPE, meeting_id)
        self._agent_id = agent_id
        self._agent_name = agent_name
        self._channel_ready = False
        self._lock = asyncio.Lock()

    def _message(self, text: str):
        from getstream.models import MessageRequest, UserRequest

        return MessageRequest(
            text=text,
            user=UserRequest(id=self._agent_id, name=self._agent_name),
        )

    async def _ensure_channel(self) -> None:
        if self._channel_ready:
            return
        async with self._lock:
            if self._channel_ready:
                return
            from getstream.models import ChannelInput

            await self._channel.get_or_create(
                data=ChannelInput(created_by_id=self._agent_id)
            )
            self._channel_ready = True

    async def post(self, text: str) -> None:
        """Send a message as the agent, creating the channel if it is missing."""
        try:
            await self._channel.send_message(self._message(text))
            return
        except Exception:
            if self._channel_ready:
                raise
            logger.debug("channel missing, creating it before retrying", exc_info=True)

        await self._ensure_channel()
        await self._channel.send_message(self._message(text))

    async def aclose(self) -> None:
        try:
            await self._stream.aclose()
        except Exception:
            logger.debug("failed to close the chat client", exc_info=True)


def build_chat_poster(
    meeting_id: str, agent_id: str, agent_name: str
) -> ChatPoster | None:
    """Return a poster for this meeting, or ``None`` when chat is not configured."""
    api_key = os.getenv("STREAM_API_KEY", "").strip()
    api_secret = os.getenv("STREAM_API_SECRET", "").strip()
    if not api_key or not api_secret:
        logger.info("chat tool disabled: STREAM_API_KEY / STREAM_API_SECRET not set")
        return None
    try:
        return ChatPoster(api_key, api_secret, meeting_id, agent_id, agent_name)
    except Exception as exc:
        # A bad credential must not cost the whole meeting: the agent runs on
        # without the chat tool.
        logger.warning("chat tool disabled: %s", exc)
        logger.debug("chat client construction failed", exc_info=True)
        return None


async def run(ctx: ToolContext, title: str, url: str, note: str = "") -> str:
    if ctx.chat is None:
        return fail("posting to chat is not configured")

    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        return fail("url must start with http:// or https://")

    label = clip(title, 120) or url
    text = f"{label}\n{url}"
    if note and note.strip():
        text += f"\n{clip(note, 200)}"

    try:
        await ctx.chat.post(text)
    except Exception as exc:
        logger.warning("post_link failed: %s", exc)
        logger.debug("post_link failure detail", exc_info=True)
        return fail(f"could not post to chat ({type(exc).__name__})")

    return ok(posted=url)
