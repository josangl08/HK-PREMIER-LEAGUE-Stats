# ABOUTME: Global runtime state and assisted-session storage for Transfermarkt refresh workflows.

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from models.db_models import ExternalSourceCredential, ExternalSourceStatus
from utils.db_engine import SessionFactory


logger = logging.getLogger(__name__)

TM_SOURCE = "transfermarkt"


class TransfermarktRuntimeManager:
    def _utcnow(self) -> datetime:
        # SQLite typically returns naive datetimes; keep runtime comparisons in naive UTC.
        return datetime.utcnow()

    def _to_naive_utc(self, value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def _get_status_row(self, session) -> ExternalSourceStatus:
        row = session.get(ExternalSourceStatus, TM_SOURCE)
        if row is None:
            row = ExternalSourceStatus(source=TM_SOURCE, mode="NORMAL", status="READY", failure_count=0)
            session.add(row)
            session.flush()
        return row

    def get_status(self) -> ExternalSourceStatus:
        with SessionFactory() as session:
            row = self._get_status_row(session)
            session.expunge(row)
            return row

    def should_skip_automatic_refresh(self) -> bool:
        with SessionFactory() as session:
            row = self._get_status_row(session)
            now = self._utcnow()
            if row.mode == "ASSISTED_ACTIVE":
                return False
            cooldown_until = self._to_naive_utc(row.cooldown_until)
            if row.mode == "BLOCKED" and cooldown_until and cooldown_until > now:
                return True
            return False

    def record_success(self, metadata: Optional[dict[str, Any]] = None) -> None:
        with SessionFactory() as session:
            row = self._get_status_row(session)
            now = self._utcnow()
            row.last_success_at = now
            row.failure_count = 0
            row.block_reason = None
            row.blocked_at = None
            row.cooldown_until = None
            if row.mode == "ASSISTED_ACTIVE":
                row.mode = "RECOVERING"
                row.status = "ASSISTED"
            else:
                row.mode = "NORMAL"
                row.status = "READY"
            if metadata:
                row.metadata_json = metadata
            session.commit()

    def record_failure(self, *, reason: str, hard_block: bool, cooldown_hours: int = 24) -> ExternalSourceStatus:
        with SessionFactory() as session:
            row = self._get_status_row(session)
            now = self._utcnow()
            row.last_failure_at = now
            row.failure_count = (row.failure_count or 0) + 1
            row.block_reason = reason[:500]
            if hard_block or row.failure_count >= 3:
                row.mode = "BLOCKED"
                row.status = "BLOCKED"
                row.blocked_at = now
                row.cooldown_until = now + timedelta(hours=cooldown_hours)
            else:
                row.mode = "DEGRADED"
                row.status = "DEGRADED"
            session.commit()
            session.expunge(row)
            return row

    def activate_assisted_mode(self, expires_in_hours: int = 12) -> None:
        with SessionFactory() as session:
            row = self._get_status_row(session)
            now = self._utcnow()
            row.mode = "ASSISTED_ACTIVE"
            row.status = "ASSISTED"
            row.assisted_session_loaded_at = now
            row.assisted_session_expires_at = now + timedelta(hours=expires_in_hours)
            row.cooldown_until = None
            session.commit()

    def deactivate_assisted_mode(self) -> None:
        with SessionFactory() as session:
            row = self._get_status_row(session)
            if row.failure_count:
                row.mode = "DEGRADED"
                row.status = "DEGRADED"
            else:
                row.mode = "NORMAL"
                row.status = "READY"
                row.blocked_at = None
                row.cooldown_until = None
                row.block_reason = None
            row.assisted_session_loaded_at = None
            row.assisted_session_expires_at = None
            session.commit()

    def store_cookie_payload(self, payload: str, *, created_by: str = "manual", expires_at: Optional[datetime] = None) -> None:
        with SessionFactory() as session:
            row = session.get(ExternalSourceCredential, TM_SOURCE)
            if row is None:
                row = ExternalSourceCredential(source=TM_SOURCE)
                session.add(row)
            row.credential_type = "cookies_json"
            row.secret_payload = payload
            row.created_by = created_by
            row.expires_at = self._to_naive_utc(expires_at)
            session.commit()

    def clear_cookie_payload(self) -> None:
        with SessionFactory() as session:
            row = session.get(ExternalSourceCredential, TM_SOURCE)
            if row:
                row.secret_payload = None
                row.expires_at = None
                session.commit()

    def get_cookie_payload(self) -> Optional[str]:
        with SessionFactory() as session:
            row = session.get(ExternalSourceCredential, TM_SOURCE)
            if not row or not row.secret_payload:
                return None
            expires_at = self._to_naive_utc(row.expires_at)
            if expires_at and expires_at < self._utcnow():
                return None
            return row.secret_payload

    def get_cookie_jar(self) -> list[dict[str, Any]]:
        payload = self.get_cookie_payload()
        if not payload:
            return []
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("Transfermarkt cookie payload is not valid JSON.")
            return []
        if isinstance(data, dict):
            return [{"name": k, "value": v} for k, v in data.items()]
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict) and item.get("name") and item.get("value")]
        return []
