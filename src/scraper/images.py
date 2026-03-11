import io
import re
from dataclasses import dataclass

import aiohttp
from PIL import Image

TIMEOUT = aiohttp.ClientTimeout(total=15)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:148.0) "
        "Gecko/20100101 Firefox/148.0"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://duckduckgo.com/",
    "Sec-GPC": "1",
    "DNT": "1",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

IMG_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:148.0) "
        "Gecko/20100101 Firefox/148.0"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass(frozen=True, slots=True)
class CandidateImage:
    url: str
    data: bytes


def resize_image(image_bytes: bytes, max_side: int) -> bytes:
    """Shrink longest side to max_side px."""
    img = Image.open(io.BytesIO(image_bytes))
    if max(img.size) <= max_side:
        return image_bytes
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


class ImageFetcher:
    """DuckDuckGo Image Search → candidate product images."""

    async def search(
        self,
        query: str,
        num: int = 3,
    ) -> list[CandidateImage]:
        """Search DDG images, download up to `num` results."""
        if not query.strip():
            return []

        urls = await self._ddg_image_urls(query, num)
        return await self.download_candidates(urls)

    async def download_candidates(
        self,
        urls: list[str],
    ) -> list[CandidateImage]:
        candidates: list[CandidateImage] = []
        for url in urls:
            data = await self.fetch_direct(url)
            if data:
                candidates.append(CandidateImage(url=url, data=data))
        return candidates

    async def fetch_direct(self, url: str) -> bytes | None:
        try:
            async with aiohttp.ClientSession(headers=IMG_HEADERS) as session:
                async with session.get(
                    url,
                    timeout=TIMEOUT,
                    allow_redirects=True,
                ) as resp:
                    if resp.status != 200:
                        print(f"❌ Image HTTP {resp.status}: {url[:80]}")
                        return None
                    ct = resp.headers.get("content-type", "")
                    if "html" in ct:
                        print(f"❌ Got HTML: {url[:80]}")
                        return None
                    data = await resp.read()
                    if len(data) < 1_000:
                        print(f"❌ Too small ({len(data)}b): {url[:80]}")
                        return None
                    return data
        except Exception as exc:
            print(f"❌ Download error: {exc}")
            return None

    async def _ddg_image_urls(
        self,
        query: str,
        num: int,
    ) -> list[str]:
        """
        1. GET duckduckgo.com/?q=...&iax=images&ia=images → extract vqd token
        2. GET duckduckgo.com/i.js?q=...&vqd=...&o=json → JSON with results
        3. Return full-size image URLs
        """
        vqd = await self._get_vqd(query)
        if not vqd:
            print("❌ DDG: failed to get vqd token")
            return []

        params = {
            "q": query,
            "o": "json",
            "p": "1",
            "l": "us-en",
            "vqd": vqd,
        }

        try:
            async with aiohttp.ClientSession(headers=HEADERS) as session:
                async with session.get(
                    "https://duckduckgo.com/i.js",
                    params=params,
                    timeout=TIMEOUT,
                ) as resp:
                    if resp.status != 200:
                        print(f"❌ DDG i.js HTTP {resp.status}")
                        return []
                    data = await resp.json(content_type=None)
                    results = data.get("results") or []
                    urls: list[str] = []
                    for r in results[:num]:
                        img = r.get("image")
                        if img:
                            urls.append(img)
                    print(f"🔍 DDG: found {len(urls)} images for '{query[:50]}'")
                    return urls
        except Exception as exc:
            print(f"❌ DDG i.js error: {exc}")
            return []

    async def _get_vqd(self, query: str) -> str | None:
        """Fetch DDG search page to extract vqd token."""
        params = {"q": query, "iax": "images", "ia": "images"}
        try:
            async with aiohttp.ClientSession(
                headers={
                    "User-Agent": HEADERS["User-Agent"],
                    "Accept": "text/html,*/*;q=0.9",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            ) as session:
                async with session.get(
                    "https://duckduckgo.com/",
                    params=params,
                    timeout=TIMEOUT,
                ) as resp:
                    if resp.status != 200:
                        print(f"❌ DDG page HTTP {resp.status}")
                        return None
                    text = await resp.text()
                    # vqd token is in: vqd="4-123456..."
                    match = re.search(r'vqd="([^"]+)"', text)
                    if match:
                        return match.group(1)
                    # alternative: vqd=4-123... in script
                    match = re.search(r"vqd=([0-9a-f-]+)", text)
                    if match:
                        return match.group(1)
                    print("❌ DDG: vqd token not found in page")
                    return None
        except Exception as exc:
            print(f"❌ DDG vqd error: {exc}")
            return None
