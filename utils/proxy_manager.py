# ABOUTME: Rotating proxy pool manager for Transfermarkt scraping.
# ABOUTME: Loads proxies from data/proxies.txt, rotates on failure with cooldown tracking.

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

DEFAULT_PROXY_FILE = Path("data/proxies.txt")
_COOLDOWN_SECONDS = 600      # 10 min cooldown per proxy after max failures
_MAX_FAILURES = 2            # failures before cooldown


@dataclass
class _ProxyState:
    url: str
    failures: int = 0
    cooldown_until: float = 0.0


class ProxyManager:
    """
    Round-robin proxy pool with per-proxy failure tracking and cooldown.

    Proxy file format (one per line, lines starting with # are comments):
        http://user:pass@host:port
        socks5://user:pass@host:port
        http://host:port            # no auth

    Returns None from get_proxy() when the pool is empty or all proxies are cooling down
    (caller should fall back to direct connection).
    """

    def __init__(self, proxy_file: Path = DEFAULT_PROXY_FILE):
        self._pool: List[_ProxyState] = []
        self._index: int = 0
        self._load(proxy_file)

    def _load(self, path: Path) -> None:
        if not path.exists():
            logger.info("ProxyManager: %s not found — running without proxies.", path)
            return
        lines = path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            self._pool.append(_ProxyState(url=line))
        logger.info("ProxyManager: loaded %d proxy/proxies from %s.", len(self._pool), path)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    @property
    def has_proxies(self) -> bool:
        return bool(self._pool)

    def get_proxy(self) -> Optional[str]:
        """Return next available proxy URL, or None if pool is empty / all cooling down."""
        if not self._pool:
            return None
        now = time.time()
        available = [p for p in self._pool if p.cooldown_until <= now]
        if not available:
            soonest = min(self._pool, key=lambda p: p.cooldown_until)
            wait = soonest.cooldown_until - now
            logger.warning("ProxyManager: all proxies cooling down. Soonest ready in %.0fs.", wait)
            return None
        # Round-robin among available proxies.
        self._index = self._index % len(available)
        proxy = available[self._index]
        self._index = (self._index + 1) % len(available)
        return proxy.url

    def mark_failure(self, proxy_url: str) -> None:
        """Record a WAF block or connection failure for this proxy."""
        state = self._find(proxy_url)
        if state is None:
            return
        state.failures += 1
        if state.failures >= _MAX_FAILURES:
            state.cooldown_until = time.time() + _COOLDOWN_SECONDS
            logger.warning(
                "ProxyManager: proxy %s reached %d failures — cooling down for %ds.",
                self._safe_url(proxy_url), state.failures, _COOLDOWN_SECONDS,
            )
        else:
            logger.debug("ProxyManager: proxy %s failure %d/%d.", self._safe_url(proxy_url), state.failures, _MAX_FAILURES)

    def mark_success(self, proxy_url: str) -> None:
        """Reset failure counter for this proxy."""
        state = self._find(proxy_url)
        if state:
            state.failures = 0
            state.cooldown_until = 0.0

    def as_requests_dict(self, proxy_url: str) -> Dict[str, str]:
        """Format for requests / cloudscraper: {"http": url, "https": url}."""
        return {"http": proxy_url, "https": proxy_url}

    def as_playwright_dict(self, proxy_url: str) -> Dict:
        """
        Format for Playwright launch_persistent_context(proxy=...).
        Extracts credentials from the URL if present.
        """
        parsed = urlparse(proxy_url)
        result: Dict = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
        if parsed.username:
            result["username"] = parsed.username
        if parsed.password:
            result["password"] = parsed.password
        return result

    def status(self) -> List[Dict]:
        """Return pool status for admin UI / debugging."""
        now = time.time()
        return [
            {
                "proxy": self._safe_url(p.url),
                "failures": p.failures,
                "cooling_down": p.cooldown_until > now,
                "ready_in_s": max(0.0, p.cooldown_until - now),
            }
            for p in self._pool
        ]

    # ------------------------------------------------------------------ #
    # Internals                                                            #
    # ------------------------------------------------------------------ #

    def _find(self, url: str) -> Optional[_ProxyState]:
        for p in self._pool:
            if p.url == url:
                return p
        return None

    @staticmethod
    def _safe_url(url: str) -> str:
        """Return URL with password masked."""
        try:
            parsed = urlparse(url)
            if parsed.password:
                return url.replace(parsed.password, "***")
        except Exception:
            pass
        return url
