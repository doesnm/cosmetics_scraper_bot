import io
from dataclasses import dataclass

from telethon import TelegramClient


@dataclass(frozen=True, slots=True)
class PostResult:
    message_id: int
    file_id: str | None


def format_post(data: dict) -> str:
    price = data.get("price") or 0
    ru = data.get("post_ru") or {}

    lines = [
        f"Цена: {_format_price(price)} ₸",
        "",
        "Подробные характеристики",
        "",
        f"Название продукта: {data.get('name') or '—'}",
        f"Тип продукта: {ru.get('product_type') or '—'}",
        f"Для кого: {ru.get('target_audience') or '—'}",
        f"Назначение: {ru.get('purpose') or '—'}",
        f"Тип кожи: {ru.get('skin_type') or '—'}",
        f"Область применения: {ru.get('application_area') or '—'}",
        f"Объём: {ru.get('volume') or '—'}",
    ]
    return "\n".join(lines)


def _format_price(price: float | int) -> str:
    if isinstance(price, float) and price == int(price):
        return str(int(price))
    return str(price)


class ChannelPoster:
    def __init__(self, client: TelegramClient, channel_id: int) -> None:
        self._client = client
        self._channel_id = channel_id

    async def post(self, data: dict, photo_bytes: bytes) -> PostResult:
        text = format_post(data)

        buf = io.BytesIO(photo_bytes)
        buf.name = "product.jpg"

        msg = await self._client.send_file(
            self._channel_id,
            file=buf,
            caption=text,
            force_document=False,
        )

        file_id: str | None = None
        photo = getattr(msg, "photo", None)
        if photo is not None:
            file_id = str(photo.id)

        return PostResult(message_id=msg.id, file_id=file_id)

