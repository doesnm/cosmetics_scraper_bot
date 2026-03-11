import asyncio
import sys

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from src.config import settings
from src.infrastructure.database.session import async_session, create_tables
from src.scraper import (
    ChannelScraper,
    GeminiAnalyzer,
    ImageFetcher,
    ImageMatcher,
    ChannelPoster,
    Pipeline,
)


async def main() -> None:
    interactive = "--auto" not in sys.argv

    await create_tables()

    async with TelegramClient(
        "scraper_session",
        settings.api_id,
        settings.api_hash,
    ) as tg:
        if not await tg.is_user_authorized():
            await tg.send_code_request(settings.phone_number)
            try:
                await tg.sign_in(settings.phone_number, input("Code: "))
            except SessionPasswordNeededError:
                await tg.sign_in(password=input("2FA password: "))

        scraper = ChannelScraper(tg, settings.source_channel_id)
        analyzer = GeminiAnalyzer(settings.gemini_api_key, settings.gemini_model)
        image_fetcher = ImageFetcher()
        poster = ChannelPoster(tg, settings.target_channel_id)

        matcher = (
            None
            if interactive
            else ImageMatcher(settings.gemini_api_key, settings.gemini_model)
        )

        async with async_session() as session:
            pipeline = Pipeline(
                scraper,
                analyzer,
                image_fetcher,
                poster,
                session,
                matcher=matcher,
                interactive=interactive,
            )
            await pipeline.run()


if __name__ == "__main__":
    asyncio.run(main())
