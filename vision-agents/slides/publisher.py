from __future__ import annotations

import io
import logging

import av
from PIL import Image, ImageDraw, ImageFont
from vision_agents.core.processors import VideoPublisher
from vision_agents.core.utils.video_track import QueuedVideoTrack

logger = logging.getLogger("miva.slides.publish")


def _font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


class SlidePublisher(VideoPublisher):
    """Holds the agent's outbound video track and swaps slides into it."""

    name = "slide_publisher"

    def __init__(
        self,
        agent_name: str = "Miva",
        width: int = 1280,
        height: int = 720,
        fps: int = 8,
    ):
        super().__init__()  # Processor.__init__ sets self.metrics
        self.agent_name = agent_name
        self.width, self.height, self.fps = width, height, fps
        # max_queue_size=1 => newest frame wins, no playback backlog
        self._track = QueuedVideoTrack(width, height, fps=fps, max_queue_size=1)
        self._idle_png: bytes | None = None
        self._agent: object | None = None

    def attach_agent(self, agent: object) -> None:
        """Called by the Agent during construction; used to emit UI events."""
        self._agent = agent

    def publish_video_track(self) -> av.VideoStreamTrack:
        return self._track

    async def show_png(self, png: bytes) -> None:
        image = Image.open(io.BytesIO(png)).convert("RGB").resize(
            (self.width, self.height), Image.LANCZOS
        )
        await self._track.add_frame(av.VideoFrame.from_image(image))

    async def show_idle(self) -> None:
        if self._idle_png is None:
            self._idle_png = self._make_idle(self.agent_name)
        await self.show_png(self._idle_png)
        await self.announce(active=False)

    async def set_idle_png(self, png: bytes) -> None:
        """Use a rendered idle card instead of the Pillow fallback."""
        self._idle_png = png

    async def announce(self, active: bool, title: str = "") -> None:
        """Tell the UI which slide is on screen (5KB limit, so metadata only)."""
        if self._agent is None:
            return
        try:
            await self._agent.send_custom_event(  # type: ignore[attr-defined]
                {"type": "slide", "active": active, "title": title}
            )
        except Exception:
            logger.debug("failed to send slide custom event", exc_info=True)

    async def close(self) -> None:
        self._track.stop()

    # ---------- idle card fallback (no browser needed) ----------
    def _make_idle(self, agent_name: str) -> bytes:
        """Approximation of the branded idle slide, used only if rendering fails."""
        w, h = self.width, self.height
        bg, surface, accent = (10, 14, 13), (18, 25, 23), (23, 207, 151)
        img = Image.new("RGB", (w, h), bg)
        draw = ImageDraw.Draw(img)
        for y in range(h):  # subtle vertical lift towards the middle
            t = 1 - abs((y / h) - 0.5) * 2
            draw.line(
                [(0, y), (w, y)],
                fill=tuple(int(b + (s - b) * t * 0.8) for b, s in zip(bg, surface)),
            )
        draw.ellipse([w // 2 - 96, h // 2 - 190, w // 2 + 96, h // 2 + 2], fill=(19, 32, 28))
        draw.ellipse(
            [w // 2 - 26, h // 2 - 120, w // 2 + 26, h // 2 - 68], outline=accent, width=6
        )
        draw.text((w // 2, h // 2 + 60), agent_name, font=_font(56),
                  fill=(234, 242, 239), anchor="mm")
        draw.text((w // 2, h // 2 + 132), "Listening", font=_font(30),
                  fill=accent, anchor="mm")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
