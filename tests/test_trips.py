"""Tests for Trip Albums feature — CRUD, invite flow, timeline, map."""

import pytest
from datetime import datetime, timezone

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.moments import Moment
from app.models.media import Media
from app.models.trips import Trip, TripParticipant, TripMoment


# ─── CRUD ─────────────────────────────────────────────────────────

class TestTripCRUD:
    async def test_create_trip(self, admin_client: AsyncClient):
        resp = await admin_client.post("/api/trips", json={
            "name": "Summer in Mallorca",
            "description": "Family beach vacation",
            "start_date": "2026-07-01",
            "end_date": "2026-07-15",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Summer in Mallorca"
        assert data["description"] == "Family beach vacation"
        assert data["start_date"] == "2026-07-01"
        assert data["end_date"] == "2026-07-15"
        assert data["participant_count"] == 1  # Creator auto-added
        assert data["invite_token"] is not None
        assert data["creator_name"] is not None

    async def test_create_trip_minimal(self, admin_client: AsyncClient):
        resp = await admin_client.post("/api/trips", json={
            "name": "Quick Weekend",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Quick Weekend"
        assert data["start_date"] is None

    async def test_list_trips(self, admin_client: AsyncClient):
        # Create two trips
        await admin_client.post("/api/trips", json={"name": "Trip A"})
        await admin_client.post("/api/trips", json={"name": "Trip B"})

        resp = await admin_client.get("/api/trips")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2
        names = [t["name"] for t in data]
        assert "Trip A" in names
        assert "Trip B" in names

    async def test_get_trip(self, admin_client: AsyncClient):
        create_resp = await admin_client.post("/api/trips", json={"name": "Get Me"})
        trip_id = create_resp.json()["id"]

        resp = await admin_client.get(f"/api/trips/{trip_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Me"

    async def test_get_trip_404(self, admin_client: AsyncClient):
        resp = await admin_client.get("/api/trips/nonexistent-id")
        assert resp.status_code == 404

    async def test_update_trip(self, admin_client: AsyncClient):
        create_resp = await admin_client.post("/api/trips", json={"name": "Original"})
        trip_id = create_resp.json()["id"]

        resp = await admin_client.put(f"/api/trips/{trip_id}", json={
            "name": "Updated Name",
            "description": "New description",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"
        assert resp.json()["description"] == "New description"

    async def test_delete_trip(self, admin_client: AsyncClient):
        create_resp = await admin_client.post("/api/trips", json={"name": "Delete Me"})
        trip_id = create_resp.json()["id"]

        resp = await admin_client.delete(f"/api/trips/{trip_id}")
        assert resp.status_code == 204

        resp = await admin_client.get(f"/api/trips/{trip_id}")
        assert resp.status_code == 404

    async def test_unauthenticated_create_trip(self, client: AsyncClient):
        resp = await client.post("/api/trips", json={"name": "No Auth"})
        assert resp.status_code == 401


# ─── Participants ─────────────────────────────────────────────────

class TestParticipants:
    async def test_creator_is_organizer(self, admin_client: AsyncClient):
        create_resp = await admin_client.post("/api/trips", json={"name": "My Trip"})
        trip_id = create_resp.json()["id"]

        resp = await admin_client.get(f"/api/trips/{trip_id}/participants")
        assert resp.status_code == 200
        participants = resp.json()
        assert len(participants) == 1
        assert participants[0]["role"] == "organizer"

    async def test_member_cannot_edit_trip(self, admin_client: AsyncClient, member_client: AsyncClient):
        create_resp = await admin_client.post("/api/trips", json={"name": "Admin Trip"})
        trip_id = create_resp.json()["id"]

        # Member tries to update — not an organizer
        resp = await member_client.put(f"/api/trips/{trip_id}", json={"name": "Hacked"})
        assert resp.status_code == 403


# ─── Invite Flow ──────────────────────────────────────────────────

class TestInviteFlow:
    async def test_generate_invite(self, admin_client: AsyncClient):
        create_resp = await admin_client.post("/api/trips", json={"name": "Invitable"})
        trip_id = create_resp.json()["id"]

        resp = await admin_client.post(f"/api/trips/{trip_id}/invite")
        assert resp.status_code == 200
        data = resp.json()
        assert "invite_token" in data
        assert "invite_url" in data

    async def test_join_via_token(self, admin_client: AsyncClient, member_client: AsyncClient):
        # Admin creates trip
        create_resp = await admin_client.post("/api/trips", json={"name": "Join Me"})
        trip_data = create_resp.json()
        trip_id = trip_data["id"]
        invite_token = trip_data["invite_token"]

        # Member joins via token
        resp = await member_client.get(f"/api/trips/join/{invite_token}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Joined trip successfully"
        assert data["trip_id"] == trip_id

        # Verify participant was added
        resp = await admin_client.get(f"/api/trips/{trip_id}/participants")
        participants = resp.json()
        assert len(participants) == 2

        # Find the member participant
        member_p = [p for p in participants if p["role"] == "contributor"]
        assert len(member_p) == 1

    async def test_join_already_member(self, admin_client: AsyncClient, member_client: AsyncClient):
        create_resp = await admin_client.post("/api/trips", json={"name": "Already In"})
        trip_data = create_resp.json()
        invite_token = trip_data["invite_token"]

        # Join first time
        await member_client.get(f"/api/trips/join/{invite_token}")

        # Join again
        resp = await member_client.get(f"/api/trips/join/{invite_token}")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Already a participant"

    async def test_join_invalid_token(self, member_client: AsyncClient):
        resp = await member_client.get("/api/trips/join/bogus-token")
        assert resp.status_code == 404

    async def test_refresh_invite_link(self, admin_client: AsyncClient):
        create_resp = await admin_client.post("/api/trips", json={"name": "Refresh Link"})
        trip_data = create_resp.json()
        trip_id = trip_data["id"]
        old_token = trip_data["invite_token"]

        resp = await admin_client.post(f"/api/trips/{trip_id}/invite")
        new_token = resp.json()["invite_token"]
        assert new_token != old_token


# ─── Moments ─────────────────────────────────────────────────────

class TestTripMoments:
    async def _create_moment(self, client: AsyncClient) -> str:
        resp = await client.post("/api/moments", json={
            "kind": "photo",
            "body": "Test photo",
        })
        assert resp.status_code == 201
        return resp.json()["id"]

    async def test_add_moments_to_trip(self, admin_client: AsyncClient):
        # Create trip
        create_resp = await admin_client.post("/api/trips", json={"name": "Photo Trip"})
        trip_id = create_resp.json()["id"]

        # Create moments
        m1 = await self._create_moment(admin_client)
        m2 = await self._create_moment(admin_client)

        # Add moments to trip
        resp = await admin_client.post(f"/api/trips/{trip_id}/moments", json={
            "moment_ids": [m1, m2],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["added"] == 2

    async def test_add_duplicate_moment(self, admin_client: AsyncClient):
        create_resp = await admin_client.post("/api/trips", json={"name": "Dupe Test"})
        trip_id = create_resp.json()["id"]

        m1 = await self._create_moment(admin_client)

        # Add once
        await admin_client.post(f"/api/trips/{trip_id}/moments", json={"moment_ids": [m1]})

        # Add again — should be idempotent
        resp = await admin_client.post(f"/api/trips/{trip_id}/moments", json={"moment_ids": [m1]})
        assert resp.json()["added"] == 0

    async def test_remove_moment_from_trip(self, admin_client: AsyncClient):
        create_resp = await admin_client.post("/api/trips", json={"name": "Remove Test"})
        trip_id = create_resp.json()["id"]

        m1 = await self._create_moment(admin_client)
        await admin_client.post(f"/api/trips/{trip_id}/moments", json={"moment_ids": [m1]})

        resp = await admin_client.delete(f"/api/trips/{trip_id}/moments/{m1}")
        assert resp.status_code == 204

    async def test_contributor_can_add_moments(self, admin_client: AsyncClient, member_client: AsyncClient):
        # Admin creates trip
        create_resp = await admin_client.post("/api/trips", json={"name": "Contrib Test"})
        trip_data = create_resp.json()
        trip_id = trip_data["id"]
        invite_token = trip_data["invite_token"]

        # Member joins
        await member_client.get(f"/api/trips/join/{invite_token}")

        # Member creates and adds a moment
        m1 = await self._create_moment(member_client)
        resp = await member_client.post(f"/api/trips/{trip_id}/moments", json={
            "moment_ids": [m1],
        })
        assert resp.status_code == 200
        assert resp.json()["added"] == 1

    async def test_viewer_cannot_add_moments(self, admin_client: AsyncClient, member_client: AsyncClient):
        create_resp = await admin_client.post("/api/trips", json={"name": "Viewer Test"})
        trip_id = create_resp.json()["id"]

        # Member is not a participant at all — should be denied
        m1 = await self._create_moment(member_client)
        resp = await member_client.post(f"/api/trips/{trip_id}/moments", json={
            "moment_ids": [m1],
        })
        assert resp.status_code == 403


# ─── Timeline ────────────────────────────────────────────────────

class TestTimeline:
    async def test_timeline_returns_moments(self, admin_client: AsyncClient):
        create_resp = await admin_client.post("/api/trips", json={
            "name": "Timeline Trip",
            "start_date": "2026-07-01",
            "end_date": "2026-07-15",
        })
        trip_id = create_resp.json()["id"]

        # Create and add moments
        m1_resp = await admin_client.post("/api/moments", json={
            "kind": "photo",
            "body": "Day 1 photo",
            "occurred_at": "2026-07-02T10:00:00Z",
        })
        m2_resp = await admin_client.post("/api/moments", json={
            "kind": "photo",
            "body": "Day 3 photo",
            "occurred_at": "2026-07-04T14:00:00Z",
        })

        m1_id = m1_resp.json()["id"]
        m2_id = m2_resp.json()["id"]

        await admin_client.post(f"/api/trips/{trip_id}/moments", json={
            "moment_ids": [m1_id, m2_id],
        })

        # Get timeline (now returns day-grouped structure)
        resp = await admin_client.get(f"/api/trips/{trip_id}/timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_moments"] == 2
        assert data["total_days"] == 2
        # Days should be chronological
        assert data["days"][0]["moments"][0]["body"] == "Day 1 photo"
        assert data["days"][1]["moments"][0]["body"] == "Day 3 photo"

    async def test_empty_timeline(self, admin_client: AsyncClient):
        create_resp = await admin_client.post("/api/trips", json={"name": "Empty Trip"})
        trip_id = create_resp.json()["id"]

        resp = await admin_client.get(f"/api/trips/{trip_id}/timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_moments"] == 0
        assert data["days"] == []


# ─── Map (GeoJSON) ───────────────────────────────────────────────

class TestMap:
    async def test_map_returns_geojson(self, admin_client: AsyncClient):
        create_resp = await admin_client.post("/api/trips", json={"name": "Map Trip"})
        trip_id = create_resp.json()["id"]

        resp = await admin_client.get(f"/api/trips/{trip_id}/map")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"
        assert isinstance(data["features"], list)

    async def test_map_empty_trip(self, admin_client: AsyncClient):
        create_resp = await admin_client.post("/api/trips", json={"name": "No Photos"})
        trip_id = create_resp.json()["id"]

        resp = await admin_client.get(f"/api/trips/{trip_id}/map")
        assert resp.status_code == 200
        assert resp.json()["features"] == []


# ─── Auto-suggest ────────────────────────────────────────────────

class TestAutoSuggest:
    async def test_suggest_trip_for_moment(self, admin_client: AsyncClient):
        # Create a trip with date range
        await admin_client.post("/api/trips", json={
            "name": "July Vacation",
            "start_date": "2026-07-01",
            "end_date": "2026-07-15",
        })

        # Create a moment within that date range
        m_resp = await admin_client.post("/api/moments", json={
            "kind": "photo",
            "body": "Beach day",
            "occurred_at": "2026-07-05T12:00:00Z",
        })
        moment_id = m_resp.json()["id"]

        resp = await admin_client.get(f"/api/trips/suggest/{moment_id}")
        assert resp.status_code == 200
        suggestions = resp.json()["suggestions"]
        assert len(suggestions) >= 1
        assert any(s["trip_name"] == "July Vacation" for s in suggestions)

    async def test_no_suggestion_outside_range(self, admin_client: AsyncClient):
        await admin_client.post("/api/trips", json={
            "name": "August Trip",
            "start_date": "2026-08-01",
            "end_date": "2026-08-15",
        })

        m_resp = await admin_client.post("/api/moments", json={
            "kind": "photo",
            "body": "June photo",
            "occurred_at": "2026-06-15T12:00:00Z",
        })
        moment_id = m_resp.json()["id"]

        resp = await admin_client.get(f"/api/trips/suggest/{moment_id}")
        suggestions = resp.json()["suggestions"]
        assert not any(s["trip_name"] == "August Trip" for s in suggestions)

    async def test_suggest_excludes_already_assigned(self, admin_client: AsyncClient):
        create_resp = await admin_client.post("/api/trips", json={
            "name": "Assigned Trip",
            "start_date": "2026-07-01",
            "end_date": "2026-07-31",
        })
        trip_id = create_resp.json()["id"]

        m_resp = await admin_client.post("/api/moments", json={
            "kind": "photo",
            "body": "Assigned photo",
            "occurred_at": "2026-07-10T12:00:00Z",
        })
        moment_id = m_resp.json()["id"]

        # Add to trip
        await admin_client.post(f"/api/trips/{trip_id}/moments", json={
            "moment_ids": [moment_id],
        })

        # Suggest should exclude this trip
        resp = await admin_client.get(f"/api/trips/suggest/{moment_id}")
        suggestions = resp.json()["suggestions"]
        assert not any(s["trip_name"] == "Assigned Trip" for s in suggestions)


# ─── Full invite flow (E2E-ish) ──────────────────────────────────

class TestFullInviteFlow:
    async def test_create_invite_join_upload_verify(
        self, admin_client: AsyncClient, member_client: AsyncClient
    ):
        """Full flow: create trip → invite → join → upload → verify in timeline."""
        # 1. Admin creates trip
        create_resp = await admin_client.post("/api/trips", json={
            "name": "Family Reunion 2026",
            "start_date": "2026-08-01",
            "end_date": "2026-08-07",
        })
        assert create_resp.status_code == 201
        trip_data = create_resp.json()
        trip_id = trip_data["id"]
        invite_token = trip_data["invite_token"]

        # 2. Member joins via invite token
        join_resp = await member_client.get(f"/api/trips/join/{invite_token}")
        assert join_resp.status_code == 200
        assert join_resp.json()["trip_id"] == trip_id

        # 3. Member creates a moment (simulating photo upload)
        moment_resp = await member_client.post("/api/moments", json={
            "kind": "photo",
            "body": "Arrived at the reunion!",
            "occurred_at": "2026-08-01T18:00:00Z",
        })
        assert moment_resp.status_code == 201
        moment_id = moment_resp.json()["id"]

        # 4. Member adds moment to trip
        add_resp = await member_client.post(f"/api/trips/{trip_id}/moments", json={
            "moment_ids": [moment_id],
        })
        assert add_resp.status_code == 200
        assert add_resp.json()["added"] == 1

        # 5. Admin sees the moment in timeline (day-grouped)
        timeline_resp = await admin_client.get(f"/api/trips/{trip_id}/timeline")
        assert timeline_resp.status_code == 200
        timeline = timeline_resp.json()
        assert timeline["total_moments"] == 1
        assert timeline["days"][0]["moments"][0]["body"] == "Arrived at the reunion!"

        # 6. Verify participant counts
        trip_resp = await admin_client.get(f"/api/trips/{trip_id}")
        assert trip_resp.json()["participant_count"] == 2
        assert trip_resp.json()["moment_count"] == 1
