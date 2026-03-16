"""Tests for Moment Reactions API."""
import pytest


TYLER_ID = "tyler-000-0000-0000-000000000002"
MEMBER_ID = "member-00-0000-0000-000000000005"


@pytest.fixture
async def moment_id(admin_client):
    """Create a moment and return its ID."""
    resp = await admin_client.post("/api/moments", json={
        "kind": "text",
        "body": "A moment for reactions",
    })
    return resp.json()["id"]


class TestReactions:
    """POST, DELETE /api/moments/{id}/reactions"""

    async def test_add_reaction(self, admin_client, moment_id):
        resp = await admin_client.post(
            f"/api/moments/{moment_id}/reactions",
            json={"emoji": "\u2764\ufe0f"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["emoji"] == "\u2764\ufe0f"
        assert body["count"] == 1

    async def test_reaction_requires_auth(self, client):
        resp = await client.post(
            "/api/moments/some-id/reactions",
            json={"emoji": "\u2764\ufe0f"},
        )
        assert resp.status_code == 401

    async def test_reaction_on_nonexistent_moment(self, admin_client):
        resp = await admin_client.post(
            "/api/moments/nonexistent/reactions",
            json={"emoji": "\u2764\ufe0f"},
        )
        assert resp.status_code == 404

    async def test_replace_reaction(self, admin_client, moment_id):
        # Add heart
        await admin_client.post(
            f"/api/moments/{moment_id}/reactions",
            json={"emoji": "\u2764\ufe0f"},
        )
        # Replace with laugh
        resp = await admin_client.post(
            f"/api/moments/{moment_id}/reactions",
            json={"emoji": "\U0001f602"},
        )
        assert resp.status_code == 200
        assert resp.json()["emoji"] == "\U0001f602"

        # Verify moment card shows updated reaction
        moment_resp = await admin_client.get(f"/api/moments/{moment_id}")
        reactions = moment_resp.json()["reactions"]
        assert "\u2764\ufe0f" not in reactions
        assert reactions.get("\U0001f602", 0) >= 1

    async def test_remove_reaction(self, admin_client, moment_id):
        # Add reaction
        await admin_client.post(
            f"/api/moments/{moment_id}/reactions",
            json={"emoji": "\u2764\ufe0f"},
        )

        # Remove it
        resp = await admin_client.delete(f"/api/moments/{moment_id}/reactions")
        assert resp.status_code == 204

        # Verify gone
        moment_resp = await admin_client.get(f"/api/moments/{moment_id}")
        assert moment_resp.json()["reactions"] == {}
        assert moment_resp.json()["my_reaction"] is None

    async def test_remove_nonexistent_reaction(self, admin_client, moment_id):
        resp = await admin_client.delete(f"/api/moments/{moment_id}/reactions")
        assert resp.status_code == 404

    async def test_multiple_users_react(self, admin_client, member_client, moment_id):
        # Admin reacts
        await admin_client.post(
            f"/api/moments/{moment_id}/reactions",
            json={"emoji": "\u2764\ufe0f"},
        )
        # Member reacts
        await member_client.post(
            f"/api/moments/{moment_id}/reactions",
            json={"emoji": "\u2764\ufe0f"},
        )

        # Check aggregation
        resp = await admin_client.get(f"/api/moments/{moment_id}")
        assert resp.json()["reactions"]["\u2764\ufe0f"] == 2
        assert resp.json()["my_reaction"] == "\u2764\ufe0f"

    async def test_my_reaction_shown_correctly(self, admin_client, member_client, moment_id):
        # Admin reacts with heart
        await admin_client.post(
            f"/api/moments/{moment_id}/reactions",
            json={"emoji": "\u2764\ufe0f"},
        )

        # Member sees no my_reaction
        resp = await member_client.get(f"/api/moments/{moment_id}")
        assert resp.json()["my_reaction"] is None

        # Member adds their own
        await member_client.post(
            f"/api/moments/{moment_id}/reactions",
            json={"emoji": "\U0001f602"},
        )
        resp = await member_client.get(f"/api/moments/{moment_id}")
        assert resp.json()["my_reaction"] == "\U0001f602"
