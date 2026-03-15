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

### Moment

The beating heart of Family Book. A reverse-chronological feed of family life.

| Field | Type | Required | Default | Constraints | Notes |
|-------|------|----------|---------|-------------|-------|
| id | UUID | yes | auto | PK | |
| person_id | UUID | yes | — | FK → Person.id | Who this Moment is about (or who posted it) |
| kind | enum | yes | — | photo, video, text, milestone, memorial | |
| title | str | no | null | max 300 | Optional headline: "First steps!", "Graduation day" |
| body | str | no | null | max 5000 | Caption, description, or milestone text |
| media_ids | JSON | no | [] | Array of Photo.id UUIDs | Photos/videos attached to this Moment |
| milestone_type | enum | no | null | birth, first_steps, first_words, first_day_school, graduation, engagement, marriage, divorce, new_home, travel, death, birthday, anniversary, custom | Only for kind=milestone |
| occurred_at | datetime | yes | now() | | When the Moment happened (may be backdated for imports) |
| occurred_precision | enum | no | exact | exact, day, month, year | For imported/historical Moments |
| source | enum | yes | manual | manual, whatsapp_import, facebook_import, instagram_import, auto_generated | |
| visibility | enum | yes | members | members, admins, hidden | Who can see this Moment |
| posted_by | UUID | no | null | FK → Person.id | Who uploaded/created it |
| created_at | datetime | yes | now() | | |

**Auto-generated Moments:**
- Birthday: created by cron, `kind=milestone`, `milestone_type=birthday`, `source=auto_generated`
- Anniversary: same pattern, computed from Partnership.start_date
- Memorial date: annual reminder on death_date

**WhatsApp-imported Moments:**
- `kind=photo` or `kind=video`, `source=whatsapp_import`
- `occurred_at` = original WhatsApp message timestamp
- `person_id` = the sender (as mapped by admin)
- `body` = message text that accompanied the photo (if any)

### MomentReaction

| Field | Type | Required | Default | Constraints | Notes |
|-------|------|----------|---------|-------------|-------|
| id | UUID | yes | auto | PK | |
| moment_id | UUID | yes | — | FK → Moment.id, ON DELETE CASCADE | |
| person_id | UUID | yes | — | FK → Person.id | |
| emoji | str | yes | — | max 10 chars, single emoji | ❤️ 😂 😢 🎉 🙏 😮 |
| created_at | datetime | yes | now() | | |

**Constraints:** Unique on (moment_id, person_id). One reaction per person per Moment.

### MomentComment

| Field | Type | Required | Default | Constraints | Notes |
|-------|------|----------|---------|-------------|-------|
| id | UUID | yes | auto | PK | |
| moment_id | UUID | yes | — | FK → Moment.id, ON DELETE CASCADE | |
| person_id | UUID | yes | — | FK → Person.id | |
| body | str | yes | — | max 2000 chars | Plain text + emoji. No markdown. |
| created_at | datetime | yes | now() | | |

### GedcomImportBatch (specced now, built later)

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
| `/` | member → Moments feed; anonymous → landing page | Moments feed (logged in) or "Family Book" + login (anonymous) | Server + HTMX |
| `/invite/{token}` | none | Claim page — "Welcome, [name]! Confirm to join." | Server |
| `/login` | none | Login form — magic link email + Facebook option | Server |
| `/tree` | member | Full-page D3 tree visualization | Server shell + D3 client |
| `/people` | member | List view — searchable, filterable by branch/country | Server + HTMX |
| `/people/{id}` | member | Person detail — bio, relationships, contact, Moments by this person | Server + HTMX |
| `/profile` | member | Own profile edit form | Server + HTMX |
| `/admin` | admin | Dashboard — pending approvals, recent audit log, invite links | Server + HTMX |
| `/admin/people/new` | admin | Create person form | Server + HTMX |
| `/admin/people/{id}/edit` | admin | Edit person form | Server + HTMX |
| `/admin/relationships` | admin | Relationship manager — add/edit parent-child + partnerships | Server + HTMX |
| `/admin/backup` | admin | Backup/export controls | Server + HTMX |
| `/admin/import/whatsapp` | admin | WhatsApp group export upload + name mapping | Server + HTMX |

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

### The Core UX Insight

Family Book is NOT a social network that family members post to. It is a **sovereign archive** that sits underneath the platforms they already use. The family keeps using WhatsApp, Facebook, Instagram, iMessage — whatever they use today. Family Book silently ingests, archives, organizes, and makes it permanent and searchable.

**The cold start problem:** Day one, the archive is empty and nobody will switch from WhatsApp to post on a new website.

**The solution:** Be a parasite first, be useful second, be better third.

1. **Parasite:** Ingest from everywhere. WhatsApp export, Facebook export, email forwarding, share sheet. Fill the archive with EXISTING content. Family changes zero behavior. Tyler does the setup once.
2. **Useful:** Once there's content, Family Book becomes the best place to FIND anything. "What was that photo from Christmas 2024?" You can't search WhatsApp for that. You can search Family Book.
3. **Better:** The feed, tree, birthday reminders, agent API — these become reasons people start posting directly. Not because Tyler forced them, but because it's genuinely better.

**Operational model:** Zero-touch. Tyler sets up ingestion once. Content flows in automatically. Tyler intervenes only for exceptions (merge conflicts, new family members, relationship changes). If Tyler has to manually run exports every week, the archive falls behind and dies.

### Adaptive Home Screen

The same URL (`/`), different experience based on who you are:

| User Type | Detection | Home Screen |
|-----------|-----------|-------------|
| Admin (Tyler/Yuliya) | `is_admin = true` | Dashboard: new content, pending imports, system health, quick actions |
| Active member | `last_activity < 7 days` | Timeline feed: reverse-chronological stream of recent Moments |
| Casual member | `last_activity > 7 days` | "What's new" summary: photo highlights + milestones since last visit |
| First visit | `visit_count < 3` | Guided tour: the tree, key faces, "this is your family" |
| Child/teen (future) | Age-based flag or custom role | Face explorer: tap faces on the tree, see their photos |

No algorithm. No ML. Simple rules based on role and visit recency. Transparent and predictable.

Anonymous visitors → landing page with login/invite options.

### Moments Feed

The Moments feed is the archive viewer. Content comes IN from ingestion pipelines (WhatsApp, email, Facebook, share sheet, direct upload). The feed DISPLAYS it in reverse-chronological order.

**Layout:** Single-column, reverse-chronological, infinite scroll.

```
┌─────────────────────────────────┐
│  🏠 Family Book    🌳 👥 ⚙️    │  ← nav: home (feed), tree, people, settings
├─────────────────────────────────┤
│  [+ New Moment]                 │  ← floating action button (mobile: bottom-right)
├─────────────────────────────────┤
│  ┌─────────────────────────────┐│
│  │ 📷  Tyler Martin            ││  ← source person
│  │     2h ago · via WhatsApp · Madrid ││  ← time + source + location
│  │                             ││
│  │  [═══════════════════════]  ││  ← photo (full-width, aspect-ratio preserved)
│  │  [═══════════════════════]  ││
│  │  [═══════════════════════]  ││
│  │                             ││
│  │  "First time on skis! ⛷️"   ││  ← caption
│  │                             ││
│  │  ❤️ 4   💬 2               ││  ← reactions + comment count
│  └─────────────────────────────┘│
│                                 │
│  ┌─────────────────────────────┐│
│  │ 🎂  Auto-generated          ││
│  │     Today                   ││
│  │                             ││
│  │  "Happy birthday Дядя Саша! ││
│  │   🎂 He turns 58 today."   ││
│  │                             ││
│  │  [📷 Дядя Саша's photo]    ││  ← profile photo as hero image
│  │                             ││
│  │  ❤️ 7                      ││
│  └─────────────────────────────┘│
│                                 │
│  ┌─────────────────────────────┐│
│  │ 📷  Yuliya Martin           ││
│  │     Yesterday · via Email · Madrid ││
│  │                             ││
│  │  [photo] [photo] [photo]    ││  ← multi-photo: horizontal scroll or grid
│  │                             ││
│  │  "Пельмени с бабушкой! 🥟"  ││
│  │                             ││
│  │  ❤️ 12  💬 5               ││
│  └─────────────────────────────┘│
└─────────────────────────────────┘
```

**Moment Card Anatomy:**

| Element | Source | Notes |
|---------|--------|-------|
| Source person avatar | Person.photo_url (circle, 40px) | Tap → person card |
| Source person name | Person display name | Tap → person profile |
| Timestamp | Moment.occurred_at | Relative: "2h ago", "Yesterday", "March 10" |
| Source platform | Moment.source | "via WhatsApp", "via Email", "via Facebook", "via direct upload". Shows how content arrived. |
| Location | Person.residence or EXIF data | Optional. Only shown if present. |
| Media | Photo(s) / Video | Full-width. Single photo: fill card. Multi-photo (2-4): grid. 5+: grid with "+N more" overlay. Video: inline player with poster frame. |
| Caption | Moment.body | Max 3 lines visible, "more…" expands. Supports emoji. No markdown. |
| Milestone badge | Moment.milestone_type | 🎂 birthday, 💒 wedding, 🎓 graduation, 👶 new baby, 🕊️ memorial, ✈️ travel. Shown as icon + colored banner. |
| Reactions | MomentReaction records | Emoji row: ❤️ 4, 😂 2, etc. Tap to add/remove. |
| Comment count | Count of MomentComment | Tap → expands comment thread inline (HTMX load) |

**Direct Posting (optional, not the primary content source):**

Most content arrives via ingestion pipelines (see Ingestion Architecture below). But for family members who WANT to post directly, the feed has a chat-style input bar at the bottom — WhatsApp-level friction:

1. Tap 📷 → pick/take photo(s) → caption (optional) → tap ✈️ send
2. Or type text → send (text-only Moment)

```
┌─────────────────────────────────────────────┐
│  📷  Share something with the family...  ✈️│
└─────────────────────────────────────────────┘
```

**Optional metadata (hidden, discoverable):**
- @ icon → tag a family member (autocomplete)
- Long-press send → backdate picker (for uploading old photos)
- These NEVER block the primary flow.

**Real-time updates:**
- SSE push: new Moments appear at top without refresh
- Badge on 🏠 tab: "3 new" when Moments arrive while browsing another page

**Infinite Scroll:**
- Initial load: 20 Moments
- Scroll to bottom → HTMX `hx-get="/api/moments?before={oldest_id}"` appends next 20
- End of feed: "You've reached the beginning! 📖"

**Filtering:**
- Default: all Moments from all family members
- Filter by person: `/moments?person={id}` (also accessible from person profile)
- Filter by branch: `/moments?branch=martin`
- Filter by type: `/moments?kind=milestone` (milestones only)
- Filter by year: `/moments?year=2024`
- Filters available via dropdown in nav bar, NOT a separate page

### Moment Reactions

Simple emoji reactions, not likes. Family members tap to react.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | UUID | yes | PK |
| moment_id | UUID | yes | FK → Moment.id |
| person_id | UUID | yes | FK → Person.id (who reacted) |
| emoji | str | yes | Single emoji: ❤️ 😂 😢 🎉 🙏 😮 max 1 reaction per person per moment |
| created_at | datetime | yes | |

**Constraints:** Unique on (moment_id, person_id). One reaction per person per Moment. Changing reaction replaces the old one.

**UI:** Below each Moment card, show aggregated emoji counts. Tap an emoji to toggle your own reaction. Long-press (mobile) or hover (desktop) to pick a different emoji from a small palette: ❤️ 😂 😢 🎉 🙏 😮

### Moment Comments

Lightweight threaded comments on Moments.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | UUID | yes | PK |
| moment_id | UUID | yes | FK → Moment.id |
| person_id | UUID | yes | FK → Person.id (who commented) |
| body | str | yes | Max 2000 chars. Plain text + emoji. No markdown. |
| created_at | datetime | yes | |

**UI:**
- Comment count shown on Moment card. Tap → expands inline comment thread (HTMX).
- Comments show: avatar (24px) + name + text + relative timestamp
- "Add a comment…" text field at bottom of thread
- Submit via Enter or tap send button
- New comments appear instantly (HTMX swap, no page reload)
- No nested replies. Flat thread. This is family, not Reddit.
- Admin can delete any comment. Members can delete their own.

### Moments API Endpoints

| Method | Path | Auth | Request | Success | Errors |
|--------|------|------|---------|---------|--------|
| GET | `/api/moments` | member | `?before=uuid&limit=20&person=uuid&branch=str&kind=str&year=int` | 200: `[MomentCard]` | 401 |
| POST | `/api/moments` | member | multipart: photos + `{ body?, person_id?, occurred_at?, kind }` | 201: `MomentCard` | 400, 401, 413 |
| DELETE | `/api/moments/{id}` | admin or poster | — | 204 | 401, 403, 404 |
| POST | `/api/moments/{id}/reactions` | member | `{ emoji }` | 200: `{ emoji, count }` | 400, 401, 404 |
| DELETE | `/api/moments/{id}/reactions` | member | — | 204 | 401, 404 |
| GET | `/api/moments/{id}/comments` | member | `?limit=50` | 200: `[Comment]` | 401, 404 |
| POST | `/api/moments/{id}/comments` | member | `{ body }` | 201: `Comment` | 400, 401, 404 |
| DELETE | `/api/comments/{id}` | admin or author | — | 204 | 401, 403, 404 |

**MomentCard response:**
```json
{
  "id": "uuid",
  "kind": "photo",
  "poster": { "id": "uuid", "display_name": "Tyler Martin", "photo_url": "/photos/..." },
  "about": { "id": "uuid", "display_name": "Luna" },
  "body": "First time on skis! ⛷️",
  "media": [{ "id": "uuid", "url": "/photos/uuid/ski.jpg", "width": 1200, "height": 900 }],
  "milestone_type": null,
  "occurred_at": "2026-03-15T09:30:00Z",
  "reactions": { "❤️": 4, "😂": 2 },
  "my_reaction": "❤️",
  "comment_count": 3,
  "created_at": "2026-03-15T09:35:00Z"
}
```

### Ingestion Architecture (Zero-Touch)

Content flows INTO Family Book through multiple automated pipelines. Tyler sets up each pipeline once. After that, it runs unattended.

| Pipeline | Automation Level | How It Works | Tyler's Setup Work |
|----------|-----------------|--------------|-------------------|
| **Email** (Envelope) | Fully automatic | family@martin.fm receives forwarded photos. Envelope parses sender, extracts images, creates Moments. | Configure Envelope route (once) |
| **WhatsApp group export** | Semi-automatic | Tyler exports family group chat with media. Upload .zip → parser extracts all photos + captions + sender mapping. | Export + upload (~15 min/quarter) |
| **Facebook data export** | Semi-automatic | Family members request FB data export. Forward download email to family@martin.fm. Envelope catches it, ingestion is automatic. | Tell family members once |
| **Instagram data export** | Semi-automatic | Same pattern as Facebook. | Tell family members once |
| **Share sheet (PWA)** | Fully automatic | Family members install PWA. "Share to Family Book" appears in phone's share sheet. Photo goes directly to archive. | Family members install PWA (2 taps) |
| **Telegram bot** | Fully automatic | Send photos to Family Book bot → auto-creates Moments. | Set up bot (once) |
| **Auto-generated milestones** | Fully automatic | Cron generates birthday, anniversary, memorial Moments from graph data. | Zero — automatic |
| **WhatsApp bridge** | TBD — needs research | Continuous monitoring of family group. Highest value, highest complexity. | TBD |

**Ingestion processing pipeline (all sources):**
1. Content arrives (email, upload, share, bot)
2. Extract: photos, videos, sender identity, timestamp, caption text
3. Match sender to Person record (by email, phone, name, or Telegram ID)
4. Dedup by file hash (SHA-256) — don't import the same photo twice
5. Create Photo records + Moment record (with source platform tag)
6. If sender can't be matched → queue for admin review
7. Moment appears in feed. SSE push notifies active viewers.

### Grandparent Experience (Push-First Design)

Grandparents will NOT sign into a website every day. They open WhatsApp. They check texts. They look at email. Family Book has to **come to them**.

**The website is the archive. The experience for grandparents is push notifications with actual content — not links.**

#### Push Channels — Global Delivery Router

Family Book must deliver rich media notifications to family members across every continent. No single channel works globally. The system routes to the best channel per person based on their country + preference.

| Channel | Coverage | Content | Cost | Interaction |
|---------|----------|---------|------|-------------|
| **MMS** (Twilio) | 🇺🇸🇨🇦 only | Photo + caption in native texts | ~$0.02/msg | Reply emoji → reaction |
| **WhatsApp Business** | 🌍 ~80% global (LatAm, Europe, Africa, Asia) | Photo + caption + reaction buttons | ~$0.005-0.08/msg | Reply emoji → reaction |
| **Telegram bot** | 🌍 strong in Russia/E.Europe, growing globally | Photo + caption + inline buttons | FREE | Tap button → reaction |
| **Signal** (OpenClaw bridge) | 🌍 growing, privacy-first users | Photo + caption via E2E encrypted channel | FREE (bridge cost only) | Reply emoji → reaction |
| **Email** | 🌍 100% (universal fallback) | Rich HTML digest with embedded photos | ~$0.0001/email | Click reaction link → reaction |

**Routing logic (per person, configured once by admin):**

| Person's preference | Primary | Fallback |
|--------------------|---------|----------|
| `push_channel = auto` | Route by country: US/CA → MMS, LatAm/Europe/Africa → WhatsApp, Russia → Telegram | Email |
| `push_channel = whatsapp` | WhatsApp Business API | Email |
| `push_channel = telegram` | Telegram bot | Email |
| `push_channel = signal` | Signal via OpenClaw bridge | Email |
| `push_channel = sms` | SMS/MMS (MMS if US/CA, SMS+link if international) | Email |
| `push_channel = email` | Email only | — |

**Auto-routing by country (when `push_channel = auto`):**

| Country/Region | Auto-routes to | Why |
|---------------|---------------|-----|
| US, Canada | MMS | Native text messaging with photos |
| Latin America, Western Europe, Africa, Middle East, South/SE Asia | WhatsApp | 80%+ penetration |
| Russia, Eastern Europe, Central Asia | Telegram | Dominant platform, free API |
| China | Email (WeChat integration deferred) | WeChat API is a separate world |
| Japan | Email (LINE integration deferred) | LINE dominant but API complex |
| South Korea | Email (KakaoTalk deferred) | KakaoTalk dominant but API complex |
| Fallback / Unknown | Email | Always works |

**WhatsApp Business API considerations:**
- Requires approved message templates for outbound notifications
- Per-message cost varies by country (India cheapest, EU most expensive)
- 24-hour conversation window: first message needs approved template, replies within 24h are cheaper
- Needs WhatsApp Business account registration + Meta verification
- This is the MOST important integration after email — covers the largest global audience
- Research needed: current pricing tiers, template approval process, monthly costs for a family of 50

**Signal — the philosophically aligned option:**
- E2E encrypted, nonprofit, open protocol. If Family Book is about data sovereignty, Signal shares that DNA.
- OpenClaw already has a working Signal bridge — proven delivery channel.
- No business API (requires unofficial bridge), no rich interaction (no inline buttons).
- But: photo delivery + emoji reply → reaction works through the OpenClaw bridge.
- Position: peer to Telegram as a preference option, not auto-routed by country (Signal adoption is preference-based, not geography-based).

**Channel resilience — the real argument for multi-channel:**
- If Telegram goes dark in Russia (happening now), system falls back to email.
- If WhatsApp gets banned somewhere, same thing.
- If MMS dies because carriers kill SMS, router adapts.
- No single channel dependency. No "our family communication breaks because one government had a bad day."
- Email is federated and no single government controls it. It's always the final fallback.

**The principle:** Family Book doesn't care HOW the notification reaches grandma. It cares THAT it reaches her, with the photo, and she can react. The router abstracts the channel. Adding new channels later (LINE, WeChat, RCS) is just a new adapter.

#### Two-Way Reactions via Push

Grandma doesn't need to log in to react. She reacts WHERE she already is:

- **SMS:** Reply "❤️" or "😂" → Family Book parses the emoji → creates MomentReaction
- **Email:** Click a reaction link at the bottom of the digest → registers reaction via API
- **Telegram:** Tap inline button (❤️ 😂 🎉) → callback creates reaction

#### Push Notification Preferences (per person)

| Setting | Options | Default |
|---------|---------|---------|
| `push_channel` | auto, whatsapp, telegram, signal, sms, email, none | auto |
| `push_phone` | E.164 phone number | from Person.contact_whatsapp or contact_signal |
| `push_email` | email address | from Person.contact_email |
| `push_telegram_id` | Telegram user ID | from linked Telegram account |
| `push_whatsapp` | E.164 phone number (WhatsApp-registered) | from Person.contact_whatsapp |
| `push_frequency` | realtime, daily_digest, weekly_digest | weekly_digest |
| `push_milestones` | bool — always push births, deaths, marriages regardless of frequency | true |

Admin (Tyler) configures push preferences for each family member. Family members can later adjust their own via profile settings.

#### The "Same Space" Problem

WhatsApp groups work because everyone is there together — reacting, replying, present. Family Book's web feed will feel empty compared to a buzzing group chat.

**Solution:** The push notifications CREATE the "same space" feeling:
- Grandma gets MMS of baby photo → hearts it via SMS reply
- Cousin Dmitri gets Telegram notification → reacts with 🎉
- Tyler sees both reactions appear in the Family Book feed
- Everyone is participating from their preferred platform, but the reactions converge in one place

The website shows the aggregated engagement. The EXPERIENCE happens on each person's preferred channel. Family Book is the **hub** that connects platforms, not a destination that replaces them.

### Grandparent Roles (Matriarch/Patriarch)

Grandparents aren't just consumers — they're co-organizers and privacy guardians for their branch.

| Permission | Description |
|-----------|-------------|
| Branch curator | Approve/hide photos of grandchildren in their branch. "This photo is too private for cousins." |
| Family historian | Add context to old photos, write bios for deceased relatives, annotate the tree with stories. "This is your дедушка at age 20 in Leningrad." |
| Branch welcomer | Send invites to family members on their side. Onboard their own relatives. |
| Privacy guardian | Set default visibility for their branch's content. "Grandchildren's photos are immediate family only." |

**Implementation:** New role `branch_admin` with scope limited to Person records within their branch. Not full admin — can't delete people, can't change tree structure outside their branch, can't access system settings. But within their branch, they have meaningful authority.

### Family Governance (Lightweight Consent Model)

Not everything needs a vote. Most actions are individual. But decisions about others require consent from the people affected. Graph distance determines who has standing.

| Decision | Who Votes | Threshold |
|----------|-----------|-----------|
| Adding a minor's photos | Both parents | Both must approve |
| Memorial creation (when someone dies) | Spouse + children | Majority of immediate family |
| Estrangement / hiding someone | Immediate family of the person | Majority |
| Re-adding an ex after reconciliation | Both parties | Both must approve |
| Escalating content visibility (private → extended family) | Subject (or subject's parents if minor) | Subject approves |

**Everything else is individual:** posting your own photos, editing your own bio, reacting, commenting. No vote needed.

**Principle:** You control your own data. Decisions about others require consent from the people the graph says are affected.

### Navigation

| Icon | Route | Label |
|------|-------|-------|
| 🏠 | `/` | Home (adaptive: dashboard / feed / summary / tour) |
| 🌳 | `/tree` | Tree |
| 👥 | `/people` | People |
| ⚙️ | `/profile` (member) or `/admin` (admin) | Settings / Admin |

Mobile: bottom tab bar (4 icons). Desktop: top nav bar.

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

## WhatsApp Group Export Ingestion (Bootstrap — Critical Path)

This is how the family gets into Family Book. Not manual JSON seed files. Not one-by-one admin entry. The family WhatsApp group IS the family database — it just needs to be imported.

### How It Works

1. Tyler opens the family WhatsApp group → Settings → Export Chat → **"Include Media"**
2. WhatsApp produces a `.zip` containing:
   - `_chat.txt` — full message history with timestamps and sender names
   - Media files: `IMG-20260315-WA0001.jpg`, `VID-...mp4`, `PTT-...opus`, etc.
3. Tyler uploads the `.zip` to Family Book admin panel (`/admin/import/whatsapp`)
4. Parser extracts:
   - **Unique contact names** → candidate Person records
   - **Photos with timestamps** → candidate Moments + Photo records
   - **Videos** → candidate Moments (stored as media)
   - **System messages** → group membership history ("X added Y", "X left")
5. Admin mapping UI: Tyler sees a list of extracted contact names and matches each to a Person record (existing or new)
6. After mapping, photos/videos are assigned to the correct Person and become Moments
7. Historical photos are backdated to their original WhatsApp timestamps

### WhatsApp Export Format

The chat text file format varies by OS and locale:

```
# iOS format:
[DD/MM/YYYY, HH:MM:SS] Contact Name: message text
[DD/MM/YYYY, HH:MM:SS] Contact Name: <attached: IMG-20260315-WA0001.jpg>

# Android format:
MM/DD/YY, HH:MM - Contact Name: message text
MM/DD/YY, HH:MM - Contact Name: IMG-20260315-WA0001.jpg (file attached)

# System messages:
[DD/MM/YYYY, HH:MM:SS] Contact Name added Contact Name2
[DD/MM/YYYY, HH:MM:SS] Contact Name left
[DD/MM/YYYY, HH:MM:SS] Contact Name changed the group description
```

### Parser Requirements

| Field | Source | Notes |
|-------|--------|-------|
| Contact names | Message sender field | Unique set = candidate person list |
| Photos | .jpg/.jpeg/.png files in zip | Matched to sender by filename reference in chat text |
| Videos | .mp4 files in zip | Same matching as photos |
| Timestamps | Message timestamp | Original date/time for backdating Moments |
| Message text | Message body | Optional: import as Moment captions or discard (admin choice) |

### Limitations

- **No phone numbers in export.** Contact names only. Tyler must manually map names to people.
- **Media limit:** WhatsApp exports ~10,000 most recent messages with media, ~40,000 without. For large groups with years of history, multiple exports may be needed (or use the GDPR account data export for full history).
- **Date format varies** by device locale. Parser must handle both DD/MM/YYYY and MM/DD/YY formats.
- **Duplicate media:** Same photo may appear in multiple exports. Dedup by file hash (SHA-256).
- **Voice notes (.opus):** Import but flag as audio, not photo/video. Optional playback in Moments.

### Admin Mapping UI

After upload, the admin sees:

```
WhatsApp Import: "Martin Family Group" — 847 messages, 312 photos, 23 videos

Contact Name Mapping:
┌─────────────────────┬──────────────────────────────┬──────────┐
│ WhatsApp Name        │ Match To                     │ Status   │
├─────────────────────┼──────────────────────────────┼──────────┤
│ Tyler                │ [Tyler Martin ▾] (auto)      │ ✅ Mapped │
│ Yuliya               │ [Yuliya Martin ▾] (auto)     │ ✅ Mapped │
│ Мама                 │ [Create new person ▾]        │ ⚠️ New    │
│ Shelley              │ [Shelley Martin ▾] (auto)    │ ✅ Mapped │
│ Dmitri               │ [Create new person ▾]        │ ⚠️ New    │
│ +7 912 345 6789      │ [Search... ▾]                │ ❌ Unmatched│
└─────────────────────┴──────────────────────────────┴──────────┘

[Import 312 photos + 23 videos as Moments] [Preview first] [Cancel]
```

Auto-matching: fuzzy match WhatsApp contact names against existing Person.first_name + Person.nickname. Exact match → auto-mapped. Fuzzy match → suggested with confidence score. No match → "Create new person" with pre-filled name.

### Data Flow

```
WhatsApp .zip
    │
    ▼
Parse _chat.txt → extract unique senders + message-media mapping
    │
    ▼
Extract media files → dedup by SHA-256 hash
    │
    ▼
Admin mapping UI → match senders to Person records
    │
    ▼
Create new Person records for unmapped senders
    │
    ▼
Import photos/videos → Photo records + Moment records (backdated)
    │
    ▼
Family Book is pre-populated with years of family photos on day one
```

## WhatsApp Profile Sync (optional, via wacli)

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

## Phase Plan (no phases — features, not phases)

Stop thinking in phases. Every feature below is part of the complete product vision. Build order is determined by dependency graph, not arbitrary phase numbers. The spec describes the full product. The build agent decides implementation order based on what depends on what.

### Foundation (must exist before anything else)
- [ ] Repo setup + CLAUDE.md + .env.example
- [ ] SQLite data model (Person, ParentChild, Partnership, UserSession, AuditLog, Photo, Moment)
- [ ] Alembic migrations
- [ ] Health endpoint
- [ ] Dockerfile + Railway deploy with persistent volume
- [ ] Automated daily backup + admin backup/download UI

### Bootstrap (how the family gets in)
- [ ] WhatsApp group export ingestion (THE primary bootstrap — see WhatsApp Ingestion section)
- [ ] Admin name-to-person mapping UI (match WhatsApp contact names to Person records)
- [ ] Admin CRUD: create/edit/delete persons
- [ ] Admin: create/edit relationships (parent-child + partnerships)
- [ ] Seed data loader (JSON → DB, for manual override/supplement)
- [ ] Invite link auth (create invite, claim invite, session)
- [ ] Magic link email auth (send link, claim link, session)
- [ ] Admin: manage invites + approval queue

### The Living Room (what family members see)
- [ ] Tree visualization (D3, pan/zoom, tap for card, mobile-friendly)
- [ ] Person cards (HTMX slide-out panel)
- [ ] Person list view with search + branch/country filters
- [ ] Photo upload + auth-gated serving
- [ ] Moments feed (reverse-chronological, photos/videos/milestones)
- [ ] Moments posting (photo/video upload from mobile)
- [ ] Auto-generated milestone Moments (birthdays, anniversaries)
- [ ] Memorial mode for deceased persons
- [ ] Mobile-first responsive design

### Notifications (how the family stays connected)
- [ ] SMS/MMS notifications via Twilio (birthday reminders, milestone alerts, weekly digest)
- [ ] MMS photo delivery for key moments
- [ ] Email notifications (weekly digest with embedded photos, milestone alerts)
- [ ] Email ingestion via Envelope (forward photos → Moments)

### Data Liberation (import everything)
- [ ] Facebook data export ingestion (photos, profile, staged for review)
- [ ] Instagram data export ingestion
- [ ] WhatsApp chat export ingestion (historical photo recovery from ALL family chats)
- [ ] GEDCOM import pipeline (stage → review → accept/merge/reject)
- [ ] Facebook OAuth as optional profile enrichment
- [ ] TikTok/Instagram oEmbed in Moments

### Enrichment
- [ ] i18n: en, ru, es static catalogs + gendered Russian relationship terms
- [ ] Birthday calendar
- [ ] World map (Leaflet + OpenStreetMap)
- [ ] Duplicate detection + merge UI
- [ ] Audit log viewer in admin panel
- [ ] Rate limiting
- [ ] Graph-distance privacy engine + life-event mutations

### Optional Channels
- [ ] Telegram bot (notifications + photo upload for power users)
- [ ] Signal bridge via OpenClaw

### Long-term
- [ ] Federation API (cross-instance family linking)
- [ ] ActivityPub / GoToSocial

---

## Human-Only Bottlenecks

1. **Tyler:** Export the family WhatsApp group chat with media (~2 minutes)
2. **Tyler + Yuliya:** Map WhatsApp contact names to real family members in admin UI (~30 min)
3. **Tyler + Yuliya:** Add relationship edges (parent-child, partnerships) for mapped people (~1 evening)
4. **Tyler:** Decide domain (martin.fm or other)
5. **Tyler:** Configure SMTP or Envelope for magic link emails
6. **Tyler + Yuliya:** Send invite links to family
7. **Tyler:** Register Facebook Developer App (~30 min, only if enabling Facebook)
8. **Tyler + Yuliya:** Curate Russian relationship terms (for i18n)

---

## Family Graph API (Agent Context Layer)

The family graph isn't just for humans browsing a tree. It's a **sovereign context layer** that any authorized agent can query to understand a person in the context of their family.

### Use Cases

| Agent | What It Needs | Family Graph Provides |
|-------|--------------|----------------------|
| In-home caregiving robot (2030s) | Who lives here? Who visits? Who to call in emergency? | Household members, relationship distance → priority, emergency contacts sorted by closeness |
| Personal AI assistant | "Remind me about mom's birthday" — which mom? | Unambiguous identity resolution via relationship graph |
| Smart home | "Let Shelley in" — who is Shelley? Is she authorized? | Family membership + relationship = implicit access control |
| Estate planning agent | Who are the legal heirs? What's the family structure? | Complete relationship graph with legal relationship types (biological, adoptive, step) |
| Medical emergency agent | Next of kin? Blood relatives? Allergies in family? | Relationship graph with biological/non-biological distinction |
| Travel assistant | "Book flights for the family" — which family? | Household composition, ages, nationalities, passport countries |
| Photo organization AI | Who is in this photo? | Face-to-name mapping + relationship context |
| Language learning agent | What languages does grandma speak? | Person.languages + relationship path = "learn Russian to talk to бабушка" |

### API Design

Read-only. Scoped by API key permissions. Never exposes data beyond the requesting agent's authorization level.

#### Agent Endpoints

| Method | Path | Auth | Response | Notes |
|--------|------|------|----------|-------|
| GET | `/api/agent/person/{id}` | API key | PersonContext | Full person card + relationship labels |
| GET | `/api/agent/household/{person_id}` | API key | `[PersonSummary]` | People who share a residence with this person |
| GET | `/api/agent/emergency-contacts/{person_id}` | API key | `[{ person, relationship, phone, priority }]` | Sorted by relationship closeness |
| GET | `/api/agent/relatives/{person_id}` | API key | `[{ person, relationship_label, distance }]` | All relatives with computed labels |
| GET | `/api/agent/relatives/{person_id}?max_distance=2` | API key | `[{ person, relationship_label, distance }]` | Immediate family only |
| GET | `/api/agent/milestones/{person_id}` | API key | `[Milestone]` | Upcoming birthdays, anniversaries, memorial dates |
| GET | `/api/agent/context/{person_id}` | API key | FamilyContext | Everything an agent needs to understand this person |

#### FamilyContext Response

```json
{
  "person": {
    "id": "uuid",
    "display_name": "Tyler Martin",
    "languages": ["en", "es", "de", "fr", "ru"],
    "residence": { "place": "Madrid, Spain", "country_code": "ES", "timezone": "Europe/Madrid" },
    "age": 44
  },
  "household": [
    { "name": "Yuliya Martin", "relationship": "wife", "languages": ["ru", "en", "es"] },
    { "name": "[redacted]", "relationship": "daughter", "age": 4 }
  ],
  "emergency_contacts": [
    { "name": "Yuliya Martin", "relationship": "wife", "phone": "+34...", "priority": 1 },
    { "name": "Father Martin", "relationship": "father", "phone": "+1...", "priority": 2, "timezone": "America/Vancouver" }
  ],
  "upcoming": [
    { "type": "birthday", "person": "Дядя Саша", "date": "2026-03-22", "days_away": 7 }
  ],
  "family_size": 47,
  "countries": ["ES", "CA", "RU", "US"],
  "branches": ["martin", "semesock", "maternal"]
}
```

### API Key Scoping

| Scope | Access | Use Case |
|-------|--------|----------|
| `household` | Own household members only | Smart home, caregiving robot |
| `immediate` | Distance ≤ 2 (parents, children, siblings, spouse) | Personal assistant |
| `extended` | Distance ≤ 4 (cousins, aunts/uncles) | Travel planning, event coordination |
| `full` | Entire graph (admin only) | Estate planning, medical emergency |

API keys are created by admin, scoped per agent, and logged in the audit trail. Revocable at any time.

### The Sovereignty Principle

This API exists so that **agents come to your family graph** — your family graph never goes to them. The data stays in your SQLite. The agent makes authenticated read requests. If the agent's vendor goes bankrupt, changes terms, or gets acquired, you revoke the API key. Your data hasn't moved.

This is the inverse of how every smart assistant works today (you upload your contacts to their cloud). Family Book says: your cloud queries my data, under my terms, with my permission, revocable at my discretion.

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
