import asyncio
import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.services.leaderboard_mapper import encode_player_tag

logger = logging.getLogger(__name__)


class ClashRoyaleAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ClashRoyaleClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        max_retries: int = 5,
    ) -> None:
        self.api_key = api_key or settings.clash_royale_api_key
        self.base_url = (base_url or settings.clash_royale_api_base_url).rstrip("/")
        self.max_retries = max_retries

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

    async def _request(self, method: str, path: str) -> Any:
        if not self.api_key:
            raise ClashRoyaleAPIError("CLASH_ROYALE_API_KEY is not configured")

        url = f"{self.base_url}{path}"
        attempt = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                response = await client.request(method, url, headers=self._headers())

                if response.status_code == 429:
                    attempt += 1
                    if attempt > self.max_retries:
                        raise ClashRoyaleAPIError("Rate limit exceeded after retries", 429)

                    retry_after = response.headers.get("x-ratelimit-retry-after")
                    if retry_after:
                        wait_seconds = max(float(retry_after) / 1_000_000, 0.1)
                    else:
                        wait_seconds = min(2**attempt, 30)

                    logger.warning("Rate limited (429), retrying in %.2fs (attempt %d)", wait_seconds, attempt)
                    await asyncio.sleep(wait_seconds)
                    continue

                if response.status_code >= 400:
                    raise ClashRoyaleAPIError(
                        f"API request failed: {response.status_code} {response.text}",
                        response.status_code,
                    )

                return response.json()

    async def get_cards(self) -> list[dict[str, Any]]:
        payload = await self._request("GET", "/cards")
        items = payload.get("items")
        if items is None:
            raise ClashRoyaleAPIError("Unexpected /cards response: missing 'items'")
        return items

    async def get_global_pol_players(self, *, limit: int = 100, after: str | None = None) -> dict[str, Any]:
        params: dict[str, str | int] = {"limit": limit}
        if after is not None:
            params["after"] = after
        query = urlencode(params)
        return await self._request("GET", f"/locations/global/pathoflegend/players?{query}")

    async def get_global_pol_players_top_n(self, top_n: int, page_limit: int) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        after: str | None = None

        while len(collected) < top_n:
            page_limit = min(page_limit, top_n - len(collected))
            payload = await self.get_global_pol_players(limit=page_limit, after=after)
            items = payload.get("items") or []
            if not items:
                break
            collected.extend(items)
            if len(collected) >= top_n:
                break
            paging = payload.get("paging") or {}
            cursors = paging.get("cursors") or {}
            after = cursors.get("after")
            if not after:
                break

        return collected[:top_n]

    async def get_player_battlelog(self, player_tag: str) -> list[dict[str, Any]]:
        encoded_tag = encode_player_tag(player_tag)
        payload = await self._request("GET", f"/players/{encoded_tag}/battlelog")
        if isinstance(payload, list):
            return payload
        raise ClashRoyaleAPIError("Unexpected battlelog response: expected list")
