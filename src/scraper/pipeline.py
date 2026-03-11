import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.product import ProductORM

from .analyzer import GeminiAnalyzer
from .channel import ChannelScraper
from .images import CandidateImage, ImageFetcher
from .matcher import ImageMatcher
from .poster import ChannelPoster
from .reviewer import Reviewer

RATE_LIMIT_DELAY = 1.5


@dataclass(slots=True)
class PickResult:
    photo: bytes
    url: str | None


class Pipeline:
    """Scrape → Analyze → DDG images → Pick → Save → Post."""

    def __init__(
        self,
        scraper: ChannelScraper,
        analyzer: GeminiAnalyzer,
        image_fetcher: ImageFetcher,
        poster: ChannelPoster,
        session: AsyncSession,
        matcher: ImageMatcher | None = None,
        interactive: bool = True,
    ) -> None:
        self._scraper = scraper
        self._analyzer = analyzer
        self._images = image_fetcher
        self._poster = poster
        self._session = session
        self._matcher = matcher
        self._reviewer = Reviewer() if interactive else None

    async def run(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> int:
        date_from = date_from or datetime(2025, 1, 1, tzinfo=timezone.utc)
        date_to = date_to or datetime(2027, 1, 1, tzinfo=timezone.utc)

        saved = 0
        skipped = 0
        quit_requested = False

        async for post in self._scraper.iter_posts(date_from, date_to):
            # 1. analyze
            data = await self._analyzer.analyze(post.photo_bytes, post.caption)
            await asyncio.sleep(RATE_LIMIT_DELAY)

            if not data:
                print(f"⚠️  msg {post.message_id}: analysis failed")
                continue
            if data.get("category") != "skincare":
                print(f"⏭️  msg {post.message_id}: {data.get('category', '?')}")
                continue

            # 2. search images via DDG
            brand = data.get("brand") or ""
            name = data.get("name") or ""
            query = f"{brand} {name}".strip()
            candidates = await self._images.search(query)

            # 3. pick photo
            pick: PickResult | None = None

            if self._reviewer:
                pick, quit_requested = await self._interactive_pick(
                    data,
                    post.photo_bytes,
                    candidates,
                    post.message_id,
                )
            else:
                pick = await self._auto_pick(post.photo_bytes, candidates)

            if quit_requested:
                print("🛑 Stopped by operator.")
                break

            if pick is None:
                skipped += 1
                print(f"⏭️  msg {post.message_id}: no photo ({skipped} skipped)")
                continue

            # 4. save to DB
            product = self._to_orm(data, pick.url)
            self._session.add(product)

            # 5. post to channel
            try:
                post_result = await self._poster.post(data, pick.photo)
                product.tg_file_id = post_result.file_id
                saved += 1
                print(
                    f"✅ #{saved} {product.brand} — {product.name} "
                    f"({product.price} ₸) → msg {post_result.message_id}"
                )
            except Exception as exc:
                saved += 1
                print(f"⚠️  DB ok, TG failed: {exc}")

            if saved % 20 == 0:
                await self._session.commit()

        await self._session.commit()
        print(f"\n🎉 Done. Saved: {saved}, Skipped: {skipped}")
        return saved

    # ── interactive ──────────────────────────────────────────

    async def _interactive_pick(
        self,
        data: dict,
        source_photo: bytes,
        candidates: list[CandidateImage],
        message_id: int,
    ) -> tuple[PickResult | None, bool]:
        assert self._reviewer is not None

        while True:
            choice = self._reviewer.review(
                data,
                source_photo,
                candidates,
                message_id,
            )
            if choice == "q":
                return None, True
            if choice == "n":
                return None, False
            if choice == "y":
                photo = self._reviewer.selected_photo
                url = self._reviewer.selected_url
                if photo is not None:
                    return PickResult(photo=photo, url=url), False
                return None, False
            if choice == "u":
                pending = self._reviewer.pending_url
                if pending is None:
                    continue
                photo = await self._images.fetch_direct(pending)
                if photo:
                    return PickResult(photo=photo, url=pending), False
                print("❌ Download failed, try again")

    # ── auto ─────────────────────────────────────────────────

    async def _auto_pick(
        self,
        source_photo: bytes,
        candidates: list[CandidateImage],
    ) -> PickResult | None:
        if not candidates:
            return None
        if not self._matcher:
            c = candidates[0]
            return PickResult(photo=c.data, url=c.url)

        idx = await self._matcher.pick_best(source_photo, candidates)
        if idx is not None:
            c = candidates[idx]
            print(f"🤖 Matcher picked candidate {idx + 1}")
            return PickResult(photo=c.data, url=c.url)

        print("🤖 Matcher: none matched")
        return None

    # ── ORM ──────────────────────────────────────────────────

    @staticmethod
    def _to_orm(data: dict, image_url: str | None) -> ProductORM:
        return ProductORM(
            name=data.get("name") or "Unknown",
            brand=data.get("brand") or "Unknown",
            category="skincare",
            gender=data.get("gender") or "unisex",
            price=data.get("price") or 0,
            currency="KZT",
            rating=data.get("rating") or 0,
            description=data.get("description") or "",
            attributes=data.get("attributes") or {},
            image_url=image_url,
            tg_file_id=None,
        )
