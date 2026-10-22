"""POST /site/settings must require an admin session.

Before this fix any anonymous visitor could rename a claimed site.
"""

import pytest
from httpx import AsyncClient

from app.services.site_settings import claim_site, get_site_settings

ADMIN_ID = "alex-000-0000-0000-000000000002"


@pytest.fixture
def claimed_site():
    claim_site(title="Rivera Family Book", claimed_by=ADMIN_ID)


@pytest.mark.asyncio
async def test_anonymous_cannot_change_site_title(claimed_site, client: AsyncClient):
    resp = await client.post(
        "/site/settings",
        data={"title": "Defaced", "accent": "rose"},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    assert resp.headers["location"].startswith("/login")
    saved = get_site_settings(force_reload=True)
    assert saved.title == "Rivera Family Book"
    assert saved.accent == "forest"


@pytest.mark.asyncio
async def test_anonymous_cannot_change_title_before_claim(client: AsyncClient):
    resp = await client.post(
        "/site/settings",
        data={"title": "Defaced"},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    assert get_site_settings(force_reload=True).title is None


@pytest.mark.asyncio
async def test_member_cannot_change_site_title(claimed_site, member_client: AsyncClient):
    resp = await member_client.post("/site/settings", data={"title": "Defaced"})

    assert resp.status_code == 403
    assert get_site_settings(force_reload=True).title == "Rivera Family Book"


@pytest.mark.asyncio
async def test_admin_can_change_site_title(claimed_site, admin_client: AsyncClient):
    resp = await admin_client.post(
        "/site/settings",
        data={"title": "Rivera Family Archive", "accent": "ocean"},
    )

    assert resp.status_code == 200
    assert "Rivera Family Archive" in resp.text
    saved = get_site_settings(force_reload=True)
    assert saved.title == "Rivera Family Archive"
    assert saved.accent == "ocean"
    assert saved.state == "claimed"
    assert saved.claimed_by == ADMIN_ID


@pytest.mark.asyncio
async def test_settings_page_shows_site_form_to_admin_only(
    claimed_site,
    admin_client: AsyncClient,
    member_client: AsyncClient,
):
    admin_page = await admin_client.get("/settings")
    member_page = await member_client.get("/settings")

    assert admin_page.status_code == 200
    assert 'hx-post="/site/settings"' in admin_page.text
    assert member_page.status_code == 200
    assert 'hx-post="/site/settings"' not in member_page.text


@pytest.mark.asyncio
async def test_landing_page_has_no_site_settings_form(claimed_site, client: AsyncClient):
    resp = await client.get("/")

    assert resp.status_code == 200
    assert 'hx-post="/site/settings"' not in resp.text
