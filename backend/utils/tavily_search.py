from __future__ import annotations

import os
from typing import Any

import httpx

INCLUDE_DOMAINS = [
    "statista.com",
    "mckinsey.com",
    "bcg.com",
    "deloitte.com",
    "grandviewresearch.com",
    "marketsandmarkets.com",
    "reuters.com",
    "bloomberg.com",
    "wsj.com",
    "techcrunch.com",
    "forbes.com",
    "businessinsider.com",
    ".gov",
    "worldbank.org",
    "restaurantbusinessonline.com",
    "qsrmagazine.com",
    "nrn.com",
    "fsrmagazine.com",
]

EXCLUDE_DOMAINS = [
    "yandex.com",
    "yandex.ru",
    "tiktok.com",
    "reddit.com",
    "quora.com",
    "pinterest.com",
    "instagram.com",
    "games",
    "gaming",
    "apk",
    "app-id",
]

GARBAGE_KEYWORDS = [
    "game",
    "games",
    "yandex",
    "apk",
    "app-id",
    "avatar",
    "mds.yandex",
    "merge",
    "sandbox",
    "download",
    "play",
    "puzzle",
]

TITLE_GARBAGE = ["game", "puzzle", "random", "sandbox"]


async def tavily_search_filtered(
    query: str,
    api_key: str,
    *,
    max_results: int = 10,
    search_depth: str | None = None,
) -> list[dict[str, Any]]:
    search_depth = search_depth or os.getenv("TAVILY_SEARCH_DEPTH", "advanced")
    headers = {"Content-Type": "application/json"}
    body = {
        "api_key": api_key,
        "query": query,
        "search_depth": search_depth,
        "max_results": max_results,
        "include_domains": INCLUDE_DOMAINS,
        "exclude_domains": EXCLUDE_DOMAINS,
    }

    async with httpx.AsyncClient(timeout=40) as client:
        response = await client.post("https://api.tavily.com/search", headers=headers, json=body)
        response.raise_for_status()
        results = response.json().get("results", [])

    filtered: list[dict[str, Any]] = []
    for result in results:
        url = str(result.get("url", "")).lower()
        title = str(result.get("title", "")).lower()

        if any(kw in url for kw in GARBAGE_KEYWORDS):
            continue
        if any(kw in title for kw in TITLE_GARBAGE):
            continue

        filtered.append(result)

    return filtered[:5]
