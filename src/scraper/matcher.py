from google import genai
from google.genai import types

from .images import CandidateImage, resize_image

THUMB = 256


class ImageMatcher:
    """Gemini picks which candidate image matches the source product."""

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def pick_best(
        self,
        source_photo: bytes,
        candidates: list[CandidateImage],
    ) -> int | None:
        if not candidates:
            return None

        parts: list[types.Part] = [
            types.Part.from_bytes(
                data=resize_image(source_photo, THUMB),
                mime_type="image/jpeg",
            ),
        ]
        for c in candidates:
            parts.append(
                types.Part.from_bytes(
                    data=resize_image(c.data, THUMB),
                    mime_type="image/jpeg",
                ),
            )
        parts.append(types.Part.from_text(text=self._build_prompt(len(candidates))))

        try:
            resp = await self._client.aio.models.generate_content(
                model=self._model,
                contents=parts,
            )
            text = resp.text
            if text is None:
                return None
            return self._parse_choice(text.strip(), len(candidates))
        except Exception as exc:
            print(f"❌ Matcher error: {exc}")
            return None

    @staticmethod
    def _build_prompt(n: int) -> str:
        nums = ", ".join(str(i + 2) for i in range(n))
        return (
            "Image 1 is a reference product photo from a store.\n"
            f"Images {nums} are candidates from the internet.\n"
            "Which candidate shows the SAME product as image 1?\n"
            "Consider brand, packaging, variant.\n"
            f"Reply ONLY one digit: {nums}, or 0 if none match."
        )

    @staticmethod
    def _parse_choice(text: str, n: int) -> int | None:
        for ch in text:
            if ch.isdigit():
                num = int(ch)
                if num == 0:
                    return None
                idx = num - 2
                if 0 <= idx < n:
                    return idx
        return None

