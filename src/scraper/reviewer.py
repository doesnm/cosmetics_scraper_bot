import os
import sys
import tempfile
from pathlib import Path

from .images import CandidateImage
from .poster import format_post

REVIEW_DIR = Path(tempfile.gettempdir()) / "cosmetics_review"

EDITABLE_FIELDS = [
    ("name", "Название продукта"),
    ("brand", "Бренд"),
    ("price", "Цена"),
    ("currency", "Валюта"),
    ("category", "Категория"),
    ("gender", "Для кого (en)"),
    ("rating", "Рейтинг"),
    ("description", "Описание (en)"),
]

EDITABLE_ATTRS = [
    ("skin_type", "Тип кожи (en, через запятую)"),
    ("skin_concerns", "Проблемы кожи (en, через запятую)"),
    ("formulation", "Формула"),
    ("key_ingredients", "Ингредиенты (en, через запятую)"),
    ("volume", "Объём"),
]

EDITABLE_POST_RU = [
    ("product_type", "Тип продукта"),
    ("target_audience", "Для кого"),
    ("purpose", "Назначение"),
    ("skin_type", "Тип кожи"),
    ("application_area", "Область применения"),
    ("volume", "Объём"),
]


class Reviewer:
    """Interactive CLI review: pick photo from 3 candidates, edit any field."""

    def __init__(self) -> None:
        REVIEW_DIR.mkdir(exist_ok=True)
        self.selected_photo: bytes | None = None
        self.selected_url: str | None = None
        self.pending_url: str | None = None

    def review(
        self,
        data: dict,
        source_photo: bytes,
        candidates: list[CandidateImage],
        message_id: int,
    ) -> str:
        """
        Returns: 'y' (check selected_photo / selected_url),
                 'u' (download pending_url, then re-review),
                 'n' (skip), 'q' (quit).
        """
        self.selected_photo = None
        self.selected_url = None
        self.pending_url = None

        source_path = REVIEW_DIR / f"{message_id}_source.jpg"
        source_path.write_bytes(source_photo)

        cand_paths: list[Path] = []
        for i, c in enumerate(candidates, 1):
            p = REVIEW_DIR / f"{message_id}_cand_{i}.jpg"
            p.write_bytes(c.data)
            cand_paths.append(p)

        self._print_card(data, source_path, cand_paths, candidates)
        self._open_all(source_path, cand_paths)

        while True:
            n = len(candidates)
            nums = "/".join(str(i) for i in range(1, n + 1)) if n else ""
            options = []
            if nums:
                options.append(f"[{nums}] pick photo")
            options += ["[e] edit", "[u] paste URL", "[n] skip", "[q] quit"]
            prompt = " / ".join(options) + ": "

            choice = input(f"\n{prompt}").strip().lower()

            if choice == "q":
                return "q"
            if choice == "n":
                return "n"
            if choice == "e":
                self._edit(data)
                self._print_card(data, source_path, cand_paths, candidates)
                continue
            if choice == "u":
                self.pending_url = input("Image URL: ").strip()
                if self.pending_url:
                    return "u"
                print("Empty URL, try again")
                continue
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < n:
                    self.selected_photo = candidates[idx].data
                    self.selected_url = candidates[idx].url
                    return "y"
                print(f"Invalid number, pick 1-{n}")
                continue
            print("Invalid input")

    # ── display ──────────────────────────────────────────────

    @staticmethod
    def _print_card(
        data: dict,
        source_path: Path,
        cand_paths: list[Path],
        candidates: list[CandidateImage],
    ) -> None:
        post_text = format_post(data)
        attrs = data.get("attributes") or {}

        price_source = data.get("price_source", "?")
        price_tag = (
            "📸 фото"
            if price_source == "photo"
            else ("💬 caption" if price_source == "caption" else "🌐 Google")
        )

        print("\n" + "=" * 60)
        print(f"📷 Source photo:  {source_path}")
        for i, p in enumerate(cand_paths, 1):
            url = candidates[i - 1].url if i - 1 < len(candidates) else "?"
            print(f"🖼️  Candidate {i}:  {p}")
            print(f"    URL: {url}")
        if not cand_paths:
            print("🖼️  Candidates:   ❌ NONE FOUND")
        print("-" * 60)
        print(post_text)
        print("-" * 60)
        print(f"💰 Цена из:  {price_tag}")
        print(f"Brand:       {data.get('brand')}")
        print(f"Category:    {data.get('category')}")
        print(f"Gender:      {data.get('gender')}")
        print(f"Rating:      {data.get('rating')}")
        print(f"Description: {data.get('description')}")
        print(f"Skin type:   {attrs.get('skin_type')}")
        print(f"Concerns:    {attrs.get('skin_concerns')}")
        print(f"Formulation: {attrs.get('formulation')}")
        print(f"Ingredients: {attrs.get('key_ingredients')}")
        print(f"Volume:      {attrs.get('volume')}")
        print("=" * 60)

    @staticmethod
    def _open_all(source_path: Path, cand_paths: list[Path]) -> None:
        for p in [source_path, *cand_paths]:
            _try_open(p)

    # ── edit ─────────────────────────────────────────────────

    def _edit(self, data: dict) -> None:
        menu = self._build_edit_menu(data)
        self._print_edit_menu(menu)

        raw = input("Field numbers (comma-separated) or 'all': ").strip().lower()
        if not raw:
            return

        indices = (
            list(range(len(menu))) if raw == "all" else _parse_indices(raw, len(menu))
        )

        for idx in indices:
            section, key, label, old = menu[idx]
            new = input(f"  {label} [{old}]: ").strip()
            if not new:
                continue
            _apply_edit(data, section, key, old, new)
            print(f"  ✏️  {label} → {new}")

    @staticmethod
    def _build_edit_menu(data: dict) -> list[tuple[str, str, str, str]]:
        items: list[tuple[str, str, str, str]] = []
        for key, label in EDITABLE_FIELDS:
            items.append(("root", key, label, str(data.get(key) or "")))
        attrs = data.get("attributes") or {}
        for key, label in EDITABLE_ATTRS:
            val = attrs.get(key, "")
            if isinstance(val, list):
                val = ", ".join(val)
            items.append(("attributes", key, f"[attr] {label}", str(val)))
        post_ru = data.get("post_ru") or {}
        for key, label in EDITABLE_POST_RU:
            items.append(
                ("post_ru", key, f"[пост] {label}", str(post_ru.get(key) or ""))
            )
        return items

    @staticmethod
    def _print_edit_menu(items: list[tuple[str, str, str, str]]) -> None:
        print("\n📝 Editable fields:")
        for i, (_, _, label, value) in enumerate(items, 1):
            short = value[:50] + "…" if len(value) > 50 else value
            print(f"  {i:2d}. {label}: {short}")


# ── helpers ──────────────────────────────────────────────────


def _parse_indices(raw: str, total: int) -> list[int]:
    try:
        indices = [int(x.strip()) - 1 for x in raw.split(",")]
        return [i for i in indices if 0 <= i < total]
    except ValueError:
        print("Invalid input")
        return []


def _apply_edit(data: dict, section: str, key: str, old: str, new: str) -> None:
    parsed = _parse_value(key, old, new)
    if section == "root":
        data[key] = parsed
    elif section == "attributes":
        data.setdefault("attributes", {})[key] = parsed
    elif section == "post_ru":
        data.setdefault("post_ru", {})[key] = parsed


def _parse_value(key: str, old: str, new: str) -> object:
    if key in ("price", "rating"):
        try:
            return float(new)
        except ValueError:
            print(f"  ⚠️  Invalid number, keeping {old}")
            return float(old) if old else 0
    if key in ("skin_type", "skin_concerns", "key_ingredients"):
        return [x.strip() for x in new.split(",") if x.strip()]
    return new


def _try_open(path: Path) -> None:
    try:
        import subprocess

        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif sys.platform == "win32":
            os.startfile(str(path))
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass
