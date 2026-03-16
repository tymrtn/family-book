"""Tests for Moments API — CRUD, feed, permissions."""
import pytest


TYLER_ID = "tyler-000-0000-0000-000000000002"
MEMBER_ID = "member-00-0000-0000-000000000005"


class TestMomentsCRUD:
    """POST, GET, PUT, DELETE /api/moments"""

    async def test_create_requires_auth(self, client):
        resp = await client.post("/api/moments", json={"kind": "text"})
        assert resp.status_code == 401

    async def test_create_text_moment(self, admin_client):
        resp = await admin_client.post("/api/moments", json={
            "kind": "text",
            "body": "Hello family!",
            "person_id": TYLER_ID,
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["kind"] == "text"
        assert body["body"] == "Hello family!"
        assert body["poster"]["id"] == TYLER_ID
        assert body["about"]["id"] == TYLER_ID
        assert body["reactions"] == {}
        assert body["comment_count"] == 0

    async def test_create_moment_defaults_person_to_current_user(self, admin_client):
        resp = await admin_client.post("/api/moments", json={
            "kind": "text",
            "body": "Auto person_id",
        })
        assert resp.status_code == 201
        assert resp.json()["about"]["id"] == TYLER_ID

    async def test_create_moment_with_media_ids(self, admin_client):
        resp = await admin_client.post("/api/moments", json={
            "kind": "photo",
            "body": "With photos",
            "media_ids": ["fake-media-id-1"],
        })
        assert resp.status_code == 201
        assert resp.json()["media"] == []  # fake ID, no media found

    async def test_create_moment_bad_person(self, admin_client):
        resp = await admin_client.post("/api/moments", json={
            "kind": "text",
            "person_id": "nonexistent",
        })
        assert resp.status_code == 400

    async def test_get_moment(self, admin_client):
        create_resp = await admin_client.post("/api/moments", json={
            "kind": "text",
            "body": "Get me",
        })
        moment_id = create_resp.json()["id"]

        resp = await admin_client.get(f"/api/moments/{moment_id}")
        assert resp.status_code == 200
        assert resp.json()["body"] == "Get me"

    async def test_get_nonexistent_moment(self, admin_client):
        resp = await admin_client.get("/api/moments/nonexistent")
        assert resp.status_code == 404

    async def test_update_moment(self, admin_client):
        create_resp = await admin_client.post("/api/moments", json={
            "kind": "text",
            "body": "Original",
        })
        moment_id = create_resp.json()["id"]

        resp = await admin_client.put(f"/api/moments/{moment_id}", json={
            "body": "Edited",
        })
        assert resp.status_code == 200
        assert resp.json()["body"] == "Edited"

    async def test_delete_moment_by_poster(self, admin_client):
        create_resp = await admin_client.post("/api/moments", json={
            "kind": "text",
            "body": "Delete me",
        })
        moment_id = create_resp.json()["id"]

        resp = await admin_client.delete(f"/api/moments/{moment_id}")
        assert resp.status_code == 204

        resp2 = await admin_client.get(f"/api/moments/{moment_id}")
        assert resp2.status_code == 404

    async def test_delete_nonexistent_moment(self, admin_client):
        resp = await admin_client.delete("/api/moments/nonexistent")
        assert resp.status_code == 404


class TestMomentsFeed:
    """GET /api/moments — feed with filtering and pagination."""

    async def test_feed_requires_auth(self, client):
        resp = await client.get("/api/moments")
        assert resp.status_code == 401

    async def test_feed_returns_moments(self, admin_client):
        await admin_client.post("/api/moments", json={
            "kind": "text", "body": "Feed item 1",
        })
        await admin_client.post("/api/moments", json={
            "kind": "text", "body": "Feed item 2",
        })

        resp = await admin_client.get("/api/moments")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 2

    async def test_feed_pagination_limit(self, admin_client):
        for i in range(5):
            await admin_client.post("/api/moments", json={
                "kind": "text", "body": f"Item {i}",
            })

        resp = await admin_client.get("/api/moments?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_feed_filter_by_kind(self, admin_client):
        await admin_client.post("/api/moments", json={
            "kind": "text", "body": "Text moment",
        })
        await admin_client.post("/api/moments", json={
            "kind": "milestone", "body": "Milestone", "milestone_type": "birthday",
        })

        resp = await admin_client.get("/api/moments?kind=milestone")
        assert resp.status_code == 200
        for item in resp.json():
            assert item["kind"] == "milestone"

    async def test_feed_filter_by_person(self, admin_client):
        await admin_client.post("/api/moments", json={
            "kind": "text", "body": "Tyler's moment",
            "person_id": TYLER_ID,
        })

        resp = await admin_client.get(f"/api/moments?person={TYLER_ID}")
        assert resp.status_code == 200
        for item in resp.json():
            assert item["about"]["id"] == TYLER_ID


class TestMomentsPermissions:
    """Permission checks for moment operations."""

    async def test_member_cannot_delete_others_moment(self, admin_client, member_client):
        # Admin creates a moment
        create_resp = await admin_client.post("/api/moments", json={
            "kind": "text", "body": "Admin's moment",
        })
        moment_id = create_resp.json()["id"]

        # Member tries to delete it
        resp = await member_client.delete(f"/api/moments/{moment_id}")
        assert resp.status_code == 403

    async def test_member_cannot_edit_others_moment(self, admin_client, member_client):
        create_resp = await admin_client.post("/api/moments", json={
            "kind": "text", "body": "Admin's moment",
        })
        moment_id = create_resp.json()["id"]

        resp = await member_client.put(f"/api/moments/{moment_id}", json={
            "body": "Hacked",
        })
        assert resp.status_code == 403

    async def test_hidden_moment_not_visible_to_member(self, admin_client, member_client):
        create_resp = await admin_client.post("/api/moments", json={
            "kind": "text", "body": "Secret",
            "visibility": "hidden",
        })
        moment_id = create_resp.json()["id"]

        resp = await member_client.get(f"/api/moments/{moment_id}")
        assert resp.status_code == 403
