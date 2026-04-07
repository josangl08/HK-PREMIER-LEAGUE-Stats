# ABOUTME: Playwright-based Transfermarkt extractor that bypasses AWS WAF using a real browser with stealth.
# ABOUTME: Drop-in replacement for TransfermarktExtractor — same public API, overrides _make_request only.

from __future__ import annotations

import logging
import random
import time
from pathlib import Path
from typing import Dict, Optional, Sequence

from bs4 import BeautifulSoup
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
from playwright_stealth import Stealth

from data.extractors.transfermarkt_extractor import TransfermarktExtractor
from utils.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)

# Persistent browser profile dir — keeps cookies and local storage across runs.
_BROWSER_PROFILE_DIR = Path("data/cache/playwright_profile")

_STEALTH = Stealth(
    navigator_webdriver=True,
    navigator_languages=True,
    navigator_platform=True,
    navigator_user_agent=True,
    navigator_vendor=True,
    chrome_app=True,
    chrome_csi=True,
    chrome_load_times=True,
    webgl_vendor=True,
    hairline=True,
)


class TransfermarktPlaywrightExtractor(TransfermarktExtractor):
    """
    Uses a real Chromium browser (headless) with playwright-stealth to bypass
    Transfermarkt's AWS WAF human-verification challenges.

    Inherits all parsing logic from TransfermarktExtractor.
    Only _make_request is overridden — everything else (get_match_history,
    search_player_by_name, etc.) works identically.
    """

    def __init__(self, cache_dir: str = "data/cache", proxy_manager: Optional[ProxyManager] = None):
        super().__init__(cache_dir=cache_dir, proxy_manager=proxy_manager)
        self._pw = None          # sync_playwright() context manager
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._pending_cookies: list[Dict] = []  # cookies to inject after launch
        self._active_proxy: Optional[str] = None  # proxy used by current browser session

    # ------------------------------------------------------------------ #
    # Browser lifecycle                                                    #
    # ------------------------------------------------------------------ #

    def _ensure_browser(self, proxy_url: Optional[str] = None) -> Page:
        """Lazily launch browser and return the shared page."""
        if self._page is not None and proxy_url == self._active_proxy:
            return self._page
        # Proxy changed or first launch — (re)start browser.
        if self._page is not None:
            self._teardown_browser()

        _BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self._active_proxy = proxy_url

        self._pw = sync_playwright().start()
        launch_kwargs: Dict = dict(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
            user_agent=random.choice([
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            ]),
            locale="en-GB",
            timezone_id="Asia/Hong_Kong",
            viewport={"width": 1280, "height": 800},
            java_script_enabled=True,
        )
        if proxy_url:
            launch_kwargs["proxy"] = self.proxy_manager.as_playwright_dict(proxy_url)
            logger.info("TransfermarktPlaywrightExtractor: launching with proxy.")

        # Persistent context keeps cookies and storage across requests.
        self._context = self._pw.chromium.launch_persistent_context(
            str(_BROWSER_PROFILE_DIR), **launch_kwargs
        )

        # Inject stealth scripts into every new page.
        _STEALTH.apply_stealth_sync(self._context)

        # Inject any cookies that were loaded via load_cookie_jar().
        if self._pending_cookies:
            self._inject_cookies(self._pending_cookies)
            self._pending_cookies = []

        self._page = self._context.new_page()
        logger.info("TransfermarktPlaywrightExtractor: browser launched (headless Chromium + stealth).")
        return self._page

    def _teardown_browser(self) -> None:
        """Close browser without stopping playwright (used before proxy rotation)."""
        try:
            if self._page:
                self._page.close()
            if self._context:
                self._context.close()
            if self._pw:
                self._pw.stop()
        except Exception as exc:
            logger.debug("Browser teardown error: %s", exc)
        finally:
            self._page = None
            self._context = None
            self._pw = None

    def _inject_cookies(self, cookie_items: list[Dict]) -> None:
        """Add cookies into the Playwright context."""
        if not self._context:
            return
        _VALID_SAME_SITE = {"Strict", "Lax", "None"}
        pw_cookies = []
        for item in cookie_items:
            name = item.get("name")
            value = item.get("value")
            if not name or value is None:
                continue
            cookie: Dict = {
                "name": name,
                "value": str(value),
                "domain": item.get("domain") or ".transfermarkt.com",
                "path": item.get("path") or "/",
            }
            if "secure" in item:
                cookie["secure"] = bool(item["secure"])
            if "httpOnly" in item:
                cookie["httpOnly"] = bool(item["httpOnly"])
            same_site = item.get("sameSite") or item.get("samesite") or item.get("same_site")
            if same_site and same_site in _VALID_SAME_SITE:
                cookie["sameSite"] = same_site
            if "expires" in item and item["expires"] is not None:
                try:
                    cookie["expires"] = float(item["expires"])
                except (TypeError, ValueError):
                    pass
            pw_cookies.append(cookie)
        if pw_cookies:
            try:
                self._context.add_cookies(pw_cookies)
                logger.debug("Injected %d cookies into Playwright context.", len(pw_cookies))
            except Exception as exc:
                logger.warning("Cookie injection failed, retrying one by one: %s", exc)
                for c in pw_cookies:
                    try:
                        self._context.add_cookies([c])
                    except Exception as e2:
                        logger.debug("Skipping invalid cookie '%s': %s", c.get("name"), e2)

    def close(self) -> None:
        """Shut down the browser cleanly."""
        try:
            self._teardown_browser()
        except Exception as exc:
            logger.warning("Error closing Playwright browser: %s", exc)

    # ------------------------------------------------------------------ #
    # Public API overrides                                                 #
    # ------------------------------------------------------------------ #

    def load_cookie_jar(self, cookie_items: Sequence[Dict]) -> None:
        """Load cookies into both CloudScraper session and Playwright context."""
        super().load_cookie_jar(cookie_items)  # keep cloudscraper in sync
        items = list(cookie_items)
        if self._context:
            self._inject_cookies(items)
        else:
            # Browser not started yet — queue for injection on first launch.
            self._pending_cookies = items

    # ------------------------------------------------------------------ #
    # Core request method — uses Playwright instead of CloudScraper        #
    # ------------------------------------------------------------------ #

    def _make_request(self, url: str) -> Optional[BeautifulSoup]:
        proxy_url = self.proxy_manager.get_proxy() if self.proxy_manager.has_proxies else None
        try:
            self._wait_rate_limit()
            page = self._ensure_browser(proxy_url)
            logger.info("Scraping (Playwright%s): %s", " +proxy" if proxy_url else "", url)
            self.last_block_type = None
            self.last_block_reason = None
            self.last_result_source = "network"
            self.last_cache_fresh = False

            response = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            self.last_http_status = response.status if response else None

            # Brief pause for JS-rendered content to settle.
            time.sleep(random.uniform(1.0, 2.0))

            html = page.content()

            protection_reason = self._detect_protection_page(html)
            if protection_reason:
                self.last_block_type = "AWS_WAF_HUMAN_VERIFICATION"
                self.last_block_reason = protection_reason
                logger.warning("Transfermarkt protection page (Playwright) for %s: %s", url, protection_reason)
                if proxy_url:
                    self.proxy_manager.mark_failure(proxy_url)
                    # Force browser restart with next proxy on the following request.
                    self._teardown_browser()
                return None

            if self.last_http_status and self.last_http_status >= 400:
                logger.error("HTTP %s for %s", self.last_http_status, url)
                if proxy_url:
                    self.proxy_manager.mark_failure(proxy_url)
                return None

            if proxy_url:
                self.proxy_manager.mark_success(proxy_url)
            return BeautifulSoup(html, "html.parser")

        except Exception as exc:
            logger.error("Playwright request failed for %s: %s", url, exc)
            self.last_http_status = None
            if proxy_url:
                self.proxy_manager.mark_failure(proxy_url)
            # Reset page so next call gets a fresh one.
            try:
                if self._page:
                    self._page.close()
                self._page = self._context.new_page() if self._context else None
            except Exception:
                pass
            return None
