"""/demo reads the live database without auth, so it must close once the site is claimed.

Before this fix a claimed family's people, tree and moments stayed readable
to anonymous visitors under /demo.
"""

import pytest
from httpx import AsyncClient

from app.services.site_settings import claim_site

ADMIN_ID = "alex-000-0000-0000-000000000002"
DEMO_PATHS = [
    "/demo",
    "/demo/",
    "/demo/tree",
    "/demo/api/tree",
    "/demo/people",
    f"/demo/people/{ADMIN_ID}",
    f"/demo/people/{ADMIN_ID}/card",
    "/demo/partials/people-grid",
    "/demo/partials/media-gallery",
    "/demo/partials/moments",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", DEMO_PATHS)
async def test_demo_is_closed_after_claim(path: str, client: AsyncClient):
    claim_site(title="Rivera Family Book", claimed_by=ADMIN_ID)

    resp = await client.get(path, follow_redirects=False)

    assert resp.status_code == 404
    assert "Alex" not in resp.text


@pytest.mark.asyncio
async def test_demo_is_open_before_claim(client: AsyncClient):
    resp = await client.get("/demo/people")

    assert resp.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/", "/login"])
async def test_public_pages_hide_demo_link_after_claim(path: str, client: AsyncClient):
    claim_site(title="Rivera Family Book", claimed_by=ADMIN_ID)

    resp = await client.get(path)

    assert resp.status_code == 200
    assert 'href="/demo"' not in resp.text
