import io
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator

from telethon import TelegramClient


@dataclass(frozen=True, slots=True)
class RawPost:
    message_id: int
    photo_bytes: bytes
    caption: str | None
    date: datetime


class ChannelScraper:
    """Yields posts with photos from a TG channel within a date range."""

    def __init__(self, client: TelegramClient, channel_id: int) -> None:
        self._client = client
        self._channel_id = channel_id

    async def iter_posts(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> AsyncIterator[RawPost]:
        async for msg in self._client.iter_messages(
            self._channel_id,
            offset_date=date_to,
        ):
            if msg.date < date_from:
                break
            if not msg.photo:
                continue

            buf = io.BytesIO()
            await self._client.download_media(msg.photo, buf)

            yield RawPost(
                message_id=msg.id,
                photo_bytes=buf.getvalue(),
                caption=msg.text,
                date=msg.date,
            )
