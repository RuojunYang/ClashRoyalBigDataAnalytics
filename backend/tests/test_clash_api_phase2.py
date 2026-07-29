from unittest.mock import AsyncMock, patch

import pytest

from app.services.clash_api import ClashRoyaleClient


@pytest.mark.asyncio
async def test_get_global_pol_players_top_n_pagination():
    client = ClashRoyaleClient(api_key="test-key")

    page_one = {
        "items": [{"tag": f"#P{i}", "rank": i, "eloRating": 3000 - i} for i in range(1, 3)],
        "paging": {"cursors": {"after": "cursor-1"}},
    }
    page_two = {
        "items": [{"tag": "#P3", "rank": 3, "eloRating": 2997}],
        "paging": {"cursors": {}},
    }

    with patch.object(client, "get_global_pol_players", new=AsyncMock(side_effect=[page_one, page_two])):
        items = await client.get_global_pol_players_top_n(top_n=3, page_limit=2)

    assert len(items) == 3
    assert items[0]["tag"] == "#P1"
    assert items[2]["tag"] == "#P3"
