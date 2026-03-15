# Family Book — Phase 1 MVP Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working private family tree web app with Facebook OAuth login, interactive D3 tree visualization, privacy-aware person cards, and Railway deployment — ready for Tyler's family to use.

**Architecture:** Python FastAPI backend serving static HTML/CSS/JS. SQLite database via SQLAlchemy ORM. Session-based auth using server-side session tokens in a DB table. Tree rendered client-side with D3.js v7, data sourced from a `/api/tree` JSON endpoint. No SPA framework — static HTML shells enhanced with vanilla JS.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic-settings, httpx, cryptography (Fernet), D3.js v7, vanilla HTML/CSS/JS, Railway (hosting + SQLite volume).

---

## Pre-Implementation: Human Actions Required Before Any Code Runs

These cannot be automated. Block implementation on resolving them first.

- [ ] **Facebook Developer App registration**
  - developers.facebook.com → Create App → Consumer type → App name: "Family Book"
  - Add "Facebook Login" product
  - Set Valid OAuth Redirect URIs: `http://localhost:8000/auth/callback` AND `https://<railway-domain>/auth/callback`
  - Copy App ID and App Secret → become `FB_APP_ID` and `FB_APP_SECRET`
  - In App Roles → Testers: add every family member who will test in dev mode (max 40 total)
  - **MVP scope:** Only request `public_profile` and `email`. `user_photos` and `user_friends` require App Review (2-4 weeks). Phase 1 works without them.

- [ ] **Identify root person**
  - Luna is the tree root. Her DB row must NOT contain her real name.
  - Store as `first_name="Our"`, `last_name="Family"`, `display_name="Our Family"`
  - Document in CLAUDE.md: "Root person's real name must never appear in code, templates, or API responses."

- [ ] **Generate stable UUIDs for the seed file**
  - Run `python -c "import uuid; [print(uuid.uuid4()) for _ in range(20)]"` once
  - Assign UUIDs to each family member and hardcode them into `data/family_tree.json`
  - These UUIDs must never change after the first production seed

- [ ] **Decide domain** — Railway auto-subdomain (`<name>.up.railway.app`) is fine for Phase 1

---

## Directory Structure

```
family-book/
│
├── CLAUDE.md                        # Dev instructions: stack, env vars, run/test/deploy commands
├── SPEC.md                          # (already exists)
├── .env.example                     # All required env vars listed, no secrets
├── .env                             # Local secrets (gitignored)
├── .gitignore
├── pyproject.toml                   # Project metadata + pinned dependencies
├── Dockerfile                       # Production container
├── railway.toml                     # Railway build + deploy config
├── alembic.ini                      # Alembic migration config
│
├── docs/
│   └── implementation-plan.md       # This file
│
├── migrations/
│   ├── env.py                       # Alembic env: imports Base, configures engine from DATABASE_URL
│   └── versions/
│       └── 20260315_001_initial.py  # Initial schema migration (date-sorted prefix)
│
├── backend/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app: lifespan, router registration, static file mounts
│   ├── config.py                    # Pydantic Settings class — all env vars, fail-fast if missing
│   ├── database.py                  # Engine, session factory, SQLite startup pragmas
│   ├── models.py                    # SQLAlchemy ORM: Person, Relationship, Session, ImportedAsset
│   ├── schemas.py                   # Pydantic request/response models (separate from ORM)
│   ├── auth.py                      # Session deps: get_current_user, require_auth, require_admin
│   ├── oauth.py                     # FB OAuth: build URL, exchange code, fetch profile, upsert person
│   ├── graph.py                     # BFS, relationship label computation, privacy layer calculation
│   ├── seed.py                      # CLI: load data/family_tree.json, upsert all rows idempotently
│   └── routers/
│       ├── __init__.py
│       ├── auth_routes.py           # /auth/login, /auth/callback, /auth/logout, /auth/me
│       ├── people.py                # CRUD /api/people and /api/people/{id}
│       ├── relationships.py         # CRUD /api/relationships
│       └── tree.py                  # GET /api/tree, GET /api/health
│
├── frontend/
│   ├── index.html                   # Public landing page (no JS required)
│   ├── app.html                     # Authenticated tree shell
│   ├── css/
│   │   ├── vars.css                 # All CSS custom properties: colors, spacing, type scale
│   │   ├── reset.css                # Minimal reset: box-sizing, margins, baseline
│   │   ├── layout.css               # Page shell, nav, mobile-first layout — logical properties
│   │   ├── tree.css                 # SVG container, node rings, link lines, branch colors
│   │   ├── card.css                 # Person card: bottom sheet (mobile), sidebar (tablet+)
│   │   └── landing.css              # Landing page: hero, CTA button
│   ├── js/
│   │   ├── api.js                   # Fetch wrapper: JSON parse, 401 redirect, error handling
│   │   ├── app.js                   # DOMContentLoaded: fetch /api/tree, init tree + card
│   │   ├── tree.js                  # D3.js tree: layout, nodes, links, zoom/pan
│   │   ├── card.js                  # Person card: open, populate, close, swipe-dismiss
│   │   └── vendor/
│   │       └── d3.v7.min.js         # D3 self-hosted (no CDN runtime — privacy requirement)
│   └── assets/
│       ├── favicon.ico
│       └── avatar-placeholder.svg   # Default when photo_url is null
│
├── data/
│   ├── .gitkeep                     # Keep dir in git
│   ├── family_tree.json             # Seed data: persons + relationships (committed)
│   └── photos/                      # Downloaded FB profile photos (gitignored, Railway volume)
│
└── tests/
    ├── conftest.py                  # Fixtures: in-memory SQLite, seeded DB, TestClient
    ├── test_models.py               # ORM model constraints
    ├── test_graph.py                # BFS, relationship labels, privacy layers (exhaustive)
    ├── test_oauth.py                # OAuth flow with httpx mocked
    ├── test_api_people.py           # CRUD endpoints, auth gates, privacy field gating
    ├── test_api_tree.py             # Tree endpoint shape, root name assertion, layer gating
    └── test_seed.py                 # Idempotency, is_root/is_admin invariants
```

---

## Database Schema

### Table: `persons`

Dates as ISO 8601 TEXT. Booleans as INTEGER 0/1. UUIDs as TEXT.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | TEXT | PRIMARY KEY | UUID v4 from Python |
| `first_name` | TEXT | NOT NULL | |
| `last_name` | TEXT | NOT NULL | |
| `patronymic` | TEXT | nullable | Russian/Arabic naming |
| `birth_last_name` | TEXT | nullable | Maiden name |
| `nickname` | TEXT | nullable | Shown in parentheses |
| `display_name` | TEXT | nullable | Overrides first+last in ALL UI. Root node = "Our Family". |
| `gender` | TEXT | nullable | "male", "female", or NULL → gender-neutral labels |
| `photo_url` | TEXT | nullable | Local path `/photos/<uuid>.jpg` — downloaded from FB on login |
| `birth_date` | TEXT | nullable | ISO 8601 |
| `death_date` | TEXT | nullable | Non-null = memorial mode |
| `location` | TEXT | nullable | Free text: "Madrid, Spain" |
| `country_code` | TEXT | nullable | ISO 3166-1 alpha-2: "ES", "CA", "RU" |
| `languages` | TEXT | nullable | JSON array serialized to text: `'["en","ru"]'` |
| `bio` | TEXT | nullable | 1-3 sentences |
| `branch` | TEXT | nullable | "martin", "semesock", "yuliya" — tree branch color assignment |
| `contact_whatsapp` | TEXT | nullable | Digits only, no `+` or spaces: "17785551234" |
| `contact_telegram` | TEXT | nullable | Username without @ |
| `contact_signal` | TEXT | nullable | Digits only |
| `contact_email` | TEXT | nullable | |
| `facebook_id` | TEXT | UNIQUE, nullable | FB numeric user ID |
| `facebook_token_encrypted` | TEXT | nullable | Fernet-encrypted long-lived token |
| `is_admin` | INTEGER | NOT NULL DEFAULT 0 | |
| `is_root` | INTEGER | NOT NULL DEFAULT 0 | Exactly one row = 1 |
| `privacy_override` | INTEGER | nullable | Force layer 0-5. NULL = compute from BFS. |
| `manually_added` | INTEGER | NOT NULL DEFAULT 1 | 0 = created by FB OAuth |
| `name_display_order` | TEXT | NOT NULL DEFAULT 'western' | "western" or "eastern" |
| `created_at` | TEXT | NOT NULL DEFAULT datetime('now') | |
| `updated_at` | TEXT | NOT NULL DEFAULT datetime('now') | Must be updated on every write |

**Indexes:**
- `idx_persons_facebook_id` — unique partial: WHERE `facebook_id IS NOT NULL`
- `idx_persons_country_code` on `country_code`
- `idx_persons_is_root` — partial: WHERE `is_root = 1`

---

### Table: `relationships`

Convention: for `parent_child`, `person_a` is ALWAYS the parent, `person_b` is ALWAYS the child. Enforced in app code.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | TEXT | PRIMARY KEY | UUID v4 |
| `person_a_id` | TEXT | NOT NULL, FK → persons.id ON DELETE CASCADE | |
| `person_b_id` | TEXT | NOT NULL, FK → persons.id ON DELETE CASCADE | |
| `type` | TEXT | NOT NULL, CHECK IN ('parent_child','spouse','sibling','ex_spouse') | |
| `start_date` | TEXT | nullable | Marriage date, birth date |
| `end_date` | TEXT | nullable | Divorce date |
| `status` | TEXT | NOT NULL DEFAULT 'active', CHECK IN ('active','dissolved') | |
| `created_at` | TEXT | NOT NULL DEFAULT datetime('now') | |

**Constraints:** `UNIQUE(person_a_id, person_b_id, type)`, `CHECK(person_a_id != person_b_id)`

**Indexes:** `idx_rel_person_a` on `person_a_id`, `idx_rel_person_b` on `person_b_id`

---

### Table: `sessions`

Server-side sessions — no JWTs. Cookie stores the session token, row lives in DB.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | TEXT | PRIMARY KEY | 32-byte hex: `secrets.token_hex(32)` |
| `person_id` | TEXT | NOT NULL, FK → persons.id ON DELETE CASCADE | |
| `created_at` | TEXT | NOT NULL DEFAULT datetime('now') | |
| `expires_at` | TEXT | NOT NULL | now + 30 days |
| `user_agent` | TEXT | nullable | |

**Indexes:** `idx_sessions_person_id`, `idx_sessions_expires_at`

---

### Table: `imported_assets`

Phase 1: stores raw FB OAuth profile JSON per login. Phase 2 adds photo, post, friends_list.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | TEXT | PRIMARY KEY | UUID v4 |
| `person_id` | TEXT | NOT NULL, FK → persons.id ON DELETE CASCADE | |
| `source` | TEXT | NOT NULL, CHECK IN ('facebook_oauth') | |
| `asset_type` | TEXT | NOT NULL, CHECK IN ('profile_info') | |
| `raw_data` | TEXT | NOT NULL | JSON blob |
| `imported_at` | TEXT | NOT NULL DEFAULT datetime('now') | |

**Index:** `idx_assets_person_id` on `person_id`

---

### SQLite Startup Pragmas

Run via SQLAlchemy `@event.listens_for(engine.sync_engine, "connect")` on every new connection:

1. `PRAGMA journal_mode=WAL` — better concurrent reads, safer crash recovery
2. `PRAGMA foreign_keys=ON` — SQLite disables FK enforcement by default; enables cascade deletes
3. `PRAGMA synchronous=NORMAL` — acceptable durability for this use case

---

### Seed File Format (`data/family_tree.json`)

Pre-generate all UUIDs once, hardcode them, never regenerate. Format:

```
{
  "persons": [
    {
      "id": "<stable UUID>",
      "first_name": "Our",
      "last_name": "Family",
      "display_name": "Our Family",
      "is_root": true,
      "is_admin": false,
      "manually_added": true
    },
    {
      "id": "<stable UUID>",
      "first_name": "Tyler",
      "last_name": "Martin",
      "gender": "male",
      "location": "Madrid, Spain",
      "country_code": "ES",
      "branch": "martin",
      "is_admin": true,
      "manually_added": true
    }
  ],
  "relationships": [
    {
      "id": "<stable UUID>",
      "person_a_id": "<Tyler UUID>",
      "person_b_id": "<root UUID>",
      "type": "parent_child",
      "status": "active"
    }
  ]
}
```

Minimum seed: root, Tyler, Yuliya, + 3-5 additional family members across Russia/Canada/Spain with correct relationships to make the tree and graph algorithm testable (include at least: one grandparent, one aunt or uncle, one first cousin).

---

## Task Breakdown

---

### Task 1: Project Scaffolding

**Files:** `.gitignore`, `pyproject.toml`, `.env.example`, `CLAUDE.md`, `backend/__init__.py`, `backend/main.py` (skeleton), `backend/config.py`

- [ ] `git init && git branch -M main`
- [ ] Create `.gitignore`: `.env`, `data/*.db`, `data/photos/`, `__pycache__/`, `.pytest_cache/`, `*.pyc`, `.DS_Store`, `.venv/`
- [ ] Create `pyproject.toml` with pinned deps (minor version): fastapi, uvicorn[standard], sqlalchemy, alembic, pydantic-settings, httpx, cryptography, python-multipart. Dev extras: pytest, pytest-asyncio, httpx.
- [ ] Create `.env.example` with all vars documented: `FB_APP_ID`, `FB_APP_SECRET`, `FB_REDIRECT_URI`, `ADMIN_FB_IDS`, `FERNET_KEY`, `SESSION_SECRET`, `DATABASE_URL`
- [ ] Create `backend/config.py`: Pydantic `Settings` class from pydantic-settings. All vars required — fail at import if missing. No hardcoded secrets anywhere.
- [ ] Create `backend/main.py`: bare FastAPI with lifespan (startup: create `data/photos/` if missing). Mount `/static` → `frontend/`, `/photos` → `data/photos/`. Router registration stubs.
- [ ] Write `CLAUDE.md`: stack, env var sources, local run command, test command, Railway deploy steps, SQLite path, seed command, gotchas summary.
- [ ] Create `data/.gitkeep`
- [ ] Install: `pip install -e ".[dev]"`. Verify: `python -c "import fastapi, sqlalchemy, httpx, cryptography"`
- [ ] Commit: `chore: scaffold project structure`

---

### Task 2: Database Models + Alembic Migration

**Files:** `backend/database.py`, `backend/models.py`, `alembic.ini`, `migrations/env.py`, `migrations/versions/20260315_001_initial.py`, `tests/conftest.py`, `tests/test_models.py`

- [ ] Write `backend/database.py`:
  - Async SQLAlchemy engine from `settings.DATABASE_URL`
  - Connection event listener running all three startup pragmas on every new connection
  - `get_db()` async generator for FastAPI DI
  - `create_all_for_tests()` helper used only in `tests/conftest.py` (production uses Alembic)

- [ ] Write `backend/models.py`: four SQLAlchemy 2.0 mapped classes using `DeclarativeBase` with type annotations: `Person`, `Relationship`, `AppSession`, `ImportedAsset`. Include `__repr__` on each. Add a Python `@property` on `Person` for `languages` that json.loads on get and json.dumps on set. Note: `updated_at` is managed by a SQLAlchemy session event (not `onupdate=func.now()`, which is unreliable with SQLite TEXT dates).

- [ ] Configure Alembic: `alembic init migrations`. Edit `alembic.ini` → `script_location = migrations`. Edit `migrations/env.py` → import `Base` from `backend.models`, configure URL from env.

- [ ] Generate initial migration: `alembic revision --autogenerate -m "initial_schema"`. Review the generated file carefully: all tables, columns, indexes, check constraints must be present. Manual additions often needed for partial indexes and check constraints (Alembic autogenerate misses some).

- [ ] Write `tests/conftest.py`:
  - `db` fixture: in-memory SQLite, `create_all_for_tests()`, run pragmas, yield session, rollback after each test
  - `seeded_db` fixture: uses `db`, inserts root person + Tyler (admin) + Yuliya (admin) + one grandparent + one aunt + one first cousin with all correct relationships
  - `client` fixture: `AsyncClient` against the FastAPI app with `get_db` dependency overridden to use `db`

- [ ] Write `tests/test_models.py`:
  - Test Person creation with minimal required fields succeeds
  - Test `UNIQUE(person_a_id, person_b_id, type)` raises `IntegrityError` on duplicate
  - Test `CHECK(person_a_id != person_b_id)` raises on self-relationship
  - Test `ON DELETE CASCADE`: delete a Person, their Relationship and AppSession rows disappear
  - Test `languages` property: store list, retrieve list (not raw JSON string)

- [ ] Run: `pytest tests/test_models.py -v`
- [ ] Commit: `feat(db): SQLAlchemy models, Alembic initial migration`

---

### Task 3: Seed Data + Loader

**Files:** `data/family_tree.json`, `backend/seed.py`, `tests/test_seed.py`

- [ ] Create `data/family_tree.json`. Include:
  - Root (Luna placeholder): `is_root=true`, `display_name="Our Family"`, no real name
  - Tyler: `is_admin=true`, `country_code="ES"`, `gender="male"`, `branch="martin"`
  - Yuliya: `is_admin=true`, `country_code="ES"`, `gender="female"`, `branch="yuliya"`
  - Relationships: Tyler → root (parent_child), Yuliya → root (parent_child), Tyler ↔ Yuliya (spouse)
  - 3-5 more family members with `branch` set: at least one grandparent, one aunt/uncle, one first cousin

- [ ] Write `backend/seed.py`:
  - Reads `data/family_tree.json`
  - For each person and relationship: `session.merge(Model(**row))` — upserts by PK
  - Prints: "Seeded N persons, M relationships"
  - `if __name__ == "__main__"`: block so `python -m backend.seed` works

- [ ] Write `tests/test_seed.py`:
  - Test idempotency: run seed twice, person count is identical both times
  - Test exactly one `is_root=True` person exists
  - Test Tyler and Yuliya have `is_admin=True`
  - Test root person's `display_name` equals "Our Family" (not a real child's name)
  - Test expected relationship count matches `family_tree.json`

- [ ] Run locally: `alembic upgrade head && python -m backend.seed`
- [ ] Run: `pytest tests/test_seed.py -v`
- [ ] Commit: `feat(seed): family_tree.json + idempotent seed loader`

---

### Task 4: Graph Computation Engine (TDD — tests first)

**Files:** `backend/graph.py`, `tests/test_graph.py`

Write ALL tests before any implementation. This is the most critical module.

- [ ] Write `tests/test_graph.py` — all tests should FAIL before implementation:

  **BFS distance tests:**
  - `test_bfs_root_is_zero`
  - `test_bfs_parent_is_one` (Tyler → Luna = distance 1)
  - `test_bfs_grandparent_is_two`
  - `test_bfs_aunt_via_parent_sibling` (aunt = 3 hops: up to parent, across to sibling)
  - `test_bfs_first_cousin` (distance 4: up, up, down, down via common grandparent)
  - `test_bfs_unreachable_person_absent_from_result`

  **Relationship label tests:**
  - `test_label_father` (male parent of root)
  - `test_label_mother` (female parent of root)
  - `test_label_parent_gender_neutral` (null gender → "Parent")
  - `test_label_grandfather`, `test_label_grandmother`
  - `test_label_great_grandfather`
  - `test_label_uncle`, `test_label_aunt`
  - `test_label_sibling_brother`, `test_label_sibling_sister`
  - `test_label_nephew`, `test_label_niece`
  - `test_label_first_cousin`
  - `test_label_first_cousin_once_removed_up` (person is one gen above cousin)
  - `test_label_first_cousin_once_removed_down`
  - `test_label_second_cousin`
  - `test_label_spouse_husband`, `test_label_spouse_wife`
  - `test_label_ex_spouse`
  - `test_label_no_relation_returns_graceful_string`

  **Privacy layer tests:**
  - `test_layer_root_is_zero`
  - `test_layer_admin_parent_is_one`
  - `test_layer_grandparent_is_two`
  - `test_layer_first_cousin_is_four`
  - `test_layer_ex_spouse_is_five_regardless_of_bfs`
  - `test_layer_marriage_graft` (spouse of Layer 2 person → Layer 3)
  - `test_layer_privacy_override_respected`
  - `test_layer_unreachable_is_five`

- [ ] Run: `pytest tests/test_graph.py -v` — all must FAIL

- [ ] Implement `backend/graph.py`:

  **`build_adjacency(session) → dict[str, list[tuple[str, str]]]`**

  Query all active Relationship rows. For each row, create bidirectional edges:
  - `parent_child`: add `(child_id, "child")` to parent's list; add `(parent_id, "parent")` to child's list
  - `spouse`: add `(b_id, "spouse")` to a's list and `(a_id, "spouse")` to b's list
  - `ex_spouse`: symmetric with label "ex_spouse"
  - `sibling`: symmetric with label "sibling"

  **`bfs_distance(root_id, adjacency) → dict[str, int]`**

  Standard BFS from root_id. Treats all edge types equally for distance. Returns dict of all reachable node IDs and their distances. Root = 0. Unreachable nodes are absent.

  **`get_privacy_layer(person_id, bfs_distances, session) → int`**

  Apply rules in this exact order:
  1. Fetch `Person.privacy_override` — return it if not None
  2. If `person_id` absent from `bfs_distances` → return 5
  3. If person has any `ex_spouse` relationship in DB → return 5
  4. If person has `spouse` relationship to a person at layer N → return min(N+1, 5)
  5. Otherwise: return min(bfs_distances[person_id], 5)

  **`compute_relationship_label(from_id, to_id, adjacency, persons_map) → str`**

  Algorithm:
  1. BFS from `from_id` with parent tracking to recover path to `to_id`
  2. Walk path, counting "up" hops (direction="parent") and "down" hops (direction="child")
  3. Check for direct `spouse` edge: return "Husband"/"Wife"/"Spouse" by gender
  4. Check for direct `ex_spouse` edge: return "Ex-Husband"/"Ex-Wife"/"Ex-Spouse"
  5. Apply naming table:

  | (up, down) | Male | Female | Neutral |
  |-----------|------|--------|---------|
  | (1, 0) | Father | Mother | Parent |
  | (0, 1) | Son | Daughter | Child |
  | (2, 0) | Grandfather | Grandmother | Grandparent |
  | (0, 2) | Grandson | Granddaughter | Grandchild |
  | (3, 0) | Great-Grandfather | Great-Grandmother | Great-Grandparent |
  | (N≥4, 0) | Prepend "Great-" to (N-1, 0) result | | |
  | (1, 1) | Brother | Sister | Sibling |
  | (2, 1) | Uncle | Aunt | Aunt/Uncle |
  | (1, 2) | Nephew | Niece | Niece/Nephew |
  | (2, 2) | — | — | First Cousin |
  | (3, 3) | — | — | Second Cousin |
  | (N, N) | — | — | `(N-1)th Cousin` |
  | (N, M), N≠M | — | — | `(min(N,M)-1)th Cousin, abs(N-M) times removed` |

  6. If path not found: return "No relation found"

  **`build_tree_for_d3(root_id, session) → dict`**

  - Build adjacency, run BFS from root
  - For each person: compute privacy layer, compute relationship label vs. root
  - Build hierarchical nested dict using only `parent_child` edges (BFS traversal, respecting direction: root's parents, their parents, etc. — and root's children and their descendants)
  - Apply privacy field gating in the flat `people` map: Layer 4+ → omit contacts; Layer 5 → only id, name, country_code, relationship_label, layer
  - Return `{"root": <hierarchy>, "people": <flat map>, "edges": [<spouse/sibling edges for custom link rendering>]}`

- [ ] Run: `pytest tests/test_graph.py -v` — all must PASS
- [ ] Commit: `feat(graph): BFS, relationship labels, privacy layers`

---

### Task 5: Facebook OAuth Flow

**Files:** `backend/oauth.py`, `backend/auth.py`, `backend/routers/auth_routes.py`, `tests/test_oauth.py`

- [ ] Write `tests/test_oauth.py` (httpx mocked throughout):
  - `test_build_auth_url_contains_required_params` (client_id, state, redirect_uri, scope)
  - `test_exchange_code_returns_token`
  - `test_exchange_long_lived_token_called_after_short_lived`
  - `test_fetch_profile_extracts_all_fields`
  - `test_upsert_creates_new_person_on_first_login`
  - `test_upsert_updates_existing_person_on_re_login`
  - `test_upsert_no_duplicate_rows` (run twice with same FB ID, count stays 1)
  - `test_upsert_sets_is_admin_for_admin_fb_id`
  - `test_state_mismatch_raises_value_error`
  - `test_photo_download_failure_does_not_crash_flow`

- [ ] Run: `pytest tests/test_oauth.py -v` — all FAIL

- [ ] Implement `backend/oauth.py`:

  **`build_auth_url(state)`** — construct Facebook authorization URL:
  - Base: `https://www.facebook.com/v21.0/dialog/oauth`
  - Params: `client_id`, `redirect_uri`, `state`, `scope=public_profile,email`, `response_type=code`

  **`exchange_code_for_token(code)`** — async POST to `https://graph.facebook.com/v21.0/oauth/access_token`. Returns short-lived token string.

  **`exchange_for_long_lived_token(short_token)`** — async GET to Facebook's `fb_exchange_token` endpoint. Returns long-lived token string (60 days). Call this immediately after the short-lived exchange — store only the long-lived token.

  **`fetch_facebook_profile(access_token)`** — async GET `/v21.0/me?fields=id,first_name,last_name,email,gender,picture.width(400)`. Returns dict.

  **`download_profile_photo(url, person_id)`** — async GET the photo URL, write to `data/photos/{person_id}.jpg`. Return `/photos/{person_id}.jpg` as the `photo_url` value. Log a warning and return None if download fails — don't crash the OAuth flow.

  **`encrypt_token(token)` / `decrypt_token(encrypted)`** — Fernet symmetric encryption. Key from `settings.FERNET_KEY`.

  **`upsert_person_from_fb(profile_dict, access_token, session)`** — look up by `facebook_id`, create or update Person row, download photo, encrypt and store token, save `ImportedAsset`. Check `settings.ADMIN_FB_IDS` (comma-separated) for admin assignment. Return Person.

- [ ] Implement `backend/auth.py`:

  **`create_session(person_id, user_agent, session)`** — generate 32-byte hex token, insert AppSession row (expires 30 days), return token.

  **`get_current_user(request, session)` (FastAPI dependency)** — read `family_book_session` cookie, look up AppSession by token, check `expires_at`, return Person or None.

  **`require_auth`** — depends on `get_current_user`. Raises HTTP 302 → `/` if None.

  **`require_admin`** — depends on `require_auth`. Raises HTTP 403 if `person.is_admin == False`.

- [ ] Implement `backend/routers/auth_routes.py`:

  **`GET /auth/login`**: generate CSRF state (`secrets.token_urlsafe(16)`), sign it into a 5-minute cookie using `itsdangerous.URLSafeTimedSerializer(settings.SESSION_SECRET)`, redirect to `build_auth_url(state)`.

  **`GET /auth/callback`**: read and verify state from signed cookie (CSRF) — clear cookie on any outcome; exchange code; exchange for long-lived token; fetch profile; download photo; upsert person; create session; set `family_book_session` cookie (HTTPOnly, Secure in prod, SameSite=Lax, path=/, max-age=2592000); redirect to `/app`.

  **`POST /auth/logout`**: delete AppSession row, clear `family_book_session` cookie, redirect to `/`.

  **`GET /auth/me`**: return current Person as Pydantic JSON.

- [ ] Run: `pytest tests/test_oauth.py -v` — all PASS
- [ ] Manually test: `GET /auth/login` with real FB credentials → confirms redirect to Facebook dialog
- [ ] Commit: `feat(auth): Facebook OAuth flow, session management, token encryption`

---

### Task 6: API Endpoints

**Files:** `backend/schemas.py`, `backend/routers/people.py`, `backend/routers/relationships.py`, `backend/routers/tree.py`, `tests/test_api_people.py`, `tests/test_api_tree.py`

- [ ] Write `backend/schemas.py`: Pydantic models for `PersonCreate`, `PersonUpdate`, `PersonResponse`, `RelationshipCreate`, `TreeNode`, `TreeEdge`, `TreeResponse`. `PersonResponse` fields include nullables — populate based on privacy layer in routers.

- [ ] Implement `GET /api/tree` in `backend/routers/tree.py`:
  - Requires auth
  - Calls `graph.build_tree_for_d3(settings.ROOT_PERSON_ID, session)`
  - Returns `TreeResponse`
  - Add `ROOT_PERSON_ID` to `Settings` (loaded from env or derived from seed — Tyler sets this once)

- [ ] Add `GET /api/health` (no auth): execute `SELECT 1` on DB, return `{"status": "ok"}`. Railway uses this.

- [ ] Implement people endpoints in `backend/routers/people.py`:
  - `GET /api/people`: list all persons, optional `?country_code=` filter. Privacy field gating by layer.
  - `GET /api/people/{id}`: single person, 404 if not found. Same field gating.
  - `POST /api/people` (admin): create from `PersonCreate`, return 201.
  - `PUT /api/people/{id}` (admin): update from `PersonUpdate`, return updated.
  - `DELETE /api/people/{id}` (admin): delete, cascade handles relationships, return 204.
  - `POST /api/people/{id}/photo` (admin): accept `UploadFile`, save to `data/photos/{id}.jpg`, update `photo_url`.

- [ ] Implement relationship endpoints in `backend/routers/relationships.py`:
  - `GET /api/relationships` (admin): list all.
  - `POST /api/relationships` (admin): create. Validate `person_a_id != person_b_id`. Return 409 on unique constraint violation.
  - `DELETE /api/relationships/{id}` (admin): delete, return 204.

- [ ] Write `tests/test_api_tree.py`:
  - Unauthenticated → 302
  - Authenticated → 200 with valid JSON shape
  - Root node `name` field equals "Our Family" (not a real child's name) — this test is a privacy invariant
  - Layer 5 person in nodes has no contact fields, no birth_date
  - Layer 1 person (Tyler) has all fields

- [ ] Write `tests/test_api_people.py`:
  - `GET /api/people/{id}` unauthenticated → 302
  - Layer 1 person response has all fields
  - Layer 4 person response has no contact fields
  - Non-existent ID → 404
  - Non-admin `DELETE` → 403
  - Admin `POST` creates person, `DELETE` removes them, 404 after deletion
  - Duplicate relationship `POST` → 409

- [ ] Run: `pytest tests/test_api_people.py tests/test_api_tree.py -v`
- [ ] Commit: `feat(api): tree, people, relationship endpoints with auth + privacy gating`

---

### Task 7: Frontend Templates

**Files:** `frontend/index.html`, `frontend/app.html`, `backend/main.py` (page routes)

- [ ] Add page routes to `backend/main.py` (not in routers — simple `FileResponse` returns):
  - `GET /`: if `get_current_user` returns a person → 302 to `/app`. Otherwise serve `frontend/index.html`.
  - `GET /app`: if not authenticated → 302 to `/`. Otherwise serve `frontend/app.html`.

- [ ] Write `frontend/index.html`:
  - `<!DOCTYPE html>`, `lang="en"`, `<meta name="viewport" content="width=device-width, initial-scale=1">`
  - `<meta name="theme-color" content="#2563eb">`
  - CSS: `vars.css`, `reset.css`, `layout.css`, `landing.css`
  - Zero JavaScript — the landing page must render fully without JS
  - Body: simple `<nav>` with logo text; `<main>` with:
    - Two circular trust photos (Tyler + Yuliya — use placeholder initially, replace with actual photos after seed)
    - `<h1>Family Book</h1>`
    - Tagline: 2 sentences max
    - `<a href="/auth/login" class="btn btn-primary">Connect with Facebook</a>`
    - Privacy note: "No ads. No tracking. Your data stays in our family."
  - No Google Fonts, no third-party scripts, no analytics

- [ ] Write `frontend/app.html`:
  - Same `<head>` boilerplate
  - CSS: `vars.css`, `reset.css`, `layout.css`, `tree.css`, `card.css`
  - `<nav>`: logo left, `<form action="/auth/logout" method="post"><button>Logout</button></form>` right
  - `<main id="tree-container">`:
    - `<div id="loading-indicator">` (CSS spinner, shown until tree data loads)
    - `<svg id="family-tree">` (D3 renders into this)
  - `<aside id="person-card">` with full card DOM (see person card task)
  - `<div id="person-card-backdrop">` (backdrop overlay)
  - Scripts at end of `<body>`: `vendor/d3.v7.min.js`, `api.js`, `tree.js`, `card.js`, `app.js`

- [ ] Commit: `feat(frontend): landing page + app shell HTML`

---

### Task 8: D3 Tree Visualization

**Files:** `frontend/js/tree.js`, `frontend/js/app.js`, `frontend/js/api.js`, `frontend/css/tree.css`, download `frontend/js/vendor/d3.v7.min.js`

- [ ] Download D3 v7.9.x minified JS from the D3 GitHub releases (not from CDN — self-host). Save to `frontend/js/vendor/d3.v7.min.js`.

- [ ] Write `frontend/js/api.js`:
  - `apiFetch(path, options)` wrapper: adds credentials mode, checks for 401 (redirects window to `/`), parses JSON response, throws on non-2xx with error detail.

- [ ] Write `frontend/js/app.js`:
  - `DOMContentLoaded`: show `#loading-indicator`
  - Call `apiFetch('/api/tree')`
  - Success: hide loading indicator, store `data.people` in module scope, call `initTree(data)`
  - Error: show user-friendly error message, offer "Try again" button

- [ ] Write `frontend/js/tree.js` with `initTree(data)`:

  **Hierarchy conversion:** Call `d3.hierarchy(data.root)`. The API returns a pre-built nested structure — `d3.hierarchy()` wraps it in D3's node class.

  **Layout:** `d3.tree().nodeSize([nodeW, nodeH])` where `nodeW` and `nodeH` depend on `window.innerWidth`:
  - Mobile (< 640px): nodeW=80, nodeH=120
  - Desktop (≥ 640px): nodeW=120, nodeH=160

  **SVG setup:** select `#family-tree`, get width/height from container. Create inner `<g id="tree-group">` as zoom transform target.

  **Render links first** (so nodes appear on top):
  - `parent_child` edges: `d3.linkVertical()` paths with class `link-parent-child`
  - After tree layout, iterate `data.edges` for spouse/sibling links: look up source and target x/y positions from the hierarchy node map, draw custom horizontal SVG paths with class `link-spouse` or `link-ex-spouse`

  **Render nodes:** For each hierarchy datum, append `<g class="person-node branch-{branch}" data-id="{id}">` to `#tree-group`. Inside each group:
  - `<clipPath id="clip-{id}">` containing `<circle r="{radius}">`
  - `<image>` with placeholder `href` initially, clip-path applied, centered on origin
  - `<circle class="node-ring">` with branch-class for colored stroke
  - `<text class="node-name">` below circle — first name only, truncated to ~14 chars
  - `<text class="node-relationship">` — relationship label
  - CSS class for layer: add `layer-4` or `layer-5` based on `datum.data.layer`
  - CSS class for memorial: add `is-memorial` if `datum.data.is_memorial`

  **Photo lazy loading:** Create one `IntersectionObserver` for the SVG container. When a `<image>` element enters the viewport, swap the `href` from placeholder to `datum.data.photo_url || '/assets/avatar-placeholder.svg'`.

  **Click handler:** On each node group: `d3.select(node).on("click", (event, datum) => { event.stopPropagation(); openPersonCard(datum.data.id); })`

  **Zoom + pan:**
  - `const zoom = d3.zoom().scaleExtent([0.2, 3]).on("zoom", ({transform}) => d3.select("#tree-group").attr("transform", transform))`
  - Apply to SVG: `d3.select("#family-tree").call(zoom)`
  - Auto-fit on load: compute bounding box of all nodes post-layout, derive `scale` and `translate` to center in viewport. Apply initial transform.

- [ ] Write `frontend/css/tree.css`:
  - `#tree-container`: `width: 100%; height: calc(100dvh - 56px); overflow: hidden; background: var(--color-bg); position: relative`
  - `#family-tree`: `width: 100%; height: 100%; cursor: grab; touch-action: none`
  - `#family-tree:active`: `cursor: grabbing`
  - `.person-node`: `cursor: pointer; pointer-events: all` (pointer-events required for iOS Safari)
  - `.node-ring`: `fill: none; stroke-width: 3px`
  - `.branch-martin .node-ring`: `stroke: var(--branch-martin)`, etc. for all branches
  - `.node-name`: `font-size: 12px; text-anchor: middle; fill: var(--color-text); font-family: var(--font-family)`
  - `.node-relationship`: `font-size: 10px; text-anchor: middle; fill: var(--color-text-muted)`
  - `.link-parent-child`: `fill: none; stroke: var(--color-link-line); stroke-width: 1.5px`
  - `.link-spouse`: `fill: none; stroke: var(--color-link-line); stroke-dasharray: 6 3; stroke-width: 1.5px`
  - `.link-ex-spouse`: `fill: none; stroke: var(--color-border); stroke-dasharray: 3 3; stroke-width: 1px`
  - `.layer-4`: `opacity: 0.7`; `.layer-5`: `opacity: 0.5`
  - `.is-memorial image`: `filter: grayscale(100%)`
  - `#loading-indicator`: centered, CSS spinner animation

- [ ] Manual test: run server, log in, confirm tree renders with seeded data, zoom/pan works
- [ ] Test in Chrome DevTools: iPhone SE (375px), iPad (768px), desktop (1280px)
- [ ] Commit: `feat(ui): D3 tree visualization with zoom/pan and photo lazy loading`

---

### Task 9: Person Card Component

**Files:** `frontend/js/card.js`, `frontend/css/card.css`

- [ ] Add card DOM to `frontend/app.html` (inside `<aside id="person-card">`):
  - Drag handle div (mobile only visual)
  - Close button `<button id="card-close" aria-label="Close">`
  - `<img id="card-photo" alt="">` — circle-cropped via CSS
  - `.card-memorial-badge` (hidden by default)
  - `<h2 id="card-name">`
  - `<p id="card-nickname">` (hidden if null)
  - `<p id="card-relationship">`
  - `<div class="card-location"><span id="card-flag"></span><span id="card-location-text"></span></div>`
  - `<p id="card-birthday">` (hidden if null)
  - `<div id="card-contacts">` (populated by JS)
  - `<p id="card-bio">` (hidden if null)
  - `<time id="card-updated">`

- [ ] Write `frontend/js/card.js`:

  **`openPersonCard(personId)`:**
  1. Get person from module-scope `people` map (no extra API call)
  2. Populate all DOM fields:
     - `#card-name`: `display_name || (first_name + " " + last_name)` + nickname in parens if present
     - `#card-photo src`: `photo_url || '/assets/avatar-placeholder.svg'`
     - `#card-relationship`: from `relationship_label`
     - `#card-flag`: Unicode flag emoji via Regional Indicator Symbol formula: `String.fromCodePoint(...[...code.toUpperCase()].map(c => 0x1F1E6 + c.charCodeAt(0) - 65))`
     - `#card-birthday`: if present and `layer <= 3`, format as "March 15". If admin, include year.
     - `#card-contacts`: clear, then conditionally append contact links if `layer <= 2`:
       - WhatsApp: `<a href="https://wa.me/{digits_only}" target="_blank" rel="noopener noreferrer">`
       - Telegram: `<a href="https://t.me/{username}" target="_blank" rel="noopener noreferrer">`
       - Signal: `<span>` with formatted number (no reliable deep link scheme)
     - Toggle `is-memorial` class based on `is_memorial`
  3. Show backdrop, show card (add `.open` class)
  4. Trap focus within `#person-card` — cycle Tab through focusable elements, prevent escape to rest of page
  5. Store reference to the tree node element that triggered open (for focus return on close)

  **`closePersonCard()`:**
  1. Remove `.open` from card and backdrop
  2. Remove focus trap listener
  3. Return focus to stored node element

  **Dismiss triggers:**
  - `#card-close` click
  - `#person-card-backdrop` click
  - `keydown` Escape
  - Mobile swipe-down: `touchstart` → `touchmove` → `touchend`. If `deltaY > 60px` downward, close.

- [ ] Write `frontend/css/card.css`:

  **Mobile bottom sheet:**
  - `#person-card`: `position: fixed; bottom: 0; left: 0; right: 0; height: 72dvh; background: var(--color-surface); border-radius: var(--radius-lg) var(--radius-lg) 0 0; box-shadow: var(--shadow-md); transform: translateY(110%); transition: transform 0.3s cubic-bezier(0.4,0,0.2,1); z-index: 200; overflow-y: auto; padding: var(--space-4)`
  - `#person-card.open`: `transform: translateY(0)`
  - Drag handle: `width: 40px; height: 4px; border-radius: var(--radius-full); background: var(--color-border); margin: 0 auto var(--space-4); cursor: grab`

  **Backdrop:**
  - `#person-card-backdrop`: `position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 199; display: none; backdrop-filter: blur(2px)`
  - `.open`: `display: block`

  **Photo:** `#card-photo`: `width: 120px; height: 120px; border-radius: 50%; object-fit: cover; display: block; margin: 0 auto var(--space-4)`

  **Memorial:** `.card-memorial-badge`: hidden by default. `.is-memorial .card-memorial-badge`: shown as a small badge.

  **Contact buttons:** `#card-contacts`: `display: flex; gap: var(--space-3); flex-wrap: wrap; margin-block: var(--space-4)`. `.contact-btn`: `min-height: 44px; padding: var(--space-2) var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-full); display: inline-flex; align-items: center; gap: var(--space-2); font-size: var(--text-sm)`

  **Tablet sidebar (`@media (min-width: 640px)`):**
  - `#person-card`: `position: fixed; top: 56px; right: 0; bottom: 0; left: auto; width: 360px; height: auto; border-radius: var(--radius-lg) 0 0 0; transform: translateX(110%)`
  - `.open`: `transform: translateX(0)`
  - Drag handle hidden on tablet+

- [ ] Test: mobile swipe dismiss, ESC key dismiss, focus trap, memorial mode appearance
- [ ] Commit: `feat(ui): person card with bottom sheet, privacy-gated contacts, memorial mode`

---

### Task 10: Mobile CSS Design System

**Files:** `frontend/css/vars.css`, `frontend/css/reset.css`, `frontend/css/layout.css`, `frontend/css/landing.css`

Note: `tree.css` and `card.css` already written in Tasks 8-9 using vars. These vars must be finalized before those files are complete.

- [ ] Write `frontend/css/vars.css`:

  **Colors:**
  - `--color-bg: #fafaf9` — warm off-white
  - `--color-surface: #ffffff`
  - `--color-text: #1c1917` — warm near-black
  - `--color-text-muted: #78716c`
  - `--color-border: #e7e5e4`
  - `--color-accent: #2563eb` — CTA, links
  - `--color-link-line: #d1d5db` — SVG tree connecting lines
  - `--branch-martin: #2563eb`, `--branch-semesock: #16a34a`, `--branch-yuliya: #dc2626`

  **Dark mode `@media (prefers-color-scheme: dark)`:** Override bg/surface/text/border. Reduce branch color saturation slightly.

  **Typography (fluid, no web fonts):**
  - `--font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif`
  - `--text-xs` through `--text-2xl` using `clamp()` for fluid scaling across viewport widths

  **Spacing:** `--space-1: 0.25rem` through `--space-12: 3rem`

  **Radii:** `--radius-full: 9999px`, `--radius-lg: 0.75rem`, `--radius-md: 0.5rem`

  **Shadows:** `--shadow-sm`, `--shadow-md`

- [ ] Write `frontend/css/reset.css`:
  - Universal `box-sizing: border-box; margin: 0; padding: 0`
  - `body`: font, color, background from vars; `line-height: 1.5; -webkit-text-size-adjust: 100%`
  - `img, svg`: `display: block; max-width: 100%`
  - `button`: `cursor: pointer; font: inherit; border: none; background: none; padding: 0`
  - `a`: `color: inherit; text-decoration: none`
  - `:focus-visible`: `outline: 2px solid var(--color-accent); outline-offset: 2px` — NEVER `outline: none` globally
  - `@media (prefers-reduced-motion: reduce)`: zero animation/transition durations on `*`

- [ ] Write `frontend/css/layout.css` (mobile-first):
  - `html, body { height: 100%; margin: 0 }`
  - `body`: `min-height: 100svh; display: flex; flex-direction: column`
  - `nav`: `height: 56px; display: flex; align-items: center; justify-content: space-between; padding-inline: var(--space-4); background: var(--color-surface); border-bottom: 1px solid var(--color-border)`
  - Nav mobile: logo text left, logout icon button right (44×44 min tap target)
  - `main`: `flex: 1; position: relative; overflow: hidden`
  - iOS safe areas: `padding-top: env(safe-area-inset-top)` on nav
  - **Logical properties throughout**: `padding-inline-start` not `padding-left`, `margin-block-end` not `margin-bottom`, `border-inline-start` not `border-left`, etc. This is non-negotiable — RTL support in Phase 4 requires it.
  - `.btn`: `display: inline-flex; align-items: center; justify-content: center; min-height: 44px; padding: var(--space-3) var(--space-6); border-radius: var(--radius-md); font-size: var(--text-base); cursor: pointer`
  - `.btn-primary`: `background: var(--color-accent); color: #fff`
  - `@media (min-width: 640px)`: sidebar layout — when card is open, tree + card in grid

- [ ] Write `frontend/css/landing.css`:
  - `body` override for landing: center content vertically and horizontally
  - `<main>`: `display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: calc(100svh - 56px); padding: var(--space-8) var(--space-4); text-align: center; max-width: 480px; margin-inline: auto`
  - Trust photos: two 72px circle `<img>` elements in a flex row, centered
  - Headline `<h1>`: `font-size: var(--text-2xl); font-weight: 700; margin-block: var(--space-4)`
  - Tagline: `font-size: var(--text-base); color: var(--color-text-muted); max-width: 32ch; margin-inline: auto`
  - CTA `.btn-primary`: `width: 100%; max-width: 360px; min-height: 56px; font-size: var(--text-lg); margin-block-start: var(--space-6)`
  - Privacy note: `font-size: var(--text-xs); color: var(--color-text-muted); margin-block-start: var(--space-3)`

- [ ] Test all CSS on Chrome DevTools: iPhone SE (375px), iPhone 14 Pro (393px), iPad (768px), desktop (1280px)
- [ ] Toggle `prefers-color-scheme: dark` in DevTools — verify dark mode works
- [ ] Commit: `feat(css): mobile-first design system`

---

### Task 11: Railway Deployment

**Files:** `Dockerfile`, `railway.toml`, health endpoint in `backend/routers/tree.py`

- [ ] Write `Dockerfile`:
  - `FROM python:3.12-slim`
  - `WORKDIR /app`
  - `COPY pyproject.toml .`
  - `RUN pip install --no-cache-dir .`
  - `COPY backend/ backend/` `COPY frontend/ frontend/` `COPY migrations/ migrations/` `COPY alembic.ini .`
  - `RUN mkdir -p data/photos` (Railway volume mounts over this, creating the real persistent dir)
  - `EXPOSE 8000`
  - `CMD alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}`
  - Do NOT copy `.env` — secrets come from Railway env vars

- [ ] Write `railway.toml`:
  - `[build] builder = "DOCKERFILE" dockerfilePath = "Dockerfile"`
  - `[deploy] healthcheckPath = "/api/health" healthcheckTimeout = 30 restartPolicyType = "ON_FAILURE" restartPolicyMaxRetries = 3`

- [ ] Verify `GET /api/health` is implemented in `backend/routers/tree.py` (or `backend/main.py`): executes `SELECT 1`, returns `{"status": "ok"}`. No auth.

- [ ] Railway dashboard setup:
  - Create project → service linked to GitHub repo
  - Add Volume mounted at `/app/data` — CRITICAL for SQLite and photo persistence
  - Set all env vars (see table below)
  - First deploy → confirm health check passes (green)
  - `railway run python -m backend.seed` to load initial family data
  - Update Facebook App: add Railway HTTPS URL to Valid OAuth Redirect URIs

- [ ] Persistence test: add a test person via admin, trigger a redeploy, confirm person still exists

- [ ] Commit: `chore(deploy): Dockerfile, railway.toml, health endpoint`

**Railway Environment Variables:**

| Variable | Example | Notes |
|----------|---------|-------|
| `FB_APP_ID` | `1234567890` | From Facebook Developer Console |
| `FB_APP_SECRET` | `abc123...` | Never commit |
| `FB_REDIRECT_URI` | `https://family-book.up.railway.app/auth/callback` | Must exactly match FB app settings |
| `ADMIN_FB_IDS` | `111111111,222222222` | Tyler's + Yuliya's numeric FB user IDs |
| `FERNET_KEY` | `<base64>` | Generate fresh for production |
| `SESSION_SECRET` | `<64-char hex>` | Generate fresh for production |
| `DATABASE_URL` | `sqlite:////app/data/family.db` | 4 slashes = absolute path |
| `ROOT_PERSON_ID` | `<UUID>` | Root person's UUID from seed file |

---

### Task 12: End-to-End Verification

- [ ] Desktop full flow: landing → Facebook login → tree renders → click person → card opens → logout
- [ ] iPhone full flow: same, with swipe-down card dismiss, pinch-zoom on tree
- [ ] iPad full flow: sidebar card layout, wider tree
- [ ] Admin flow: Tyler adds person, adds relationship, verifies tree, deletes both
- [ ] Non-admin privacy check: log in as test family member → confirm no admin endpoint access (403) → confirm Layer 4/5 person cards omit contact info
- [ ] Root node privacy check: confirm "Our Family" appears as root in tree, inspect HTML source — no real child's name anywhere
- [ ] Full test suite: `pytest tests/ -v --cov=backend --cov-report=term-missing`

---

## Gotchas Reference

### Facebook API

**1. Development mode limits** — App stays in dev mode until App Review. Only users added as Testers/Developers/Admins in App Roles can log in (max 40 total). Add each family member before sending the invite link.

**2. `user_photos`/`user_friends` require App Review** — Phase 1 does NOT request them. Do not promise photo import until Phase 2 post-review.

**3. Short-lived tokens expire in ~1 hour** — Always exchange for long-lived token (60 days) immediately in the callback. Never skip this.

**4. Profile photo URLs are temporary** — `picture.data.url` from Graph API expires within hours. Download the photo to disk in the callback. Never store the CDN URL as `photo_url`.

**5. State token is single-use** — Clear the CSRF state cookie after the callback regardless of success/failure. If callback is replayed, verify-and-fail gracefully → redirect to `/`, not 500.

**6. `ADMIN_FB_IDS` needs numeric IDs** — Not vanity slugs. Get Tyler's and Yuliya's numeric IDs by calling `GET /me?fields=id` during first login. Hardcode in env var.

**7. Graph API version pinning** — Pin all URLs to `v21.0`. Set a reminder to upgrade before it reaches end-of-life (~2 years).

### SQLite on Railway

**8. Volume mount path must match `DATABASE_URL`** — If `DATABASE_URL=sqlite:////app/data/family.db` but volume is at `/data`, you get an empty DB on every deploy. Verify before first real-data deploy.

**9. WAL mode is essential** — Without it, concurrent async reads during a write → "database is locked" errors. Add `PRAGMA journal_mode=WAL` to the connection event listener.

**10. Foreign keys are off by default** — Add `PRAGMA foreign_keys=ON` to the same listener. Without it, cascade deletes silently fail.

**11. Alembic autogenerate is unreliable for SQLite changes** — Most `ALTER TABLE` operations are unsupported. Write future schema migrations manually. Document in CLAUDE.md.

**12. `data/photos/` must exist before first photo download** — Create it in FastAPI `lifespan` startup. The Railway volume provides `/app/data/` but not `photos/` subdirectory.

### D3 and SVG

**13. D3 hierarchy requires single connected root** — Persons unreachable from root via BFS are excluded from `/api/tree`. Surface them in admin panel as "Unconnected Persons."

**14. Spouses violate hierarchy** — Don't put spouses into `d3.hierarchy()`. Render them via custom SVG path elements using the `edges` list from the API, after the tree layout runs.

**15. iOS Safari SVG tap events need `pointer-events: all`** — Without it, taps on `<g>` elements silently do nothing. Add to `.person-node` in `tree.css`.

**16. iOS Safari pinch-zoom fights d3.zoom** — Set `touch-action: none` on `#family-tree`. Without it, browser zoom and d3.zoom conflict.

**17. SVG `<text>` doesn't wrap** — Truncate node name to ~14 characters in the tree. Show full name in the card.

**18. SVG `<image>` is same-origin in Phase 1** — Photos served from `/photos/` (same origin). No CORS issues. If photos move to R2 in Phase 2, configure CORS on the bucket.

### Privacy and Security

**19. Root node name assertion must be in tests** — `test_api_tree.py` must assert the root node's `name` field in the API response equals "Our Family" (or placeholder). This test catches any accidental real-name exposure.

**20. `FERNET_KEY` rotation breaks all sessions** — All encrypted tokens become unreadable. All users must re-login. Document in CLAUDE.md.

**21. SameSite=Lax is required (not Strict)** — Strict blocks the OAuth redirect from carrying the state cookie back to the callback. Keep Lax.

### General

**22. `branch` field must be in `family_tree.json`** — Not derived from UUIDs. Store `branch` on the Person, save it in seed JSON. If hardcoded to UUIDs, any seed regeneration silently breaks branch coloring.

**23. WhatsApp phone numbers need normalization** — `wa.me` requires digits only, no `+` or spaces. Strip all non-digits from `contact_whatsapp` before building the link URL.

**24. `updated_at` won't auto-update reliably** — SQLAlchemy's `onupdate=func.now()` is unreliable with SQLite TEXT dates. Use a `@event.listens_for(Session, "before_flush")` listener to set `updated_at = datetime.utcnow().isoformat()` on all `dirty` objects.

**25. Admin FB IDs env var is the sole admin gate** — If Tyler's Facebook account is compromised, so is Family Book admin. Acceptable risk for Phase 1. Document in CLAUDE.md.

---

## Local Development

```
# Install
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env: add FB_APP_ID, FB_APP_SECRET, generate FERNET_KEY and SESSION_SECRET

# Initialize DB
alembic upgrade head

# Seed data
python -m backend.seed

# Run
uvicorn backend.main:app --reload --port 8000

# Test
pytest tests/ -v
```

---

## Test Coverage Targets

| Module | Priority | Key Scenarios |
|--------|----------|--------------|
| `backend/graph.py` | Critical | All label permutations; all privacy layer rules; ex-spouse → L5; marriage graft |
| `backend/oauth.py` | High | OAuth URL; code exchange (httpx mocked); upsert creates vs updates; admin detection |
| `backend/routers/tree.py` | High | Auth gate; JSON shape; root node name assertion; layer field gating |
| `backend/routers/people.py` | High | Auth gates; CRUD; 404; 403; privacy field gating by layer |
| `backend/seed.py` | Medium | Idempotency; is_root exists; admins correct |
| `backend/models.py` | Medium | Unique constraints; FK cascade; check constraints |

---

## Implementation Order

1. Human bottlenecks: FB app, UUIDs, root person identity
2. Task 1 — Project scaffolding
3. Task 2 — Database models + Alembic migration
4. Task 3 — Seed data + loader
5. Task 6 — FastAPI app shell + health endpoint (partial, from Task 6)
6. Task 4 — Graph engine (TDD)
7. Task 5 — Facebook OAuth + session auth
8. Task 6 — API endpoints (complete)
9. Task 7 — Frontend templates
10. Task 8 — D3 tree visualization
11. Task 9 — Person card
12. Task 10 — Mobile CSS design system (finalize vars, complete tree.css + card.css)
13. Task 11 — Railway deployment
14. Task 12 — End-to-end verification

---

## Phase 1 Definition of Done

- [ ] Tyler logs in via Facebook and sees the seeded family tree
- [ ] Yuliya logs in via Facebook and sees the family tree
- [ ] At least one other family member (test user) logs in and sees tree with correct relationship labels
- [ ] Luna's real name does not appear in the UI, API responses, HTML source, or logs
- [ ] Tree renders with photos, names, connecting lines — zoom/pan works on desktop and mobile
- [ ] Tapping any person opens their card: photo, relationship label, location flag, birthday, contact links (privacy-gated)
- [ ] All tests pass: `pytest tests/ -v`
- [ ] App deployed on Railway, accessible at HTTPS URL
- [ ] SQLite data persists across Railway redeploys
- [ ] Tyler and Yuliya can add, edit, delete persons and relationships from the admin UI

**Prod URL:** _(update after Railway deploy)_
**Local:** [http://localhost:8000](http://localhost:8000)
