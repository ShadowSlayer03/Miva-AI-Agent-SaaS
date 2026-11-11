from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field

MAX_BULLETS = 6
MAX_BULLET_CHARS = 110
MAX_MERMAID = 4000
MAX_LATEX = 2000
MAX_CODE = 3000
MAX_IMAGE = 2_000_000  # characters of data: URI (roughly 1.4 MB of JPEG)
# Miva brand green (public/logo.svg)
DEFAULT_ACCENT = "#17cf97"
LAYOUTS = ("", "idle")


def _clean(value: str | None, limit: int) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()[:limit]


@dataclass
class SlideSpec:
    title: str
    kicker: str = ""
    bullets: list[str] = field(default_factory=list)
    mermaid: str = ""
    latex: str = ""
    code: str = ""
    language: str = "text"
    caption: str = ""
    image: str = ""  # data: URI or http(s) URL of a photo drawn beside the text
    credit: str = ""
    accent: str = DEFAULT_ACCENT
    layout: str = ""  # "" = normal slide, "idle" = branded listening card

    def normalized(self) -> "SlideSpec":
        accent = self.accent if re.fullmatch(r"#[0-9a-fA-F]{6}", self.accent or "") else DEFAULT_ACCENT
        layout = self.layout if self.layout in LAYOUTS else ""

        # Only inline data: URIs and plain http(s) URLs are allowed through.
        image = (self.image or "").strip()
        if not (image.startswith("data:image/") or image.startswith(("http://", "https://"))):
            image = ""
        image = image[:MAX_IMAGE]

        return SlideSpec(
            title=_clean(self.title, 100) or "Untitled",
            kicker=_clean(self.kicker, 60),
            bullets=[_clean(b, MAX_BULLET_CHARS) for b in self.bullets if b and b.strip()][:MAX_BULLETS],
            mermaid=(self.mermaid or "").strip()[:MAX_MERMAID],
            latex=(self.latex or "").strip()[:MAX_LATEX],
            code=(self.code or "").rstrip()[:MAX_CODE],
            language=_clean(self.language, 20) or "text",
            caption=_clean(self.caption, 140),
            image=image,
            credit=_clean(self.credit, 90) if image else "",
            accent=accent,
            layout=layout,
        )

    def payload(self) -> dict:
        return asdict(self)

    def cache_key(self) -> str:
        raw = json.dumps(self.payload(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    @classmethod
    def from_tool_args(cls, **kwargs) -> "SlideSpec":
        bullets = kwargs.pop("bullets", "")
        if isinstance(bullets, str):
            # Models like to prefix lines with "-", "1." or "•"; the template
            # draws its own markers, so strip theirs.
            bullets = [
                re.sub(r"^\s*(?:[-*•·]|\d+[.)])\s+", "", line).strip()
                for line in bullets.splitlines()
                if line.strip()
            ]
        return cls(bullets=bullets, **kwargs).normalized()
