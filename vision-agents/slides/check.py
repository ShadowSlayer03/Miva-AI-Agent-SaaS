"""Developer check: render a few slides to PNG without joining a call.

Run from the ``vision-agents`` folder:

    python -m slides.check
"""

import asyncio
import os
import pathlib

import httpx
from dotenv import load_dotenv

from slides.images import find_image
from slides.renderer import close_renderer, get_renderer
from slides.spec import SlideSpec

load_dotenv()

OUT = pathlib.Path(__file__).resolve().parent.parent / "slide-check"


async def image_sample() -> SlideSpec | None:
    """A photo slide, only when Pixabay is configured."""
    if not os.getenv("PIXABAY_API_KEY", "").strip():
        return None
    async with httpx.AsyncClient(timeout=10.0) as http:
        photo = await find_image(http, "geometry mathematics shapes")
    if photo is None:
        return None
    return SlideSpec(
        title="Geometry in the real world",
        kicker="a photo slide",
        bullets=["Shapes are everywhere", "Photos render beside the text"],
        image=photo.data_uri,
        credit=photo.credit,
        caption="Images are inlined, never hotlinked",
    )


SAMPLES = [
    SlideSpec(
        title="JWT authentication flow",
        kicker="request lifecycle",
        bullets=[
            "Client posts credentials once",
            "API returns a signed JWT",
            "Every later call carries that token",
        ],
        mermaid=(
            "flowchart LR\n"
            "  C[Client] -->|POST /login| A[API]\n"
            "  A --> D[(Postgres)]\n"
            "  A -.->|JWT| C"
        ),
        caption="Access tokens are stateless",
    ),
    SlideSpec(
        title="Gradient descent",
        kicker="why the learning rate matters",
        bullets=[
            "Step size decides whether we converge",
            "Too large: we overshoot the minimum",
            "Too small: training takes forever",
        ],
        latex=r"\theta_{t+1} = \theta_t - \eta \nabla_\theta \mathcal{L}(\theta_t)",
        caption="eta is the learning rate",
    ),
    SlideSpec(
        title="Debounced search",
        kicker="one small hook, three wins",
        bullets=["Fewer network calls", "No out-of-order responses", "Cheap to test"],
        code=(
            "const q = useDebounced(value, 300);\n"
            "useEffect(() => { api.search(q) }, [q]);"
        ),
        language="tsx",
    ),
    SlideSpec(
        title="Miva",
        kicker="listening",
        caption="Ask a question and I will sketch the answer",
        layout="idle",
    ),
]


async def main() -> None:
    OUT.mkdir(exist_ok=True)
    samples = list(SAMPLES)
    photo = await image_sample()
    if photo is not None:
        samples.insert(2, photo)
    renderer = await get_renderer()
    for index, spec in enumerate(samples, start=1):
        png, warnings = await renderer.render(spec.normalized())
        path = OUT / f"{index:02d}-{spec.title.lower().replace(' ', '-')}.png"
        path.write_bytes(png)
        print(f"{path.name}: {len(png)} bytes, warnings={warnings}")
    await close_renderer()


if __name__ == "__main__":
    asyncio.run(main())