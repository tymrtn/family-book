"""Tests for chunked upload and batch upload endpoints."""

import pytest
from io import BytesIO

from PIL import Image
from httpx import AsyncClient


def _make_jpeg(width=100, height=100) -> bytes:
    """Create a minimal JPEG for testing."""
    img = Image.new("RGB", (width, height), color="red")
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestChunkedUpload:
    async def test_init_upload(self, admin_client: AsyncClient):
        resp = await admin_client.post("/api/upload/init", json={
            "filename": "vacation.jpg",
            "mime_type": "image/jpeg",
            "file_size": 5000,
            "person_id": "alex-000-0000-0000-000000000002",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "upload_id" in data
        assert data["chunk_size"] > 0
        assert data["total_chunks"] >= 1

    async def test_init_invalid_mime(self, admin_client: AsyncClient):
        resp = await admin_client.post("/api/upload/init", json={
            "filename": "virus.exe",
            "mime_type": "application/x-msdownload",
            "file_size": 5000,
            "person_id": "alex-000-0000-0000-000000000002",
        })
        assert resp.status_code == 400

    async def test_init_file_too_large(self, admin_client: AsyncClient):
        resp = await admin_client.post("/api/upload/init", json={
            "filename": "huge.mp4",
            "mime_type": "video/mp4",
            "file_size": 600 * 1024 * 1024,  # 600 MB > 500 MB limit
            "person_id": "alex-000-0000-0000-000000000002",
        })
        assert resp.status_code == 413

    async def test_full_chunked_flow(self, admin_client: AsyncClient):
        """Init → chunks → complete → Media record created."""
        jpeg_data = _make_jpeg()

        # Init
        init_resp = await admin_client.post("/api/upload/init", json={
            "filename": "chunked_test.jpg",
            "mime_type": "image/jpeg",
            "file_size": len(jpeg_data),
            "person_id": "alex-000-0000-0000-000000000002",
        })
        assert init_resp.status_code == 200
        upload_id = init_resp.json()["upload_id"]

        # Send data in one chunk (small file)
        chunk_resp = await admin_client.patch(
            f"/api/upload/{upload_id}",
            content=jpeg_data,
            headers={"Content-Type": "application/octet-stream"},
        )
        assert chunk_resp.status_code == 200
        assert chunk_resp.json()["complete"] is True

        # Complete
        complete_resp = await admin_client.post(f"/api/upload/{upload_id}/complete")
        assert complete_resp.status_code == 200
        data = complete_resp.json()
        assert "media_id" in data
        assert data["is_duplicate"] is False
        assert data["width"] == 100
        assert data["height"] == 100

    async def test_chunked_with_trip(self, admin_client: AsyncClient):
        """Chunked upload auto-links to trip."""
        # Create trip first
        trip_resp = await admin_client.post("/api/trips", json={"name": "Upload Trip"})
        trip_id = trip_resp.json()["id"]

        jpeg_data = _make_jpeg(200, 150)

        # Init with trip_id
        init_resp = await admin_client.post("/api/upload/init", json={
            "filename": "trip_photo.jpg",
            "mime_type": "image/jpeg",
            "file_size": len(jpeg_data),
            "person_id": "alex-000-0000-0000-000000000002",
            "trip_id": trip_id,
        })
        upload_id = init_resp.json()["upload_id"]

        # Upload
        await admin_client.patch(
            f"/api/upload/{upload_id}",
            content=jpeg_data,
            headers={"Content-Type": "application/octet-stream"},
        )
        await admin_client.post(f"/api/upload/{upload_id}/complete")

        # Verify trip has the moment
        trip_resp = await admin_client.get(f"/api/trips/{trip_id}")
        assert trip_resp.json()["moment_count"] == 1

    async def test_resume_check(self, admin_client: AsyncClient):
        """HEAD request returns upload progress."""
        jpeg_data = _make_jpeg()

        init_resp = await admin_client.post("/api/upload/init", json={
            "filename": "resume_test.jpg",
            "mime_type": "image/jpeg",
            "file_size": len(jpeg_data),
            "person_id": "alex-000-0000-0000-000000000002",
        })
        upload_id = init_resp.json()["upload_id"]

        # Check before any upload
        head_resp = await admin_client.head(f"/api/upload/{upload_id}")
        assert head_resp.status_code == 200
        assert head_resp.headers["upload-offset"] == "0"


class TestBatchUpload:
    async def test_batch_single_file(self, admin_client: AsyncClient):
        jpeg_data = _make_jpeg()

        resp = await admin_client.post(
            "/api/upload/batch",
            data={"person_id": "alex-000-0000-0000-000000000002"},
            files=[("files", ("photo1.jpg", jpeg_data, "image/jpeg"))],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["completed"] == 1
        assert data["failed"] == 0
        assert len(data["media_ids"]) == 1

    async def test_batch_multiple_files(self, admin_client: AsyncClient):
        jpeg1 = _make_jpeg(100, 100)
        jpeg2 = _make_jpeg(200, 200)

        resp = await admin_client.post(
            "/api/upload/batch",
            data={"person_id": "alex-000-0000-0000-000000000002"},
            files=[
                ("files", ("photo1.jpg", jpeg1, "image/jpeg")),
                ("files", ("photo2.jpg", jpeg2, "image/jpeg")),
            ],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["completed"] == 2
        assert len(data["media_ids"]) == 2

    async def test_batch_with_trip(self, admin_client: AsyncClient):
        """Batch upload auto-links to trip."""
        trip_resp = await admin_client.post("/api/trips", json={"name": "Batch Trip"})
        trip_id = trip_resp.json()["id"]

        jpeg_data = _make_jpeg()

        resp = await admin_client.post(
            "/api/upload/batch",
            data={
                "person_id": "alex-000-0000-0000-000000000002",
                "trip_id": trip_id,
            },
            files=[("files", ("beach.jpg", jpeg_data, "image/jpeg"))],
        )
        assert resp.status_code == 200
        assert resp.json()["completed"] == 1

        # Verify trip has moment
        trip_resp = await admin_client.get(f"/api/trips/{trip_id}")
        assert trip_resp.json()["moment_count"] == 1


class TestDayByDayTimeline:
    async def test_timeline_grouped_by_day(self, admin_client: AsyncClient):
        """Timeline API returns day-grouped structure."""
        trip_resp = await admin_client.post("/api/trips", json={
            "name": "Day Test",
            "start_date": "2026-07-01",
            "end_date": "2026-07-03",
        })
        trip_id = trip_resp.json()["id"]

        # Create moments on different days
        for day, body in [("2026-07-01T10:00:00Z", "Day 1 am"), ("2026-07-01T16:00:00Z", "Day 1 pm"),
                          ("2026-07-02T12:00:00Z", "Day 2"), ("2026-07-03T09:00:00Z", "Day 3")]:
            m = await admin_client.post("/api/moments", json={
                "kind": "photo", "body": body, "occurred_at": day,
            })
            await admin_client.post(f"/api/trips/{trip_id}/moments", json={
                "moment_ids": [m.json()["id"]],
            })

        resp = await admin_client.get(f"/api/trips/{trip_id}/timeline")
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_days"] == 3
        assert data["total_moments"] == 4

        days = data["days"]
        assert days[0]["date"] == "2026-07-01"
        assert len(days[0]["moments"]) == 2
        assert days[1]["date"] == "2026-07-02"
        assert len(days[1]["moments"]) == 1
        assert days[2]["date"] == "2026-07-03"
        assert len(days[2]["moments"]) == 1

    async def test_timeline_contributor_filter(self, admin_client: AsyncClient, member_client: AsyncClient):
        """Filter timeline by contributor."""
        trip_resp = await admin_client.post("/api/trips", json={"name": "Filter Test"})
        trip_data = trip_resp.json()
        trip_id = trip_data["id"]

        # Member joins
        await member_client.get(f"/api/trips/join/{trip_data['invite_token']}")

        # Admin posts a moment
        m1 = await admin_client.post("/api/moments", json={"kind": "photo", "body": "Admin photo"})
        await admin_client.post(f"/api/trips/{trip_id}/moments", json={"moment_ids": [m1.json()["id"]]})

        # Member posts a moment
        m2 = await member_client.post("/api/moments", json={"kind": "photo", "body": "Member photo"})
        await member_client.post(f"/api/trips/{trip_id}/moments", json={"moment_ids": [m2.json()["id"]]})

        # Unfiltered: both moments
        resp = await admin_client.get(f"/api/trips/{trip_id}/timeline")
        assert resp.json()["total_moments"] == 2

        # Filter by admin only
        resp = await admin_client.get(
            f"/api/trips/{trip_id}/timeline?contributor=alex-000-0000-0000-000000000002"
        )
        assert resp.json()["total_moments"] == 1
        assert resp.json()["days"][0]["moments"][0]["body"] == "Admin photo"

    async def test_timeline_owner_attribution(self, admin_client: AsyncClient):
        """Each moment in timeline has poster_id, poster_name, poster_photo."""
        trip_resp = await admin_client.post("/api/trips", json={"name": "Attribution Test"})
        trip_id = trip_resp.json()["id"]

        m = await admin_client.post("/api/moments", json={"kind": "photo", "body": "My photo"})
        await admin_client.post(f"/api/trips/{trip_id}/moments", json={"moment_ids": [m.json()["id"]]})

        resp = await admin_client.get(f"/api/trips/{trip_id}/timeline")
        moment = resp.json()["days"][0]["moments"][0]
        assert moment["poster_id"] is not None
        assert moment["poster_name"] is not None


class TestMapContributorColors:
    async def test_map_has_contributor_colors(self, admin_client: AsyncClient):
        """Map GeoJSON includes contributor list with colors."""
        trip_resp = await admin_client.post("/api/trips", json={"name": "Color Map"})
        trip_id = trip_resp.json()["id"]

        resp = await admin_client.get(f"/api/trips/{trip_id}/map")
        data = resp.json()
        assert "contributors" in data
        assert isinstance(data["contributors"], list)


class TestTripExport:
    async def test_export_empty_trip(self, admin_client: AsyncClient):
        """Exporting an empty trip returns a valid zip."""
        trip_resp = await admin_client.post("/api/trips", json={"name": "Export Test"})
        trip_id = trip_resp.json()["id"]

        resp = await admin_client.get(f"/api/trips/{trip_id}/export?quality=original")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"


class TestRevokeInvite:
    async def test_revoke_invite_link(self, admin_client: AsyncClient, member_client: AsyncClient):
        """Revoking invite makes the token null; old token no longer works."""
        trip_resp = await admin_client.post("/api/trips", json={"name": "Revoke Test"})
        trip_data = trip_resp.json()
        trip_id = trip_data["id"]
        old_token = trip_data["invite_token"]

        # Revoke
        resp = await admin_client.delete(f"/api/trips/{trip_id}/invite")
        assert resp.status_code == 204

        # Old token should not work
        resp = await member_client.get(f"/api/trips/join/{old_token}")
        assert resp.status_code == 404
