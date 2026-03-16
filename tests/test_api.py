import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["db"] == "connected"
    assert isinstance(data["persons_count"], int)


@pytest.mark.asyncio
async def test_unauthenticated_persons_returns_401(client: AsyncClient):
    resp = await client.get("/api/persons")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_persons_authenticated(admin_client: AsyncClient):
    resp = await admin_client.get("/api/persons")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 3


@pytest.mark.asyncio
async def test_get_person_detail(admin_client: AsyncClient):
    resp = await admin_client.get("/api/persons/tyler-000-0000-0000-000000000002")
    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == "Tyler Martin"
    assert data["first_name"] == "Tyler"
    assert data["is_admin"] is True


@pytest.mark.asyncio
async def test_root_person_name_redacted(admin_client: AsyncClient):
    resp = await admin_client.get("/api/persons/root-0000-0000-0000-000000000001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == "Our Family"
    assert data["first_name"] is None
    assert data["last_name"] is None
    assert data["is_root"] is True


@pytest.mark.asyncio
async def test_get_person_not_found(admin_client: AsyncClient):
    resp = await admin_client.get("/api/persons/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_person_as_admin(admin_client: AsyncClient):
    resp = await admin_client.post("/api/persons", json={
        "first_name": "New",
        "last_name": "Person",
        "branch": "martin",
        "residence_country_code": "CA",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["display_name"] == "New Person"
    assert data["branch"] == "martin"


@pytest.mark.asyncio
async def test_create_person_as_member_forbidden(member_client: AsyncClient):
    resp = await member_client.post("/api/persons", json={
        "first_name": "Sneaky",
        "last_name": "Person",
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_own_profile(member_client: AsyncClient):
    resp = await member_client.put(
        "/api/persons/member-00-0000-0000-000000000005",
        json={"bio": "Updated bio"},
    )
    assert resp.status_code == 200
    assert resp.json()["bio"] == "Updated bio"


@pytest.mark.asyncio
async def test_update_other_profile_as_member_forbidden(member_client: AsyncClient):
    resp = await member_client.put(
        "/api/persons/tyler-000-0000-0000-000000000002",
        json={"bio": "Hacked bio"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_person_as_admin(admin_client: AsyncClient):
    # Create then delete
    create_resp = await admin_client.post("/api/persons", json={
        "first_name": "Temp",
        "last_name": "Person",
    })
    person_id = create_resp.json()["id"]

    resp = await admin_client.delete(f"/api/persons/{person_id}")
    assert resp.status_code == 204

    resp = await admin_client.get(f"/api/persons/{person_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_person_as_member_forbidden(member_client: AsyncClient):
    resp = await member_client.delete("/api/persons/tyler-000-0000-0000-000000000002")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_search_persons(admin_client: AsyncClient):
    resp = await admin_client.get("/api/persons?search=Tyler")
    assert resp.status_code == 200
    data = resp.json()
    assert any(p["display_name"] == "Tyler Martin" for p in data)


@pytest.mark.asyncio
async def test_filter_by_branch(admin_client: AsyncClient):
    resp = await admin_client.get("/api/persons?branch=martin")
    assert resp.status_code == 200
    data = resp.json()
    assert all(p["branch"] == "martin" for p in data)


# --- Relationship tests ---

@pytest.mark.asyncio
async def test_create_parent_child(admin_client: AsyncClient):
    # Create a new child
    create_resp = await admin_client.post("/api/persons", json={
        "first_name": "Baby",
        "last_name": "Martin",
    })
    child_id = create_resp.json()["id"]

    resp = await admin_client.post("/api/relationships/parent-child", json={
        "parent_id": "tyler-000-0000-0000-000000000002",
        "child_id": child_id,
        "kind": "biological",
    })
    assert resp.status_code == 201
    assert resp.json()["parent_id"] == "tyler-000-0000-0000-000000000002"


@pytest.mark.asyncio
async def test_create_parent_child_self_ref_rejected(admin_client: AsyncClient):
    resp = await admin_client.post("/api/relationships/parent-child", json={
        "parent_id": "tyler-000-0000-0000-000000000002",
        "child_id": "tyler-000-0000-0000-000000000002",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_duplicate_parent_child_rejected(admin_client: AsyncClient):
    # This relationship already exists in seed
    resp = await admin_client.post("/api/relationships/parent-child", json={
        "parent_id": "tyler-000-0000-0000-000000000002",
        "child_id": "root-0000-0000-0000-000000000001",
        "kind": "biological",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_partnership(admin_client: AsyncClient):
    # Create two new people for a partnership
    r1 = await admin_client.post("/api/persons", json={"first_name": "A", "last_name": "Person"})
    r2 = await admin_client.post("/api/persons", json={"first_name": "B", "last_name": "Person"})
    id_a = r1.json()["id"]
    id_b = r2.json()["id"]

    resp = await admin_client.post("/api/relationships/partnership", json={
        "person_a_id": id_a,
        "person_b_id": id_b,
        "kind": "married",
    })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_partnership_self_ref_rejected(admin_client: AsyncClient):
    resp = await admin_client.post("/api/relationships/partnership", json={
        "person_a_id": "tyler-000-0000-0000-000000000002",
        "person_b_id": "tyler-000-0000-0000-000000000002",
    })
    assert resp.status_code == 400


# --- Tree tests ---

@pytest.mark.asyncio
async def test_tree_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/tree")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_tree_authenticated(admin_client: AsyncClient):
    resp = await admin_client.get("/api/tree")
    assert resp.status_code == 200
    data = resp.json()
    assert "root_id" in data
    assert "persons" in data
    assert "parent_child" in data
    assert "partnerships" in data
    assert data["root_id"] == "root-0000-0000-0000-000000000001"


@pytest.mark.asyncio
async def test_tree_root_name_is_redacted(admin_client: AsyncClient):
    resp = await admin_client.get("/api/tree")
    data = resp.json()
    root_persons = [p for p in data["persons"] if p["display_name"] == "Our Family"]
    assert len(root_persons) == 1


# --- Auth route tests ---

@pytest.mark.asyncio
async def test_auth_me_unauthenticated(client: AsyncClient):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_authenticated(admin_client: AsyncClient):
    resp = await admin_client.get("/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == "Tyler Martin"
    assert data["is_admin"] is True


@pytest.mark.asyncio
async def test_magic_link_request(client: AsyncClient):
    # Should always return 200 regardless of email existing
    resp = await client.post("/auth/magic-link", json={"email": "nonexistent@example.com"})
    assert resp.status_code == 200
    assert "message" in resp.json()

    resp = await client.post("/auth/magic-link", json={"email": "tyler@example.com"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_logout(admin_client: AsyncClient):
    resp = await admin_client.post("/auth/logout")
    assert resp.status_code == 200

    # After logout, me should fail
    resp = await admin_client.get("/auth/me")
    assert resp.status_code == 401
