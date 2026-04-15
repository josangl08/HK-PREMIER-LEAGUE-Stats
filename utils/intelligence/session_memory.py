# ABOUTME: Filesystem-backed session memory for stage intelligence, storing seen novelty keys and current curated insight state.
# ABOUTME: Provides deterministic scope keys and JSON persistence so curation memory survives across revisits without external services.

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from utils.intelligence.freshness_manager import serialize_timestamp, utc_now
from utils.intelligence.runtime_config import get_intelligence_runtime_config


def build_session_memory_key(stage: str, scope: Mapping[str, Any]) -> str:
    """Build a deterministic session-memory key from a stage scope."""
    normalized_scope = {
        str(key).strip().lower(): str(value).strip().lower()
        for key, value in (scope or {}).items()
        if value is not None and str(value).strip()
    }
    normalized_scope["stage"] = str(stage or normalized_scope.get("stage") or "season").strip().lower()
    scope_bits = [f"{key}={normalized_scope[key]}" for key in sorted(normalized_scope)]
    return f"session_memory:{':'.join(scope_bits)}"


def build_season_session_memory_key(*, player_id: str, season: str) -> str:
    """Build the canonical session-memory key for the season stage."""
    return build_session_memory_key(
        "season",
        {
            "player_id": player_id,
            "season": season,
        },
    )


def build_career_session_memory_key(*, player_id: str) -> str:
    """Build the canonical session-memory key for the career stage."""
    return build_session_memory_key(
        "career",
        {
            "player_id": player_id,
        },
    )


def build_prematch_session_memory_key(*, player_id: str, fixture_id: str) -> str:
    """Build the canonical session-memory key for the prematch stage."""
    return build_session_memory_key(
        "prematch",
        {
            "player_id": player_id,
            "fixture_id": fixture_id,
        },
    )


def build_postmatch_session_memory_key(*, player_id: str, match_id: str) -> str:
    """Build the canonical session-memory key for the postmatch stage."""
    return build_session_memory_key(
        "postmatch",
        {
            "player_id": player_id,
            "match_id": match_id,
        },
    )


def build_season_session_memory_record(
    *,
    player_id: str,
    season: str,
    current_novelty_key: str | None = None,
    seen_novelty_keys: list[str] | None = None,
    last_curated_signal_id: str | None = None,
    current_candidate: Mapping[str, Any] | None = None,
    current_anchor: str | None = None,
    current_priority: float | None = None,
    last_updated_at: str | None = None,
) -> Dict[str, Any]:
    """Build the normalized season-stage session-memory payload."""
    normalized_seen = []
    for novelty_key in seen_novelty_keys or []:
        value = str(novelty_key or "").strip()
        if value and value not in normalized_seen:
            normalized_seen.append(value)

    return {
        "memory_key": build_season_session_memory_key(player_id=player_id, season=season),
        "scope": {
            "player_id": str(player_id or ""),
            "season": str(season or ""),
            "stage": "season",
        },
        "current_novelty_key": str(current_novelty_key or "") or None,
        "current_anchor": str(current_anchor or "") or None,
        "current_priority": float(current_priority) if current_priority is not None else None,
        "current_candidate": deepcopy(dict(current_candidate or {})) if current_candidate else None,
        "seen_novelty_keys": normalized_seen,
        "last_curated_signal_id": str(last_curated_signal_id or "") or None,
        "last_updated_at": str(last_updated_at or serialize_timestamp(utc_now())),
    }


def build_career_session_memory_record(
    *,
    player_id: str,
    current_novelty_key: str | None = None,
    seen_novelty_keys: list[str] | None = None,
    last_curated_signal_id: str | None = None,
    current_candidate: Mapping[str, Any] | None = None,
    current_anchor: str | None = None,
    current_priority: float | None = None,
    last_updated_at: str | None = None,
) -> Dict[str, Any]:
    """Build the normalized career-stage session-memory payload."""
    normalized_seen = []
    for novelty_key in seen_novelty_keys or []:
        value = str(novelty_key or "").strip()
        if value and value not in normalized_seen:
            normalized_seen.append(value)

    return {
        "memory_key": build_career_session_memory_key(player_id=player_id),
        "scope": {
            "player_id": str(player_id or ""),
            "stage": "career",
        },
        "current_novelty_key": str(current_novelty_key or "") or None,
        "current_anchor": str(current_anchor or "") or None,
        "current_priority": float(current_priority) if current_priority is not None else None,
        "current_candidate": deepcopy(dict(current_candidate or {})) if current_candidate else None,
        "seen_novelty_keys": normalized_seen,
        "last_curated_signal_id": str(last_curated_signal_id or "") or None,
        "last_updated_at": str(last_updated_at or serialize_timestamp(utc_now())),
    }


def _build_stage_session_memory_record(
    *,
    stage: str,
    scope: Mapping[str, Any],
    current_novelty_key: str | None = None,
    seen_novelty_keys: list[str] | None = None,
    last_curated_signal_id: str | None = None,
    current_candidate: Mapping[str, Any] | None = None,
    current_anchor: str | None = None,
    current_priority: float | None = None,
    last_updated_at: str | None = None,
) -> Dict[str, Any]:
    """Build a normalized shared session-memory payload for a non-season stage."""
    normalized_seen = []
    for novelty_key in seen_novelty_keys or []:
        value = str(novelty_key or "").strip()
        if value and value not in normalized_seen:
            normalized_seen.append(value)

    normalized_scope = {
        str(key): str(value or "")
        for key, value in dict(scope or {}).items()
    }
    normalized_scope["stage"] = str(stage or "").strip().lower()
    return {
        "memory_key": build_session_memory_key(stage, normalized_scope),
        "scope": normalized_scope,
        "current_novelty_key": str(current_novelty_key or "") or None,
        "current_anchor": str(current_anchor or "") or None,
        "current_priority": float(current_priority) if current_priority is not None else None,
        "current_candidate": deepcopy(dict(current_candidate or {})) if current_candidate else None,
        "seen_novelty_keys": normalized_seen,
        "last_curated_signal_id": str(last_curated_signal_id or "") or None,
        "last_updated_at": str(last_updated_at or serialize_timestamp(utc_now())),
    }


def build_prematch_session_memory_record(
    *,
    player_id: str,
    fixture_id: str,
    current_novelty_key: str | None = None,
    seen_novelty_keys: list[str] | None = None,
    last_curated_signal_id: str | None = None,
    current_candidate: Mapping[str, Any] | None = None,
    current_anchor: str | None = None,
    current_priority: float | None = None,
    last_updated_at: str | None = None,
) -> Dict[str, Any]:
    """Build the normalized prematch-stage session-memory payload."""
    return _build_stage_session_memory_record(
        stage="prematch",
        scope={"player_id": player_id, "fixture_id": fixture_id},
        current_novelty_key=current_novelty_key,
        seen_novelty_keys=seen_novelty_keys,
        last_curated_signal_id=last_curated_signal_id,
        current_candidate=current_candidate,
        current_anchor=current_anchor,
        current_priority=current_priority,
        last_updated_at=last_updated_at,
    )


def build_postmatch_session_memory_record(
    *,
    player_id: str,
    match_id: str,
    current_novelty_key: str | None = None,
    seen_novelty_keys: list[str] | None = None,
    last_curated_signal_id: str | None = None,
    current_candidate: Mapping[str, Any] | None = None,
    current_anchor: str | None = None,
    current_priority: float | None = None,
    last_updated_at: str | None = None,
) -> Dict[str, Any]:
    """Build the normalized postmatch-stage session-memory payload."""
    return _build_stage_session_memory_record(
        stage="postmatch",
        scope={"player_id": player_id, "match_id": match_id},
        current_novelty_key=current_novelty_key,
        seen_novelty_keys=seen_novelty_keys,
        last_curated_signal_id=last_curated_signal_id,
        current_candidate=current_candidate,
        current_anchor=current_anchor,
        current_priority=current_priority,
        last_updated_at=last_updated_at,
    )


class SessionMemoryStore:
    """Filesystem store for deterministic stage-intelligence session memory."""

    def __init__(self, base_dir: Path | str | None = None):
        runtime_config = get_intelligence_runtime_config()
        if base_dir is None:
            base_dir = runtime_config["session_memory_root"]
        self.base_dir = Path(base_dir)
        self.memories_dir = self.base_dir / "memories"
        self.index_path = self.base_dir / "index.json"
        self.persistence_enabled = bool(runtime_config["persistence_enabled"])
        self.max_entries = int(runtime_config["session_memory_max_entries"])
        self.max_age_hours = int(runtime_config["session_memory_max_age_hours"])
        self._initialize_storage()

    def _initialize_storage(self) -> None:
        if not self.persistence_enabled:
            return
        self.memories_dir.mkdir(parents=True, exist_ok=True)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self.index_path.write_text("{}", encoding="utf-8")

    def _load_index(self) -> Dict[str, Dict[str, Any]]:
        if not self.persistence_enabled or not self.index_path.exists():
            return {}
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _save_index(self, index: Dict[str, Dict[str, Any]]) -> None:
        if not self.persistence_enabled:
            return
        self.index_path.write_text(
            json.dumps(index, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _memory_filename(self, memory_key: str) -> str:
        digest = sha256(memory_key.encode("utf-8")).hexdigest()
        return f"{digest}.json"

    def _memory_path(self, memory_key: str) -> Path:
        return self.memories_dir / self._memory_filename(memory_key)

    def get_memory(self, memory_key: str) -> Optional[Dict[str, Any]]:
        """Return a stored session-memory record when present."""
        if not self.persistence_enabled:
            return None
        index = self._load_index()
        entry = index.get(memory_key)
        if entry is None:
            return None

        memory_path = self._memory_path(memory_key)
        if not memory_path.exists():
            index.pop(memory_key, None)
            self._save_index(index)
            return None

        return json.loads(memory_path.read_text(encoding="utf-8"))

    def put_memory(self, memory_key: str, memory: Mapping[str, Any]) -> Dict[str, Any]:
        """Persist a session-memory record and update the index."""
        stored_memory = deepcopy(dict(memory))
        stored_memory["memory_key"] = memory_key
        if not self.persistence_enabled:
            return stored_memory

        memory_path = self._memory_path(memory_key)
        memory_path.write_text(
            json.dumps(stored_memory, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        index = self._load_index()
        index[memory_key] = {
            "scope": stored_memory.get("scope", {}),
            "current_novelty_key": stored_memory.get("current_novelty_key"),
            "current_anchor": stored_memory.get("current_anchor"),
            "current_priority": stored_memory.get("current_priority"),
            "last_curated_signal_id": stored_memory.get("last_curated_signal_id"),
            "last_updated_at": stored_memory.get("last_updated_at"),
            "path": str(memory_path),
        }
        self._save_index(index)
        return stored_memory

    def delete_memory(self, memory_key: str) -> bool:
        """Delete a stored session-memory record and its index entry."""
        if not self.persistence_enabled:
            return False
        index = self._load_index()
        existed = memory_key in index
        index.pop(memory_key, None)
        self._save_index(index)

        memory_path = self._memory_path(memory_key)
        path_existed = memory_path.exists()
        memory_path.unlink(missing_ok=True)
        return existed or path_existed

    def prune_memories(
        self,
        *,
        max_entries: int | None = None,
        max_age_hours: int | None = None,
    ) -> Dict[str, Any]:
        """Prune session-memory entries by age and count."""
        if not self.persistence_enabled:
            return {"pruned_keys": [], "remaining_entries": 0}

        max_entries = self.max_entries if max_entries is None else int(max_entries)
        max_age_hours = self.max_age_hours if max_age_hours is None else int(max_age_hours)
        index = self._load_index()
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=max_age_hours)
        pruned_keys = []

        for memory_key in list(index):
            memory = self.get_memory(memory_key)
            last_updated_raw = str((memory or {}).get("last_updated_at") or "")
            last_updated = None
            if last_updated_raw:
                try:
                    last_updated = datetime.fromisoformat(last_updated_raw.replace("Z", "+00:00"))
                except ValueError:
                    last_updated = None
            if last_updated is not None and last_updated < cutoff:
                if self.delete_memory(memory_key):
                    pruned_keys.append(memory_key)

        if max_entries >= 0:
            remaining_index = self._load_index()
            remaining_candidates = []
            for memory_key in remaining_index:
                memory = self.get_memory(memory_key)
                last_updated_raw = str((memory or {}).get("last_updated_at") or "")
                last_updated = None
                if last_updated_raw:
                    try:
                        last_updated = datetime.fromisoformat(last_updated_raw.replace("Z", "+00:00"))
                    except ValueError:
                        last_updated = None
                remaining_candidates.append((memory_key, last_updated or datetime.min.replace(tzinfo=timezone.utc)))
            remaining_candidates.sort(key=lambda item: item[1], reverse=True)
            for memory_key, _ in remaining_candidates[max_entries:]:
                if self.delete_memory(memory_key) and memory_key not in pruned_keys:
                    pruned_keys.append(memory_key)

        return {
            "pruned_keys": pruned_keys,
            "remaining_entries": len(self._load_index()),
        }

    def get_season_memory(self, *, player_id: str, season: str) -> Optional[Dict[str, Any]]:
        """Return season-stage session memory for the given player and season."""
        return self.get_memory(
            build_season_session_memory_key(player_id=player_id, season=season)
        )

    def put_season_memory(
        self,
        *,
        player_id: str,
        season: str,
        current_novelty_key: str | None = None,
        seen_novelty_keys: list[str] | None = None,
        last_curated_signal_id: str | None = None,
        current_candidate: Mapping[str, Any] | None = None,
        current_anchor: str | None = None,
        current_priority: float | None = None,
        last_updated_at: str | None = None,
    ) -> Dict[str, Any]:
        """Persist a normalized season-stage session-memory record."""
        memory = build_season_session_memory_record(
            player_id=player_id,
            season=season,
            current_novelty_key=current_novelty_key,
            seen_novelty_keys=seen_novelty_keys,
            last_curated_signal_id=last_curated_signal_id,
            current_candidate=current_candidate,
            current_anchor=current_anchor,
            current_priority=current_priority,
            last_updated_at=last_updated_at,
        )
        return self.put_memory(memory["memory_key"], memory)

    def get_career_memory(self, *, player_id: str) -> Optional[Dict[str, Any]]:
        """Return career-stage session memory for the given player."""
        return self.get_memory(
            build_career_session_memory_key(player_id=player_id)
        )

    def put_career_memory(
        self,
        *,
        player_id: str,
        current_novelty_key: str | None = None,
        seen_novelty_keys: list[str] | None = None,
        last_curated_signal_id: str | None = None,
        current_candidate: Mapping[str, Any] | None = None,
        current_anchor: str | None = None,
        current_priority: float | None = None,
        last_updated_at: str | None = None,
    ) -> Dict[str, Any]:
        """Persist a normalized career-stage session-memory record."""
        memory = build_career_session_memory_record(
            player_id=player_id,
            current_novelty_key=current_novelty_key,
            seen_novelty_keys=seen_novelty_keys,
            last_curated_signal_id=last_curated_signal_id,
            current_candidate=current_candidate,
            current_anchor=current_anchor,
            current_priority=current_priority,
            last_updated_at=last_updated_at,
        )
        return self.put_memory(memory["memory_key"], memory)

    def get_prematch_memory(self, *, player_id: str, fixture_id: str) -> Optional[Dict[str, Any]]:
        """Return prematch-stage session memory for the given player and fixture."""
        return self.get_memory(
            build_prematch_session_memory_key(player_id=player_id, fixture_id=fixture_id)
        )

    def put_prematch_memory(
        self,
        *,
        player_id: str,
        fixture_id: str,
        current_novelty_key: str | None = None,
        seen_novelty_keys: list[str] | None = None,
        last_curated_signal_id: str | None = None,
        current_candidate: Mapping[str, Any] | None = None,
        current_anchor: str | None = None,
        current_priority: float | None = None,
        last_updated_at: str | None = None,
    ) -> Dict[str, Any]:
        """Persist a normalized prematch-stage session-memory record."""
        memory = build_prematch_session_memory_record(
            player_id=player_id,
            fixture_id=fixture_id,
            current_novelty_key=current_novelty_key,
            seen_novelty_keys=seen_novelty_keys,
            last_curated_signal_id=last_curated_signal_id,
            current_candidate=current_candidate,
            current_anchor=current_anchor,
            current_priority=current_priority,
            last_updated_at=last_updated_at,
        )
        return self.put_memory(memory["memory_key"], memory)

    def get_postmatch_memory(self, *, player_id: str, match_id: str) -> Optional[Dict[str, Any]]:
        """Return postmatch-stage session memory for the given player and match."""
        return self.get_memory(
            build_postmatch_session_memory_key(player_id=player_id, match_id=match_id)
        )

    def put_postmatch_memory(
        self,
        *,
        player_id: str,
        match_id: str,
        current_novelty_key: str | None = None,
        seen_novelty_keys: list[str] | None = None,
        last_curated_signal_id: str | None = None,
        current_candidate: Mapping[str, Any] | None = None,
        current_anchor: str | None = None,
        current_priority: float | None = None,
        last_updated_at: str | None = None,
    ) -> Dict[str, Any]:
        """Persist a normalized postmatch-stage session-memory record."""
        memory = build_postmatch_session_memory_record(
            player_id=player_id,
            match_id=match_id,
            current_novelty_key=current_novelty_key,
            seen_novelty_keys=seen_novelty_keys,
            last_curated_signal_id=last_curated_signal_id,
            current_candidate=current_candidate,
            current_anchor=current_anchor,
            current_priority=current_priority,
            last_updated_at=last_updated_at,
        )
        return self.put_memory(memory["memory_key"], memory)


_DEFAULT_SESSION_MEMORY_STORE: SessionMemoryStore | None = None


def _get_default_session_memory_store() -> SessionMemoryStore:
    """Lazily initialize the shared session-memory store."""
    global _DEFAULT_SESSION_MEMORY_STORE
    if _DEFAULT_SESSION_MEMORY_STORE is None:
        _DEFAULT_SESSION_MEMORY_STORE = SessionMemoryStore()
    return _DEFAULT_SESSION_MEMORY_STORE


def get_session_memory(
    memory_key: str,
    store: SessionMemoryStore | None = None,
) -> Optional[Dict[str, Any]]:
    """Module-level getter for arbitrary session-memory scope keys."""
    active_store = store or _get_default_session_memory_store()
    return active_store.get_memory(memory_key)


def put_session_memory(
    memory_key: str,
    memory: Mapping[str, Any],
    store: SessionMemoryStore | None = None,
) -> Dict[str, Any]:
    """Module-level put helper for arbitrary session-memory scope keys."""
    active_store = store or _get_default_session_memory_store()
    return active_store.put_memory(memory_key, memory)


def get_season_session_memory(
    *,
    player_id: str,
    season: str,
    store: SessionMemoryStore | None = None,
) -> Optional[Dict[str, Any]]:
    """Module-level getter for season-stage session memory."""
    active_store = store or _get_default_session_memory_store()
    return active_store.get_season_memory(player_id=player_id, season=season)


def put_season_session_memory(
    *,
    player_id: str,
    season: str,
    current_novelty_key: str | None = None,
    seen_novelty_keys: list[str] | None = None,
    last_curated_signal_id: str | None = None,
    current_candidate: Mapping[str, Any] | None = None,
    current_anchor: str | None = None,
    current_priority: float | None = None,
    last_updated_at: str | None = None,
    store: SessionMemoryStore | None = None,
) -> Dict[str, Any]:
    """Module-level put helper for season-stage session memory."""
    active_store = store or _get_default_session_memory_store()
    return active_store.put_season_memory(
        player_id=player_id,
        season=season,
        current_novelty_key=current_novelty_key,
        seen_novelty_keys=seen_novelty_keys,
        last_curated_signal_id=last_curated_signal_id,
        current_candidate=current_candidate,
        current_anchor=current_anchor,
        current_priority=current_priority,
        last_updated_at=last_updated_at,
    )


def get_career_session_memory(
    *,
    player_id: str,
    store: SessionMemoryStore | None = None,
) -> Optional[Dict[str, Any]]:
    """Module-level getter for career-stage session memory."""
    active_store = store or _get_default_session_memory_store()
    return active_store.get_career_memory(player_id=player_id)


def put_career_session_memory(
    *,
    player_id: str,
    current_novelty_key: str | None = None,
    seen_novelty_keys: list[str] | None = None,
    last_curated_signal_id: str | None = None,
    current_candidate: Mapping[str, Any] | None = None,
    current_anchor: str | None = None,
    current_priority: float | None = None,
    last_updated_at: str | None = None,
    store: SessionMemoryStore | None = None,
) -> Dict[str, Any]:
    """Module-level put helper for career-stage session memory."""
    active_store = store or _get_default_session_memory_store()
    return active_store.put_career_memory(
        player_id=player_id,
        current_novelty_key=current_novelty_key,
        seen_novelty_keys=seen_novelty_keys,
        last_curated_signal_id=last_curated_signal_id,
        current_candidate=current_candidate,
        current_anchor=current_anchor,
        current_priority=current_priority,
        last_updated_at=last_updated_at,
    )


def get_prematch_session_memory(
    *,
    player_id: str,
    fixture_id: str,
    store: SessionMemoryStore | None = None,
) -> Optional[Dict[str, Any]]:
    """Module-level getter for prematch-stage session memory."""
    active_store = store or _get_default_session_memory_store()
    return active_store.get_prematch_memory(player_id=player_id, fixture_id=fixture_id)


def put_prematch_session_memory(
    *,
    player_id: str,
    fixture_id: str,
    current_novelty_key: str | None = None,
    seen_novelty_keys: list[str] | None = None,
    last_curated_signal_id: str | None = None,
    current_candidate: Mapping[str, Any] | None = None,
    current_anchor: str | None = None,
    current_priority: float | None = None,
    last_updated_at: str | None = None,
    store: SessionMemoryStore | None = None,
) -> Dict[str, Any]:
    """Module-level put helper for prematch-stage session memory."""
    active_store = store or _get_default_session_memory_store()
    return active_store.put_prematch_memory(
        player_id=player_id,
        fixture_id=fixture_id,
        current_novelty_key=current_novelty_key,
        seen_novelty_keys=seen_novelty_keys,
        last_curated_signal_id=last_curated_signal_id,
        current_candidate=current_candidate,
        current_anchor=current_anchor,
        current_priority=current_priority,
        last_updated_at=last_updated_at,
    )


def get_postmatch_session_memory(
    *,
    player_id: str,
    match_id: str,
    store: SessionMemoryStore | None = None,
) -> Optional[Dict[str, Any]]:
    """Module-level getter for postmatch-stage session memory."""
    active_store = store or _get_default_session_memory_store()
    return active_store.get_postmatch_memory(player_id=player_id, match_id=match_id)


def put_postmatch_session_memory(
    *,
    player_id: str,
    match_id: str,
    current_novelty_key: str | None = None,
    seen_novelty_keys: list[str] | None = None,
    last_curated_signal_id: str | None = None,
    current_candidate: Mapping[str, Any] | None = None,
    current_anchor: str | None = None,
    current_priority: float | None = None,
    last_updated_at: str | None = None,
    store: SessionMemoryStore | None = None,
) -> Dict[str, Any]:
    """Module-level put helper for postmatch-stage session memory."""
    active_store = store or _get_default_session_memory_store()
    return active_store.put_postmatch_memory(
        player_id=player_id,
        match_id=match_id,
        current_novelty_key=current_novelty_key,
        seen_novelty_keys=seen_novelty_keys,
        last_curated_signal_id=last_curated_signal_id,
        current_candidate=current_candidate,
        current_anchor=current_anchor,
        current_priority=current_priority,
        last_updated_at=last_updated_at,
    )
