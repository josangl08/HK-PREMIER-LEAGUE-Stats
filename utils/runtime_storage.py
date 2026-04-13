# ABOUTME: Centralizes runtime-generated storage paths outside the ETL data tree.
# ABOUTME: Provides compatibility-aware helpers that read new storage first and then legacy paths.

from pathlib import Path
from typing import Iterable

RUNTIME_STORAGE_ROOT = Path("storage")
PLAYER_CARDS_RUNTIME_ROOT = RUNTIME_STORAGE_ROOT / "player_cards"
LEGACY_PLAYER_CARDS_ROOT = Path("data/player_cards")


def get_player_cards_root(*, legacy: bool = False) -> Path:
    """Return the active or legacy player-cards root."""
    return LEGACY_PLAYER_CARDS_ROOT if legacy else PLAYER_CARDS_RUNTIME_ROOT


def iter_player_cards_roots() -> tuple[Path, Path]:
    """Return roots in lookup order: runtime storage first, legacy second."""
    return PLAYER_CARDS_RUNTIME_ROOT, LEGACY_PLAYER_CARDS_ROOT


def build_player_cards_path(*parts: str | Path, legacy: bool = False) -> Path:
    """Build a path rooted under the player-cards storage tree."""
    return get_player_cards_root(legacy=legacy).joinpath(*(str(part) for part in parts))


def ensure_player_cards_dir(*parts: str | Path) -> Path:
    """Create and return a directory inside runtime player-card storage."""
    target = build_player_cards_path(*parts)
    target.mkdir(parents=True, exist_ok=True)
    return target


def iter_player_cards_candidates(*parts: str | Path) -> Iterable[Path]:
    """Yield candidate paths for migrated runtime assets, preferring new storage."""
    relative_parts = tuple(str(part) for part in parts)
    for root in iter_player_cards_roots():
        yield root.joinpath(*relative_parts)


def resolve_player_cards_path(*parts: str | Path) -> Path | None:
    """Resolve a runtime asset path from the new root or legacy root."""
    for candidate in iter_player_cards_candidates(*parts):
        if candidate.exists():
            return candidate
    return None
