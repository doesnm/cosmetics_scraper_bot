import json

from google import genai
from google.genai import types

from .images import resize_image

ANALYZE_MAX_PX = 1024

PROMPT = """\
You are a cosmetics product analyst.

The photo is from a Telegram cosmetics store. It may show a product and a price tag.

RULES:
1. PRICE:
   - Extract from the photo or caption FIRST.
   - If price is NOT visible, search Google for the retail price.
   - ALWAYS convert the final price to KZT (Kazakhstani Tenge).
   - "currency" MUST always be "KZT".
   - Set "price_source" to "photo", "caption", or "google".
2. Use Google Search to identify the product: full name, brand, ingredients,
   skin type, rating, etc.

Return ONLY valid JSON — no markdown, no commentary:
{
  "name": "full product name in English",
  "brand": "brand name",
  "category": "skincare | makeup | fragrance | haircare | bodycare | other",
  "price": 5070,
  "currency": "KZT",
  "price_source": "photo | caption | google",
  "gender": "unisex | female | male",
  "rating": 4.5,
  "description": "one-sentence description in English",
  "attributes": {
    "skin_type": ["oily", "dry", "normal", "combination", "sensitive"],
    "skin_concerns": ["moisturising", "acne", "anti_aging", "brightening"],
    "formulation": "cream | gel | lotion | serum | oil | foam | toner",
    "key_ingredients": ["niacinamide", "hyaluronic_acid"],
    "volume": "125 ml"
  },
  "post_ru": {
    "product_type": "пенка для умывания",
    "target_audience": "универсально",
    "purpose": "очищение кожи, удаление загрязнений",
    "skin_type": "для всех типов кожи",
    "application_area": "лицо",
    "volume": "125 мл"
  }
}

CRITICAL: currency MUST be "KZT". Convert if needed.
The "post_ru" block MUST be in Russian.
"""

MARKUP = 1.30


class GeminiAnalyzer:
    """Single Gemini call: product analysis via Google Search grounding."""

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def analyze(
        self,
        image_bytes: bytes,
        caption: str | None = None,
    ) -> dict | None:
        prompt = PROMPT
        if caption:
            prompt += f"\nPost caption: {caption}"

        resized = resize_image(image_bytes, ANALYZE_MAX_PX)

        try:
            resp = await self._client.aio.models.generate_content(
                model=self._model,
                contents=[
                    types.Part.from_bytes(data=resized, mime_type="image/jpeg"),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                ),
            )
            data = self._parse_json(resp.text)
            if data:
                self._ensure_kzt(data)
                self._apply_markup(data)
                self._log_price_source(data)
            return data
        except Exception as exc:
            print(f"❌ Gemini error: {exc}")
            return None

    @staticmethod
    def _ensure_kzt(data: dict) -> None:
        data["currency"] = "KZT"

    @staticmethod
    def _apply_markup(data: dict) -> None:
        price = data.get("price")
        if price is not None:
            try:
                data["price"] = round(float(price) * MARKUP)
            except (ValueError, TypeError):
                pass

    @staticmethod
    def _parse_json(text: str | None) -> dict | None:
        if not text:
            return None
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            print(f"❌ JSON parse failed: {text[:200]}...")
            return None

    @staticmethod
    def _log_price_source(data: dict) -> None:
        source = data.get("price_source", "?")
        price = data.get("price", "?")
        label = {"photo": "📸 фото", "caption": "💬 caption", "google": "🌐 Google"}
        print(f"💰 Price: {price} ₸ (from {label.get(source, source)}, +30% markup)")
