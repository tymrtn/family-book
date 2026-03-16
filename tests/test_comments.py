"""Tests for Moment Comments API."""
import pytest


TYLER_ID = "tyler-000-0000-0000-000000000002"
MEMBER_ID = "member-00-0000-0000-000000000005"


@pytest.fixture
async def moment_id(admin_client):
    """Create a moment and return its ID."""
    resp = await admin_client.post("/api/moments", json={
        "kind": "text",
        "body": "A moment for comments",
    })
    return resp.json()["id"]


class TestComments:
    """POST, GET, DELETE /api/moments/{id}/comments"""

    async def test_create_comment(self, admin_client, moment_id):
        resp = await admin_client.post(
            f"/api/moments/{moment_id}/comments",
            json={"body": "Great post!"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["body"] == "Great post!"
        assert body["person_id"] == TYLER_ID
        assert body["person_name"] == "Tyler Martin"
        assert body["moment_id"] == moment_id

    async def test_create_comment_requires_auth(self, client):
        resp = await client.post(
            "/api/moments/some-id/comments",
            json={"body": "Nope"},
        )
        assert resp.status_code == 401

    async def test_create_comment_on_nonexistent_moment(self, admin_client):
        resp = await admin_client.post(
            "/api/moments/nonexistent/comments",
            json={"body": "No moment"},
        )
        assert resp.status_code == 404

    async def test_list_comments(self, admin_client, moment_id):
        await admin_client.post(
            f"/api/moments/{moment_id}/comments",
            json={"body": "Comment 1"},
        )
        await admin_client.post(
            f"/api/moments/{moment_id}/comments",
            json={"body": "Comment 2"},
        )

        resp = await admin_client.get(f"/api/moments/{moment_id}/comments")
        assert resp.status_code == 200
        comments = resp.json()
        assert len(comments) >= 2
        assert comments[0]["body"] == "Comment 1"
        assert comments[1]["body"] == "Comment 2"

    async def test_list_comments_on_nonexistent_moment(self, admin_client):
        resp = await admin_client.get("/api/moments/nonexistent/comments")
        assert resp.status_code == 404

    async def test_delete_own_comment(self, admin_client, moment_id):
        create_resp = await admin_client.post(
            f"/api/moments/{moment_id}/comments",
            json={"body": "Delete me"},
        )
        comment_id = create_resp.json()["id"]

        resp = await admin_client.delete(f"/api/moments/comments/{comment_id}")
        assert resp.status_code == 204

    async def test_member_cannot_delete_others_comment(self, admin_client, member_client, moment_id):
        # Admin creates a comment
        create_resp = await admin_client.post(
            f"/api/moments/{moment_id}/comments",
            json={"body": "Admin's comment"},
        )
        comment_id = create_resp.json()["id"]

        # Member tries to delete
        resp = await member_client.delete(f"/api/moments/comments/{comment_id}")
        assert resp.status_code == 403

    async def test_admin_can_delete_any_comment(self, admin_client, member_client, moment_id):
        # Member creates a comment
        create_resp = await member_client.post(
            f"/api/moments/{moment_id}/comments",
            json={"body": "Member's comment"},
        )
        comment_id = create_resp.json()["id"]

        # Admin deletes it
        resp = await admin_client.delete(f"/api/moments/comments/{comment_id}")
        assert resp.status_code == 204

    async def test_delete_nonexistent_comment(self, admin_client):
        resp = await admin_client.delete("/api/moments/comments/nonexistent")
        assert resp.status_code == 404

    async def test_comment_count_on_moment_card(self, admin_client, moment_id):
        await admin_client.post(
            f"/api/moments/{moment_id}/comments",
            json={"body": "Comment 1"},
        )
        await admin_client.post(
            f"/api/moments/{moment_id}/comments",
            json={"body": "Comment 2"},
        )

        resp = await admin_client.get(f"/api/moments/{moment_id}")
        assert resp.json()["comment_count"] == 2
