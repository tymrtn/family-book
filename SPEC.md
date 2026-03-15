# Family Book — Spec v2

**A private, self-hosted family tree and archive.**

"Facebook is the mall. This is our living room."

---

## Vision

A private website where Tyler's daughter can see all her family — faces, names, relationships, locations — across Canada, Russia, and Spain. Family members join via invite link, optionally link their Facebook for profile enrichment, and browse an interactive family tree. Privacy is enforced by role (Phase 1) and graph-distance (Phase 2). No ads. No algorithms. No Zuckerberg.

---

## Core Concepts

### The Family Graph

Every person is a node. Edges are typed relationships (parent-child, partnership). The graph computes:
- Relationship labels ("2nd cousin once removed", "тётя", "uncle")
- Ancestry paths ("Luna → Yuliya → Бабушка Наташа → ...")
- Permission boundaries (Phase 2: graph-distance ACL)

Siblings are **derived**, not stored. If two people share a parent, they are siblings. Half-siblings share one parent. Step-siblings share a step-parent. This eliminates contradiction risk from redundant edges.

### Root Person

The tree has a designated root person for visualization. This is a **real person** in the database — not a fake "Our Family" node. The root's real name is redacted in the UI for child privacy: displayed as "Our Family" or "Наша Семья" depending on locale. The `is_root` flag on the Person record controls this. The root person's actual name exists in the database for admin use but is never exposed in templates, API responses, or client-side code.

---

## Data Model

### Person

| Field | Type | Required | Default | Constraints | Notes |
|-------|------|----------|---------|-------------|-------|
| id | UUID | yes | auto-generated | PK | Stable after creation. Used in URLs. |
| first_name | str | yes | — | max 200, Unicode | |
| last_name | str | yes | — | max 200, Unicode | |
| patronymic | str | no | null | max 200, Unicode | Russian/Arabic naming convention |
| birth_last_name | str | no | null | max 200 | Maiden name |
| nickname | str | no | null | max 100 | Displayed in quotes: "Sasha" |
| name_display_order | enum | no | western | western, eastern, patronymic | Controls name rendering |
| gender | enum | no | null | male, female, other, null | Used for gendered relationship labels only. Null = unspecified. |
| birth_date_raw | str | no | null | max 50 | Original date string as entered: "1952", "March 1985", "~1960", "before 1945" |
| birth_date | date | no | null | ISO 8601 | Best-effort normalized date. Null if unparseable. |
| birth_date_precision | enum | no | null | exact, month, year, decade, approximate | How precise is birth_date? |
| death_date_raw | str | no | null | max 50 | Same fuzzy date handling as birth |
| death_date | date | no | null | ISO 8601 | |
| death_date_precision | enum | no | null | exact, month, year, decade, approximate | |
| is_living | bool | yes | true | | False = memorial profile |
| birth_place | str | no | null | max 300 | City, region, country as entered |
| birth_country_code | str | no | null | ISO 3166-1 alpha-2 | For flag display |
| residence_place | str | no | null | max 300 | Current residence |
| residence_country_code | str | no | null | ISO 3166-1 alpha-2 | |
| burial_place | str | no | null | max 300 | For memorial profiles |
| languages | JSON | no | [] | Array of ISO 639-1 codes | |
| bio | str | no | null | max 2000 | Short narrative bio |
| contact_whatsapp | str | no | null | E.164 phone | |
| contact_telegram | str | no | null | max 100 | Username without @ |
| contact_signal | str | no | null | E.164 phone | |
| contact_email | str | no | null | max 320 | |
| photo_url | str | no | null | max 2000 | Relative path to uploaded photo |
| branch | str | no | null | max 100 | Display hint: "martin", "semesock", "maternal". Presentation only — not truth. |
| is_root | bool | yes | false | Exactly one person has is_root=true | UI redaction flag |
| is_admin | bool | yes | false | | Full CRUD + user management |
| visibility | enum | yes | visible | visible, hidden, memorial | Hidden = exists in DB but not rendered |
| facebook_id | str | no | null | max 100, unique | From OAuth. For dedup. |
| facebook_token_encrypted | bytes | no | null | Fernet-encrypted | Long-lived token. Encrypted at rest. |
| facebook_token_expires | datetime | no | null | | 60-day expiry from Meta |
| source | enum | yes | manual | manual, facebook_oauth, gedcom_import, federation | How this person entered the system |
| created_by | UUID | no | null | FK → Person.id | Who added this record |
| created_at | datetime | yes | now() | | |
| updated_at | datetime | yes | now() | | Auto-updated on change |

### ParentChild

| Field | Type | Required | Default | Constraints | Notes |
|-------|------|----------|---------|-------------|-------|
| id | UUID | yes | auto | PK | |
| parent_id | UUID | yes | — | FK → Person.id | |
| child_id | UUID | yes | — | FK → Person.id | |
| kind | enum | yes | biological | biological, adoptive, step, foster, guardian, unknown | |
| confidence | enum | no | confirmed | confirmed, probable, uncertain, unknown | Genealogy-grade provenance |
| source | enum | yes | manual | manual, facebook_import, gedcom_import, federation | |
| source_detail | str | no | null | max 500 | "GEDCOM XREF I0042", "Facebook family_members.json", etc. |
| notes | str | no | null | max 2000 | |
| start_date | date | no | null | | Adoption date, guardianship start, etc. |
| end_date | date | no | null | | Guardianship end, etc. |
| created_by | UUID | no | null | FK → Person.id | |
| created_at | datetime | yes | now() | | |

**Constraints:**
- Unique on (parent_id, child_id, kind). A person can have multiple parent relationships of different kinds (e.g., one biological + one adoptive).
- A person may have 0, 1, or 2+ parents of any kind. "Unknown parent" = no ParentChild row exists + an explicit flag is NOT needed; the absence is the signal.
- Self-referential parent_id = child_id is rejected.

### Partnership

Replaces the flat spouse/ex_spouse enum. Supports marriage, divorce, remarriage, co-parenting, and same-sex couples.

| Field | Type | Required | Default | Constraints | Notes |
|-------|------|----------|---------|-------------|-------|
| id | UUID | yes | auto | PK | |
| person_a_id | UUID | yes | — | FK → Person.id | Ordering: person_a_id < person_b_id (canonical) |
| person_b_id | UUID | yes | — | FK → Person.id | |
| kind | enum | yes | married | married, domestic_partner, co_parent, engaged, other | |
| status | enum | yes | active | active, dissolved, widowed, annulled, separated | |
| start_date | date | no | null | | Wedding date, etc. |
| start_date_precision | enum | no | null | exact, month, year, approximate | |
| end_date | date | no | null | | Divorce date, death of partner, etc. |
| end_date_precision | enum | no | null | exact, month, year, approximate | |
| source | enum | yes | manual | manual, facebook_import, gedcom_import, federation | |
| notes | str | no | null | max 2000 | |
| created_by | UUID | no | null | FK → Person.id | |
| created_at | datetime | yes | now() | | |

**Constraints:**
- Unique on (person_a_id, person_b_id, kind, start_date). Same pair can have multiple partnerships (remarriage after divorce).
- person_a_id < person_b_id enforced at insert (canonical ordering, prevents duplicate pairs).
- No gender constraints. Any two people can form any partnership kind.

### ExternalIdentity

Maps people to external system IDs for dedup and import provenance.

| Field | Type | Required | Default | Constraints | Notes |
|-------|------|----------|---------|-------------|-------|
| id | UUID | yes | auto | PK | |
| person_id | UUID | yes | — | FK → Person.id | |
| provider | enum | yes | — | facebook, gedcom, federation | |
| external_id | str | yes | — | max 500 | Facebook ID, GEDCOM XREF, federation URI |
| metadata | JSON | no | {} | | Provider-specific extra data |
| created_at | datetime | yes | now() | | |

**Constraints:** Unique on (provider, external_id).

### Photo

| Field | Type | Required | Default | Constraints | Notes |
|-------|------|----------|---------|-------------|-------|
| id | UUID | yes | auto | PK | |
| person_id | UUID | yes | — | FK → Person.id | |
| file_path | str | yes | — | max 500 | Relative path under /data/photos/ |
| original_filename | str | no | null | max 300 | |
| mime_type | str | yes | — | max 50 | image/jpeg, image/png, image/webp |
| width | int | no | null | | Pixels |
| height | int | no | null | | |
| caption | str | no | null | max 1000 | |
| taken_date | date | no | null | | From EXIF or manual |
| source | enum | yes | manual | manual, facebook_oauth, facebook_export, whatsapp | |
| is_profile | bool | yes | false | At most one per person | Used as Person.photo_url |
| uploaded_by | UUID | no | null | FK → Person.id | |
| created_at | datetime | yes | now() | | |

### UserSession

| Field | Type | Required | Default | Constraints | Notes |
|-------|------|----------|---------|-------------|-------|
| id | UUID | yes | auto | PK | |
| person_id | UUID | yes | — | FK → Person.id | |
| token_hash | str | yes | — | SHA-256 of session token | Never store raw token |
| auth_method | enum | yes | — | facebook_oauth, magic_link, invite_code | How they authenticated |
| created_at | datetime | yes | now() | | |
| expires_at | datetime | yes | +30 days | | |
| last_used | datetime | yes | now() | | Updated on each request |
| ip_address | str | no | null | max 45 | IPv4 or IPv6 |
| user_agent | str | no | null | max 500 | |

### AuditLog

Every mutation to Person, ParentChild, or Partnership is logged.

| Field | Type | Required | Default | Constraints | Notes |
|-------|------|----------|---------|-------------|-------|
| id | UUID | yes | auto | PK | |
| actor_id | UUID | no | null | FK → Person.id | Null = system/import |
| action | enum | yes | — | create, update, delete, merge, import | |
| entity_type | str | yes | — | "person", "parent_child", "partnership" | |
| entity_id | UUID | yes | — | | |
| old_value | JSON | no | null | | Snapshot before change |
| new_value | JSON | no | null | | Snapshot after change |
| created_at | datetime | yes | now() | | |

### GedcomImportBatch (Phase 2 — specced now, built later)

| Field | Type | Required | Default | Constraints | Notes |
|-------|------|----------|---------|-------------|-------|
| id | UUID | yes | auto | PK | |
| filename | str | yes | — | max 300 | |
| raw_content_path | str | yes | — | max 500 | Path to stored raw GEDCOM file |
| status | enum | yes | pending | pending, processing, review, completed, failed | |
| stats | JSON | no | {} | | { individuals: N, families: N, matched: N, new: N, errors: N } |
| imported_by | UUID | yes | — | FK → Person.id | |
| created_at | datetime | yes | now() | | |
| completed_at | datetime | no | null | | |

### GedcomStagedRecord (Phase 2)

| Field | Type | Required | Default | Constraints | Notes |
|-------|------|----------|---------|-------------|-------|
| id | UUID | yes | auto | PK | |
| batch_id | UUID | yes | — | FK → GedcomImportBatch.id | |
| xref | str | yes | — | max 50 | GEDCOM XREF (e.g., @I0042@) |
| record_type | enum | yes | — | individual, family, source, note | |
| raw_data | JSON | yes | — | | Parsed GEDCOM fields as JSON |
| matched_person_id | UUID | no | null | FK → Person.id | Auto-matched or human-linked |
| match_confidence | float | no | null | 0.0–1.0 | |
| review_status | enum | yes | pending | pending, accepted, rejected, merged | |
| reviewed_by | UUID | no | null | FK → Person.id | |
| created_at | datetime | yes | now() | | |

---

## Authentication & Authorization

### Auth Methods (Phase 1)

Three ways to authenticate, in priority order:

#### 1. Invite Link (primary onboarding path)
1. Admin creates a Person record manually (name, relationship, branch)
2. System generates a unique invite token (UUID, single-use, 30-day expiry)
3. Admin sends link via WhatsApp/Telegram/email: `https://martin.fm/invite/{token}`
4. Family member taps link → lands on claim page showing their name + relationship
5. Family member confirms identity → session created → logged in
6. Invite token is consumed (one-time use)
7. Optional: link Facebook account for profile photo enrichment

#### 2. Magic Link Email
1. User enters email on login page
2. If email matches a Person record → send magic link (UUID token, 15-min expiry)
3. User clicks link in email → session created → logged in
4. If email doesn't match → "Ask Tyler to invite you" message
5. Email sent via: Envelope API (already deployed) or SMTP fallback

#### 3. Facebook OAuth (optional enrichment)
1. User clicks "Connect with Facebook" from their profile settings (NOT from login)
2. Standard OAuth flow → `public_profile` + `email` scopes only (no App Review needed)
3. On callback: match by email or facebook_id → link to existing Person
4. If no match: reject with "Ask Tyler to add you first" (never auto-create unlinked people)
5. Import: profile photo, display name (for verification only, not overwrite)
6. Facebook is NEVER the sole authentication method. It's profile enrichment.

**Why Facebook is secondary:** Some relatives won't use it. Some won't authorize Meta. Development-mode tester management is operationally annoying. Magic link + invite code covers everyone.

### Account States

| State | Can Log In | Can See Tree | How to Reach |
|-------|-----------|-------------|--------------|
| pending | yes (via invite) | no — sees "Awaiting admin approval" | Auto after invite claim, if admin configured approval-required |
| active | yes | yes | Admin approves, or auto if approval not required |
| suspended | no | no | Admin action (estrangement, etc.) |

**Default config:** `REQUIRE_APPROVAL=false`. Invite link → immediate active. Toggle to true for stricter onboarding.

### Session Management

- Session token: 32 random bytes, hex-encoded, stored as SHA-256 hash in `UserSession`
- Token sent as `HttpOnly`, `Secure`, `SameSite=Lax` cookie named `session`
- Default expiry: 30 days, sliding (extended on each authenticated request)
- Max sessions per person: 10 (oldest evicted)
- CSRF: `state` parameter for OAuth, SameSite cookie for mutations

### Roles (Phase 1)

| Role | Permissions |
|------|------------|
| admin | Full CRUD on all entities. User management. Invite creation. Backup/export. |
| member | Read tree. Read person cards. View photos. Edit own profile. Upload own photos. |
| pending | Read own invite status only. |

### Field-Level Visibility (Phase 1)

| Field Category | admins | members | pending |
|---------------|--------|---------|---------|
| Name, photo, branch, country, relationship label | ✅ | ✅ | ❌ |
| Bio, languages, birth year | ✅ | ✅ | ❌ |
| Full birth date, contact info | ✅ | ✅ (own + admin) | ❌ |
| Death info, burial place | ✅ | ✅ | ❌ |
| Facebook ID, tokens, audit log | ✅ | ❌ | ❌ |

**Phase 2 enhancement:** Graph-distance ACL. See dedicated section below.

---

## Graph-Distance Privacy (Phase 2 — fully specced, not built in Phase 1)

### How It Works

Permissions are computed from the family graph, not configured manually. The tree IS the ACL.

| Layer | Who (relative to viewer) | Can See |
|-------|--------------------------|---------|
| 0 | Self | Everything (own profile) |
| 1 | Parents, children, spouse | Full profiles, all contacts, all photos |
| 2 | Grandparents, siblings, siblings' spouses | Their branch + shared ancestors, contact info |
| 3 | Aunts/uncles, first cousins | Their branch, shared connections, photos |
| 4 | Second cousins, great-aunts/uncles | Names, photos, location, country |
| 5 | Third+ cousins, distant | Name, country, flag. Existence only. |

### Graph-Distance Computation

- BFS from viewer to target, counting edges
- Edge weights: parent-child = 1, partnership = 1 (through to partner's family)
- Layer = min(graph_distance, 5)
- Cache: computed per viewer, invalidated on any tree mutation

### Life-Event Mutations

| Event | Effect |
|-------|--------|
| Marriage | New partnership edge. Spouse gains Layer 1 to partner's immediate family. |
| Divorce | Partnership status → dissolved. Ex-partner drops to Layer 5 from partner's family. Children retain natural layer. |
| Death | Person.is_living = false. visibility → memorial. Contact info hidden from all non-admins. Photos preserved. |
| Estrangement | Admin override: person.visibility → hidden. No graph change. Reversible. |
| Adoption | New ParentChild(kind=adoptive). Adoptive parent's family gains natural graph distance. |
| New baby | New ParentChild edges to both parents. Inherits graph position naturally. |

### Admin Overrides

Admins can override computed layers per person:
- `privacy_layer_override`: int or null. Null = use computed. Set = force this layer.
- Stored on Person record. Audit-logged.

---

## API Surface

### Auth Endpoints

| Method | Path | Auth | Request | Success Response | Error Responses |
|--------|------|------|---------|-----------------|-----------------|
| GET | `/invite/{token}` | none | — | 200: HTML claim page with person name + relationship | 404: invalid/expired token |
| POST | `/invite/{token}/claim` | none | `{}` | 302 → `/tree` + Set-Cookie session | 404: invalid token, 410: already claimed |
| POST | `/auth/magic-link` | none | `{ email: str }` | 200: `{ message: "Check your email" }` | 400: invalid email format. (Always 200 even if email not found — no enumeration.) |
| GET | `/auth/magic-link/{token}` | none | — | 302 → `/tree` + Set-Cookie session | 404: invalid/expired token |
| GET | `/auth/facebook` | none | — | 302 → Facebook OAuth URL | — |
| GET | `/auth/facebook/callback` | none | `?code=...&state=...` | 302 → `/tree` or `/profile` + Set-Cookie | 400: CSRF mismatch, 403: no matching person |
| POST | `/auth/logout` | user | — | 200 + clear cookie | — |

### Person Endpoints

| Method | Path | Auth | Request | Success | Errors |
|--------|------|------|---------|---------|--------|
| GET | `/api/persons` | member | `?search=...&branch=...&country=...` | 200: `[PersonSummary]` | 401 |
| GET | `/api/persons/{id}` | member | — | 200: `PersonDetail` | 401, 403 (visibility), 404 |
| POST | `/api/persons` | admin | `PersonCreate` | 201: `PersonDetail` | 400: validation, 401, 409: duplicate candidate |
| PUT | `/api/persons/{id}` | admin (or self for own profile) | `PersonUpdate` | 200: `PersonDetail` | 400, 401, 403, 404 |
| DELETE | `/api/persons/{id}` | admin | — | 204 | 401, 403, 404 |

**PersonSummary:** `{ id, first_name, last_name, nickname, photo_url, residence_country_code, branch, is_living, visibility }`
**PersonDetail:** PersonSummary + `{ patronymic, birth_last_name, gender, birth_date (if permitted), bio, languages, contacts (if permitted), all relationship labels to viewer }`
**PersonCreate:** `{ first_name, last_name, patronymic?, birth_last_name?, nickname?, gender?, birth_date_raw?, birth_place?, residence_place?, residence_country_code?, branch?, bio?, contact_*? }`

### Relationship Endpoints

| Method | Path | Auth | Request | Success | Errors |
|--------|------|------|---------|---------|--------|
| POST | `/api/relationships/parent-child` | admin | `{ parent_id, child_id, kind }` | 201 | 400: self-ref / cycle, 401, 404, 409: exists |
| DELETE | `/api/relationships/parent-child/{id}` | admin | — | 204 | 401, 404 |
| POST | `/api/relationships/partnership` | admin | `{ person_a_id, person_b_id, kind, status, start_date? }` | 201 | 400: self-ref, 401, 404, 409 |
| PUT | `/api/relationships/partnership/{id}` | admin | `{ status?, end_date? }` | 200 | 400, 401, 404 |
| DELETE | `/api/relationships/partnership/{id}` | admin | — | 204 | 401, 404 |
| GET | `/api/relationships/between/{id_a}/{id_b}` | member | — | 200: `{ label, path, distance }` | 401, 404 |

### Tree Endpoint

| Method | Path | Auth | Request | Success | Errors |
|--------|------|------|---------|---------|--------|
| GET | `/api/tree` | member | `?root_id=...` (default: is_root person) | 200: `TreeData` | 401 |

**TreeData:**
```json
{
  "root_id": "uuid",
  "persons": [PersonSummary],
  "parent_child": [{ "id": "uuid", "parent_id": "uuid", "child_id": "uuid", "kind": "biological" }],
  "partnerships": [{ "id": "uuid", "person_a_id": "uuid", "person_b_id": "uuid", "kind": "married", "status": "active" }]
}
```

### Photo Endpoints

| Method | Path | Auth | Request | Success | Errors |
|--------|------|------|---------|---------|--------|
| POST | `/api/persons/{id}/photos` | admin (or self) | multipart/form-data | 201: `Photo` | 400: bad file type, 401, 413: >10MB |
| GET | `/api/persons/{id}/photos` | member | — | 200: `[Photo]` | 401, 404 |
| GET | `/photos/{photo_id}/{filename}` | member | — | 200: image bytes | 401, 404 |
| DELETE | `/api/photos/{id}` | admin | — | 204 | 401, 404 |

**Photo serving:** All photo URLs go through an authenticated endpoint. No static file serving for photos. The endpoint checks session auth before streaming the file. This prevents URL-sharing bypass.

### Invite Endpoints

| Method | Path | Auth | Request | Success | Errors |
|--------|------|------|---------|---------|--------|
| POST | `/api/invites` | admin | `{ person_id }` | 201: `{ token, url, expires_at }` | 401, 404, 409: active invite exists |
| GET | `/api/invites` | admin | — | 200: `[Invite]` | 401 |
| DELETE | `/api/invites/{id}` | admin | — | 204 | 401, 404 |

### Admin Endpoints

| Method | Path | Auth | Request | Success | Errors |
|--------|------|------|---------|---------|--------|
| GET | `/api/admin/audit-log` | admin | `?entity_type=...&limit=50&offset=0` | 200: `[AuditEntry]` | 401 |
| POST | `/api/admin/backup` | admin | — | 200: `{ backup_path, size_bytes, timestamp }` | 401, 500 |
| GET | `/api/admin/backup/download` | admin | — | 200: application/zip | 401 |
| POST | `/api/admin/persons/{id}/approve` | admin | — | 200 | 401, 404 |
| POST | `/api/admin/persons/{id}/suspend` | admin | — | 200 | 401, 404 |

### Health Endpoint

| Method | Path | Auth | Response |
|--------|------|------|----------|
| GET | `/health` | none | 200: `{ status: "ok", db: "connected", version: "1.0.0" }` |

---

## UI Architecture

### Rendering Strategy

**HTMX for everything except the tree.** Server-rendered HTML templates (Jinja2) enhanced with HTMX for:
- Forms (create/edit person, create relationship, upload photo)
- Search results (live search with `hx-trigger="keyup changed delay:300ms"`)
- Admin panels (invite management, approval queue, audit log)
- List views (people by branch, by country)
- Person cards (loaded via `hx-get` on tree node click)

**D3.js tree island:** One isolated page/component for the interactive family tree visualization. This is the only client-heavy JS. It fetches `/api/tree` as JSON and renders with D3. Everything else is server-rendered.

No SPA framework. No React. No Vue. Vanilla HTML + HTMX + one D3 island.

### Pages

| Route | Auth | Renders | Method |
|-------|------|---------|--------|
| `/` | none | Landing page — "Family Book" + login options | Server |
| `/invite/{token}` | none | Claim page — "Welcome, [name]! Confirm to join." | Server |
| `/login` | none | Login form — magic link email + Facebook option | Server |
| `/tree` | member | Full-page D3 tree visualization | Server shell + D3 client |
| `/people` | member | List view — searchable, filterable by branch/country | Server + HTMX |
| `/people/{id}` | member | Person detail card — photo, bio, relationships, contact | Server + HTMX |
| `/profile` | member | Own profile edit form | Server + HTMX |
| `/admin` | admin | Dashboard — pending approvals, recent audit log, invite links | Server + HTMX |
| `/admin/people/new` | admin | Create person form | Server + HTMX |
| `/admin/people/{id}/edit` | admin | Edit person form | Server + HTMX |
| `/admin/relationships` | admin | Relationship manager — add/edit parent-child + partnerships | Server + HTMX |
| `/admin/backup` | admin | Backup/export controls | Server + HTMX |

### Tree Visualization (D3)

**Layout:** Hierarchical tree (top-down or left-right, user toggle).
**Rendering layers:**
1. SVG background: parent → child connection lines
2. Partnership connectors: horizontal double-line (active) or dashed (dissolved)
3. Person nodes: circles with clipped profile photos
4. Name labels: below nodes

**Interactions:**
- Pan + zoom (touch-friendly for iPad)
- Tap node → loads person card via HTMX (`hx-get="/people/{id}/card"` into sidebar panel)
- Color-coded by branch (CSS custom properties)
- Collapse/expand subtrees
- Double-tap → navigate to full person page

**Node rendering:**
```svg
<g class="person-node" data-id="{id}" data-branch="{branch}">
  <circle r="30" /> <!-- photo clip -->
  <circle r="40" fill="transparent" /> <!-- larger tap target for mobile -->
  <text dy="50">{display_name}</text>
  <text dy="65" class="relationship-label">{relationship_to_viewer}</text>
</g>
```

### Person Card Component

Loaded via HTMX into a slide-out panel or modal:
- Profile photo (circle crop, 120px)
- Display name (respecting name_display_order + locale)
- Nickname in quotes if present
- Relationship label to current viewer (computed)
- Country flag emoji (residence_country_code → emoji)
- Birthday (month + day only — no year exposed to non-admins)
- Contact buttons (WhatsApp, Telegram, Signal, Email — only if value exists)
- Photo gallery thumbnails (if any)
- "View full profile" link

### Design System

- **Mobile-first.** 320px minimum. Breakpoints: 640px (tablet), 1024px (desktop).
- **Color palette:** Branch-coded. Martin = `#4A90D9`, Semesock = `#6BBF6B`, Maternal = `#D94A4A`, Shared = `#9B59B6`.
- **Typography:** System font stack. No web fonts (privacy + speed).
- **Dark mode:** CSS `prefers-color-scheme` with manual toggle.
- **No JavaScript frameworks.** HTMX + D3 + vanilla JS only.

---

## Internationalization (Phase 2 — specced now)

### Approach

Static, checked-in translation catalogs. No runtime LLM translation. No OpenRouter in production.

### Supported Locales (Phase 2)

- `en` — English (default)
- `ru` — Russian
- `es` — Spanish

### UI Strings

One JSON file per locale: `locales/en.json`, `locales/ru.json`, `locales/es.json`.

Hand-written. Checked into git. Loaded by the backend at startup and passed to Jinja2 templates.

```json
{
  "nav": { "tree": "Family Tree", "people": "People", "admin": "Admin" },
  "person": { "birthday": "Birthday", "contact": "Contact", "bio": "About" },
  "admin": { "invite": "Send Invite", "approve": "Approve", "suspend": "Suspend" }
}
```

### Relationship Terms

Relationship labels are **not generic UI strings.** They are domain-specific and culturally specific. They must be manually curated, not LLM-generated.

Stored in: `locales/relationships/{locale}.json`

```json
{
  "mother": "мама",
  "father": "папа",
  "maternal_grandmother": "бабушка по маме",
  "paternal_grandmother": "бабушка по папе",
  "maternal_grandfather": "дедушка по маме",
  "paternal_grandfather": "дедушка по папе",
  "uncle_maternal": "дядя (по маме)",
  "aunt_paternal": "тётя (по папе)",
  "first_cousin": "двоюродный брат / двоюродная сестра",
  "second_cousin": "троюродный брат / троюродная сестра",
  "second_cousin_once_removed": "троюродный брат/сестра (на поколение)"
}
```

**Gender-aware labels:** Russian relationship terms are gendered (двоюродный брат vs двоюродная сестра). The relationship computation uses the target person's `gender` field to select the correct form. Null gender → use masculine form with "(м/ж)" suffix or neutral phrasing.

### Patronymics

When locale = `ru` and `patronymic` is set, display as: `Фамилия Имя Отчество` (last-first-patronymic, per Russian convention). Controlled by `name_display_order = patronymic`.

### OpenRouter (offline admin tool only)

If Tyler wants to add a new locale (e.g., Arabic, French), he can run a CLI script:
```bash
python scripts/generate_locale.py --locale fr --source locales/en.json
```
This calls OpenRouter to generate a draft translation, writes it to `locales/fr.json`, and Tyler reviews + edits before committing. **Never called at runtime. Never in production.**

---

## GEDCOM Import (Phase 2 — fully specced, built later)

### Architecture

GEDCOM import uses a **staging pipeline**, not direct writes to production tables.

```
Upload .ged file → Parse → Stage records → Human review → Accept/Reject/Merge → Write to production
```

### Import Flow

1. Admin uploads `.ged` file via `/admin/import/gedcom`
2. System creates `GedcomImportBatch` with status=processing
3. Parser extracts INDI (individual) and FAM (family) records
4. Each record → `GedcomStagedRecord` with parsed JSON and original XREF
5. Auto-matching: compare staged names against existing Person records
   - Exact name match: `match_confidence = 0.9`
   - Fuzzy match (Levenshtein ≤ 2): `match_confidence = 0.7`
   - Date + name match: `match_confidence = 0.95`
   - No match: `match_confidence = 0.0` (new person candidate)
6. Batch status → review
7. Admin reviews each staged record:
   - **Accept as new** → creates Person + relationships
   - **Merge with existing** → merges fields (admin picks which values win)
   - **Reject** → skipped, logged
8. Batch status → completed
9. All accepted records get `source = gedcom_import` and `ExternalIdentity(provider=gedcom, external_id=XREF)`

### GEDCOM Parsing Scope (v1)

| GEDCOM Record | Mapped To | Fields Extracted |
|---------------|-----------|-----------------|
| INDI | Person | NAME, BIRT DATE/PLAC, DEAT DATE/PLAC, SEX, NOTE |
| FAM | Partnership + ParentChild | HUSB, WIFE, CHIL, MARR DATE, DIV DATE |
| SOUR | notes field | Title, text (as provenance) |

**Not mapped in v1:** Media (OBJE), custom _TAGs, submitter records, repository records. Preserved in `raw_data` JSON for potential future use.

### GEDCOM Date Handling

GEDCOM dates are notoriously messy: "ABT 1952", "BEF 1900", "BET 1940 AND 1945", "1952", "MAR 1952".

Mapping:
- "12 MAR 1952" → `birth_date=1952-03-12, precision=exact`
- "MAR 1952" → `birth_date=1952-03-01, precision=month`
- "1952" → `birth_date=1952-01-01, precision=year`
- "ABT 1952" → `birth_date=1952-01-01, precision=approximate`
- "BEF 1900" → `birth_date=1899-12-31, precision=approximate, birth_date_raw="before 1900"`
- Unparseable → `birth_date=null, birth_date_raw=<original string>`

### Idempotency

Re-importing the same GEDCOM file creates a new batch but auto-matches staged records to previously imported records via XREF → ExternalIdentity. Already-imported records are flagged "previously imported" in review UI.

---

## Facebook Integration (Phase 2 — optional enrichment)

### What Facebook Provides (Development Mode, no App Review)

| Scope | Data | Requires App Review? |
|-------|------|---------------------|
| `public_profile` | Name, profile picture URL, Facebook ID | No |
| `email` | Email address (if user has one set) | No |

**That's it for Phase 1.** `user_friends` and `user_photos` require App Review (2-4 week process). They are Phase 3 features at earliest.

### Development Mode Constraints

- Max 40 testers (add via App Roles → Testers)
- Each tester must accept the invitation in their Facebook Settings
- Tester management is manual and operationally annoying
- This is why Facebook is secondary to invite links

### Facebook Data Export Ingestion (Phase 3)

1. Family member requests data export from Facebook Settings → Downloads → "Request Download"
2. Facebook emails them a download link (24-48h, sometimes longer)
3. They forward the email to `family@martin.fm`
4. Envelope receives email → pipeline extracts download URL
5. Download .zip → parse:
   - `profile_information/profile_information.json` → name, birthday, location
   - `friends_and_followers/friends.json` → friend list (weak signal, not reliable for family)
   - `photos_and_videos/album/` → photos with timestamps
   - `about_you/family_members.json` → family relationships (unreliable — depends on user having set them)
6. Parsed data → staged for admin review (same pattern as GEDCOM)
7. Never auto-write to production. Always human-reviewed.

**Reality check:** Facebook export data is inconsistent across accounts and time. `family_members.json` is often empty. Friend lists don't indicate family relationships. This is a nice-to-have enrichment, not a core data source.

---

## WhatsApp Profile Sync (Phase 3)

- Weekly cron via `wacli`
- Pull profile photos for contacts matching Person records (by phone number)
- Update photo if changed (create new Photo record, mark as profile)
- Pull status text as a lightweight "last seen" signal
- Zero effort from family members
- Requires: `wacli` configured with Tyler's WhatsApp, phone numbers in Person.contact_whatsapp

---

## Federation (Phase 4 — documented vision, not built)

### Vision

Each family's domain runs its own Family Book with its own SQLite. When families connect through marriage, the two instances exchange minimal graph data via API.

### How It Would Work

- `martin.fm` has the Martin/Semesock family SQLite
- `garcia.family` has the Garcia family SQLite
- When a Martin marries a Garcia, both admins agree to federate
- Minimal data exchanged: names, photos, relationship distance from shared node
- Each instance retains sovereignty — your data stays on your domain
- Permission layers cross federation boundaries naturally

### Why It's Deferred

Federation multiplies every hard problem: identity, trust, permissions, deduplication, deletion, conflict resolution, schema versioning. The local data model and permission system must be proven before adding cross-instance complexity.

### Interim Alternative

Manual export/import of a redacted family bundle:
- `family-export.json` with selected person records
- Selected photos
- Both admins explicitly approve the exchange
- No live sync, no protocol, no state management

---

## Security

### Threat Model

| Threat | Mitigation |
|--------|-----------|
| Unauthenticated access to family data | All /api/* and page routes require valid session (except /health, /, /login, /invite) |
| URL-sharing photo bypass | Photos served through authenticated endpoint, not static files |
| Session hijacking | HttpOnly + Secure + SameSite cookies. Token stored as SHA-256 hash. |
| CSRF on mutations | SameSite=Lax cookies. OAuth state parameter. |
| Facebook token theft | Fernet-encrypted at rest. Never exposed in API responses. |
| Stranger joins via Facebook OAuth | Facebook OAuth only links to existing persons. Never auto-creates. |
| Invite link sharing | Single-use tokens. 30-day expiry. Admin can revoke. |
| Enumeration via magic link | Always returns 200 regardless of email match. |
| Admin account compromise | Audit log on all mutations. No bulk delete API. |
| Data loss | Automated daily backups + on-demand backup via admin panel. |
| Child's name exposure | Root person's real name stored only in DB, never in templates/API/client. `is_root` flag triggers redaction. |

### Input Validation

- All string inputs: max length enforced, Unicode normalized (NFC)
- Email: RFC 5322 validation
- Phone: E.164 format validation
- Country codes: ISO 3166-1 alpha-2 whitelist
- File uploads: mime-type validation (image/jpeg, image/png, image/webp only), max 10MB
- UUIDs: format validation on all ID parameters

### Rate Limiting

| Endpoint Group | Limit | Window |
|---------------|-------|--------|
| `/auth/*` (login, magic link) | 10 | 15 min per IP |
| `/api/*` (authenticated) | 120 | 1 min per user |
| `/api/admin/backup` | 2 | 1 hour |
| `/invite/*/claim` | 5 | 15 min per IP |

---

## Deployment

### Hosting: Railway

Railway is the Phase 1 host. Not because it's "self-hosted" (it isn't — be honest about this), but because it's fast to deploy and good enough for a family app.

### Environment Variables

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| SECRET_KEY | str | yes | — | 64-char hex string. Session signing + CSRF. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| DATABASE_URL | str | no | `sqlite:///data/family.db` | SQLite path. Railway: use persistent volume. |
| DATA_DIR | str | no | `/data` | Base directory for SQLite + photos + backups |
| FB_APP_ID | str | yes* | — | Facebook App ID (*required only if Facebook OAuth enabled) |
| FB_APP_SECRET | str | yes* | — | Facebook App Secret |
| FB_ENABLED | bool | no | false | Toggle Facebook OAuth on/off |
| FERNET_KEY | str | yes | — | Fernet encryption key for Facebook tokens. Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| BASE_URL | str | yes | — | Public URL: `https://martin.fm` or `https://family-book.up.railway.app` |
| REQUIRE_APPROVAL | bool | no | false | If true, new invite claims → pending state until admin approves |
| SMTP_HOST | str | no | — | For magic link emails. If unset, magic link auth is disabled. |
| SMTP_PORT | int | no | 587 | |
| SMTP_USER | str | no | — | |
| SMTP_PASS | str | no | — | |
| SMTP_FROM | str | no | — | Sender address for magic link emails |
| ENVELOPE_API_URL | str | no | — | Alternative to SMTP: use Envelope API for sending magic links |
| ENVELOPE_API_KEY | str | no | — | |
| ADMIN_EMAILS | str | no | — | Comma-separated. Persons with these emails get is_admin=true on first login. |
| LOG_LEVEL | str | no | INFO | |
| PORT | int | no | 8000 | Railway sets this automatically |

### Build & Start

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install uv && uv sync --frozen
COPY . .
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "${PORT:-8000}"]
```

**Startup sequence:**
1. Run Alembic migrations: `alembic upgrade head`
2. Load seed data if DB is empty: `python -m app.seed` (reads `data/family_tree.json`)
3. Start uvicorn

### Health Check

`GET /health` → 200: `{ "status": "ok", "db": "connected", "version": "1.0.0", "persons_count": N }`

Railway health check: configured to hit this endpoint.

### Persistent Storage

- Railway volume mounted at `/data`
- Contains: `family.db` (SQLite), `photos/` directory, `backups/` directory
- SQLite WAL mode enabled for concurrent read performance

### Backup Strategy (Day 1 — not deferred)

**Automated daily backup:**
1. Cron (Railway cron job or in-app scheduler): daily at 03:00 UTC
2. Copy SQLite DB: `sqlite3 /data/family.db ".backup /data/backups/family-$(date +%Y%m%d).db"`
3. Compress: gzip the backup
4. Retain: last 30 daily backups locally
5. Optional: upload to R2/S3 for off-site redundancy

**On-demand backup via admin panel:**
- `POST /api/admin/backup` → triggers immediate backup
- `GET /api/admin/backup/download` → downloads latest backup as .zip (DB + photos)

**Restore procedure:**
1. Stop the app
2. Replace `/data/family.db` with backup file
3. Run `alembic upgrade head` (in case backup is from older schema)
4. Start the app
5. Verify via `/health` endpoint

**Tested:** Restore procedure must be tested before go-live. Document the test date in CLAUDE.md.

### Domain

Phase 1: Railway auto-subdomain is fine. Tyler decides the final domain (`martin.fm` or other) before sending invites to family.

---

## Seed Data

### Initial Tree Structure

Tyler and Yuliya populate the initial family tree as a JSON seed file: `data/family_tree.json`.

```json
{
  "persons": [
    {
      "id": "pre-generated-uuid-1",
      "first_name": "Tyler",
      "last_name": "Martin",
      "is_admin": true,
      "is_root": false,
      "branch": "martin",
      "contact_email": "ty@tmrtn.com",
      "residence_country_code": "ES"
    },
    {
      "id": "pre-generated-uuid-2",
      "first_name": "[REDACTED]",
      "last_name": "Martin",
      "is_root": true,
      "branch": "shared",
      "birth_date_raw": "2021",
      "birth_date_precision": "year"
    }
  ],
  "parent_child": [
    { "parent_id": "pre-generated-uuid-1", "child_id": "pre-generated-uuid-2", "kind": "biological" }
  ],
  "partnerships": [
    { "person_a_id": "pre-generated-uuid-1", "person_b_id": "pre-generated-uuid-3", "kind": "married", "status": "active" }
  ]
}
```

**UUIDs must be pre-generated and stable.** Run once, paste into seed file, never change. These IDs become permanent references.

---

## Duplicate Detection & Merge (Phase 1.5)

### When Duplicates Arise

- Admin manually adds "Alexander Petrov"
- Later, Facebook OAuth links reveal the same person
- GEDCOM import (Phase 2) contains the same individual

### Detection

- On Person creation: check for existing matches by (first_name + last_name), email, facebook_id
- Fuzzy matching: Levenshtein distance ≤ 2 on full name
- Present candidates to admin: "This looks like an existing person. Merge?"

### Merge Flow

1. Admin selects two Person records to merge
2. System shows side-by-side comparison of all fields
3. Admin picks which value wins for each conflicting field
4. Merge executes:
   - Surviving record gets merged field values
   - All ParentChild, Partnership, Photo, ExternalIdentity records re-pointed to survivor
   - Merged record → soft-deleted (visibility=hidden, marked as merged)
   - AuditLog entry with full before/after
5. Inverse operation: admin can un-merge by restoring from audit log (manual process)

---

## Search & List Views (Phase 1)

### Search

- Full-text search on: first_name, last_name, nickname, birth_last_name, patronymic, bio
- Endpoint: `GET /api/persons?search=Sasha`
- SQLite FTS5 virtual table for performance
- HTMX live search: results update as user types (300ms debounce)

### List Views

| View | Route | Filters |
|------|-------|---------|
| All people | `/people` | Search, branch, country |
| By branch | `/people?branch=martin` | Country |
| By country | `/people?country=CA` | Branch |
| Memorials | `/people?memorial=true` | Branch |

### Birthday Calendar (Phase 2)

- Monthly view at `/birthdays`
- Upcoming birthdays highlighted (next 30 days)
- Only shows month + day (no year) for non-admin viewers

### World Map (Phase 2)

- `/map` — pins for each person with residence_country_code
- Clustered by country
- Click cluster → shows person list for that country
- Lightweight: use Leaflet.js with OpenStreetMap tiles (no Google Maps, no API key)

---

## Phase Plan (revised)

### Phase 1 — MVP (target: 1-2 weeks)
- [ ] Repo setup + CLAUDE.md + .env.example
- [ ] SQLite data model (Person, ParentChild, Partnership, UserSession, AuditLog, Photo)
- [ ] Alembic migrations
- [ ] Invite link auth (create invite, claim invite, session)
- [ ] Magic link email auth (send link, claim link, session)
- [ ] Admin CRUD: create/edit/delete persons
- [ ] Admin: create/edit relationships (parent-child + partnerships)
- [ ] Admin: manage invites
- [ ] Admin: approval queue (if REQUIRE_APPROVAL=true)
- [ ] Tree visualization (D3, single page, pan/zoom, tap for card)
- [ ] Person cards (HTMX slide-out panel)
- [ ] Person list view with search + branch/country filters
- [ ] Photo upload + auth-gated serving
- [ ] Seed data loader (JSON → DB)
- [ ] Automated daily backup
- [ ] Admin backup/download UI
- [ ] Health endpoint
- [ ] Dockerfile + Railway deploy
- [ ] Mobile-first responsive design

### Phase 1.5 — Hardening (1 week)
- [ ] Duplicate detection on person creation
- [ ] Merge UI (side-by-side, admin picks winner)
- [ ] Per-field visibility enforcement
- [ ] Audit log viewer in admin panel
- [ ] Rate limiting
- [ ] Restore procedure test + documentation

### Phase 2 — Enrichment (1-2 weeks)
- [ ] Facebook OAuth as optional profile enrichment
- [ ] i18n: en, ru, es static catalogs
- [ ] Relationship term computation (with gendered Russian labels)
- [ ] Birthday calendar
- [ ] World map (Leaflet + OpenStreetMap)
- [ ] GEDCOM import pipeline (stage → review → accept)
- [ ] Graph-distance privacy engine

### Phase 3 — Import & Sync
- [ ] Facebook data export email ingestion via Envelope
- [ ] WhatsApp profile photo sync via wacli
- [ ] `user_friends` + `user_photos` (requires Facebook App Review)

### Phase 4 — Federation (if ever)
- [ ] Federation API
- [ ] Cross-instance graph linking
- [ ] ActivityPub / GoToSocial (optional)

---

## Human-Only Bottlenecks

1. **Tyler + Yuliya:** Populate `data/family_tree.json` seed file (one evening)
2. **Tyler:** Register Facebook Developer App (~30 min, only if enabling Facebook)
3. **Tyler:** Generate pre-stable UUIDs for seed file
4. **Tyler:** Decide domain (martin.fm or other)
5. **Tyler:** Configure SMTP or Envelope for magic link emails
6. **Tyler + Yuliya:** Send invite links to family via WhatsApp/Telegram
7. **Tyler:** Curate Russian relationship terms with Yuliya (for Phase 2 i18n)

---

## Non-Goals

- This is NOT a social network replacement
- This is NOT a genealogy research tool (no Ancestry.com integration)
- This is NOT public-facing — invite-only by design
- No user-generated content moderation needed (it's family)
- No monetization. Ever.
- No claim of "self-hosted" when running on Railway — it's Tyler's account, not Tyler's hardware
- No runtime LLM calls in production

---

## Name

**Family Book** / **Libro de Familia** / **Семейная Книга**
