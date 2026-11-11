from __future__ import annotations

import asyncio
import logging
import socket
import sys
import threading

from aiohttp import web
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from .spec import SlideSpec
from .template import TEMPLATE_HTML

logger = logging.getLogger("miva.slides.render")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _browser_loop() -> asyncio.AbstractEventLoop:
    """Create the event loop that the browser runs on.

    On Windows only the Proactor loop can spawn subprocesses. uvicorn hands the
    server a Selector loop whenever it manages subprocesses itself (``--reload``
    or ``--workers``), and Playwright has to spawn Chromium, so the browser gets
    its own loop in a background thread instead of borrowing the server's.
    """
    if sys.platform == "win32":
        return asyncio.ProactorEventLoop()
    return asyncio.new_event_loop()


class SlideRenderer:
    """Warm headless Chromium that turns a SlideSpec into a 1920x1080 PNG.

    Everything Playwright touches lives on a dedicated event loop in a worker
    thread. That keeps the renderer working under any server launcher, including
    ``uvicorn --reload`` on Windows, which runs a Selector loop that cannot
    create subprocesses.
    """

    def __init__(self, width: int = 1920, height: int = 1080, timeout_s: float = 12.0):
        self.width, self.height, self.timeout_s = width, height, timeout_s
        self._lock = asyncio.Lock()
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._ctx: BrowserContext | None = None
        self._page: Page | None = None
        self._runner: web.AppRunner | None = None
        self._port: int | None = None

        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._start_error: BaseException | None = None

    # ---------- lifecycle ----------
    async def start(self) -> None:
        """Boot the browser loop and warm Chromium. Safe to call twice."""
        if self._thread is not None:
            return

        self._ready.clear()
        self._start_error = None
        self._thread = threading.Thread(
            target=self._thread_main, name="miva-slide-renderer", daemon=True
        )
        self._thread.start()

        running = asyncio.get_running_loop()
        await running.run_in_executor(None, self._ready.wait)

        if self._start_error is not None:
            thread, self._thread = self._thread, None
            thread.join(timeout=5)
            raise self._start_error

        logger.info("slide renderer ready on port %s", self._port)

    def _thread_main(self) -> None:
        loop = _browser_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            try:
                loop.run_until_complete(self._async_start())
            except BaseException as exc:  # noqa: BLE001 - re-raised in start()
                self._start_error = exc
                logger.debug("browser loop failed to start", exc_info=True)
            finally:
                self._ready.set()

            if self._start_error is None:
                loop.run_forever()
        finally:
            try:
                loop.run_until_complete(self._async_close())
            except Exception:
                logger.debug("renderer shutdown failed", exc_info=True)
            asyncio.set_event_loop(None)
            loop.close()
            self._loop = None

    async def _async_start(self) -> None:
        self._port = _free_port()
        app = web.Application()
        app.router.add_get("/", self._index)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        await web.TCPSite(self._runner, "127.0.0.1", self._port).start()

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--disable-gpu", "--font-render-hinting=none"],
        )
        self._ctx = await self._browser.new_context(
            viewport={"width": self.width, "height": self.height},
            device_scale_factor=1,
        )
        self._page = await self._ctx.new_page()
        self._page.on("console", lambda m: logger.debug("page: %s", m.text))
        await self._load_page()

    async def _index(self, _request: web.Request) -> web.Response:
        return web.Response(text=TEMPLATE_HTML, content_type="text/html")

    async def _load_page(self) -> None:
        assert self._page and self._port
        await self._page.goto(f"http://127.0.0.1:{self._port}/", wait_until="load")
        await self._page.wait_for_function(
            "window.__ready === true || !!window.__bootError", timeout=45_000
        )
        err = await self._page.evaluate("window.__bootError || null")
        if err:
            raise RuntimeError(f"slide page failed to boot: {err}")

    async def _restart_page(self) -> None:
        try:
            if self._ctx:
                await self._ctx.close()
        finally:
            assert self._browser
            self._ctx = await self._browser.new_context(
                viewport={"width": self.width, "height": self.height}, device_scale_factor=1
            )
            self._page = await self._ctx.new_page()
            await self._load_page()

    async def _async_close(self) -> None:
        self._page = None
        self._ctx = None
        for closer in (self._browser and self._browser.close,
                       self._pw and self._pw.stop,
                       self._runner and self._runner.cleanup):
            if closer:
                try:
                    await closer()
                except Exception:
                    logger.debug("cleanup step failed", exc_info=True)

    async def close(self) -> None:
        loop, thread = self._loop, self._thread
        if loop is None or thread is None:
            return
        self._thread, self._loop = None, None

        # run_forever() returns, then the worker thread tears the browser down.
        loop.call_soon_threadsafe(loop.stop)
        await asyncio.get_running_loop().run_in_executor(None, thread.join, 10)

    async def render(self, spec: SlideSpec) -> tuple[bytes, list[str]]:
        loop = self._loop
        if loop is None or not self._page:
            raise RuntimeError("SlideRenderer.start() was never called")

        # Hop onto the browser loop: Playwright objects are not thread safe.
        future = asyncio.run_coroutine_threadsafe(self._render(spec), loop)
        try:
            return await asyncio.wait_for(
                asyncio.wrap_future(future), timeout=self.timeout_s + 15
            )
        except asyncio.TimeoutError:
            future.cancel()
            raise RuntimeError("slide render timed out")

    async def _render(self, spec: SlideSpec) -> tuple[bytes, list[str]]:
        if not self._page:
            raise RuntimeError("SlideRenderer.start() was never called")
        async with self._lock:
            try:
                warnings = await asyncio.wait_for(
                    self._page.evaluate("s => window.renderSlide(s)", spec.payload()),
                    timeout=self.timeout_s,
                )
                png = await self._page.screenshot(
                    type="png", clip={"x": 0, "y": 0, "width": self.width, "height": self.height}
                )
                return png, warnings or []
            except Exception:
                logger.warning("render failed; recycling page", exc_info=True)
                await self._restart_page()
                raise


# module-level singleton: one browser for every meeting in this process
_renderer: SlideRenderer | None = None
_renderer_lock = asyncio.Lock()


def renderer_ready() -> bool:
    """True when the shared browser is up. Cheap enough for a health check."""
    r = _renderer
    return bool(r is not None and r._loop is not None and not r._loop.is_closed())


async def get_renderer() -> SlideRenderer:
    global _renderer
    async with _renderer_lock:
        if _renderer is None:
            r = SlideRenderer()
            await r.start()
            _renderer = r
        return _renderer


async def close_renderer() -> None:
    """Stop the shared browser and forget it. Used at app shutdown."""
    global _renderer
    async with _renderer_lock:
        if _renderer is not None:
            renderer, _renderer = _renderer, None
            await renderer.close()