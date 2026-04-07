#!/usr/bin/env python
# ABOUTME: Tests all proxies in data/proxies.txt against Transfermarkt to verify they work.
# ABOUTME: Prints status per proxy: OK / WAF-blocked / connection error.

from __future__ import annotations

import os
import sys
import time

sys.path.append(os.getcwd())

import cloudscraper
from utils.proxy_manager import ProxyManager, DEFAULT_PROXY_FILE

TM_TEST_URL = "https://www.transfermarkt.es/x/leistungsdatendetails/spieler/1044443/saison/2025/plus/1"
TIMEOUT = 15


def _check_waf(html: str) -> bool:
    text = html.lower()
    return "human verification" in text and ("awswaf" in text or "gokuprops" in text)


def main() -> None:
    pm = ProxyManager(DEFAULT_PROXY_FILE)
    if not pm.has_proxies:
        print("No proxies found in data/proxies.txt — add at least one proxy to test.")
        return

    scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "darwin"})

    print(f"Testing {len(pm._pool)} proxy/proxies against Transfermarkt...\n")
    for state in pm._pool:
        url = state.url
        safe = pm._safe_url(url)
        proxies = pm.as_requests_dict(url)
        try:
            t0 = time.time()
            resp = scraper.get(TM_TEST_URL, proxies=proxies, timeout=TIMEOUT)
            elapsed = time.time() - t0
            if _check_waf(resp.text):
                print(f"  WAF-BLOCKED  {safe}  (status={resp.status_code}, {elapsed:.1f}s)")
            elif resp.status_code == 200:
                print(f"  OK           {safe}  (status=200, {elapsed:.1f}s)")
            else:
                print(f"  HTTP-{resp.status_code}      {safe}  ({elapsed:.1f}s)")
        except Exception as exc:
            print(f"  ERROR        {safe}  — {exc}")
        time.sleep(2)

    print("\nDone.")


if __name__ == "__main__":
    main()
