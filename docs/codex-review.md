# Family Book Red-Team Review

## Overall Verdict — REVISE

This should not ship as written.

The concept is good. The current spec and plan are not one product. They are three products jammed together:

- a private family directory and photo viewer
- a genealogy system with real kinship edge cases
- a federated social protocol

That mixture is what is making the plan feel simultaneously overbuilt and underspecified.

The biggest problem is not FastAPI or SQLite. The biggest problem is that the data model and auth model are too naive for genealogy, while the permission/federation ambitions are too ambitious for an MVP.

The most important call: cut scope hard. Ship a solid private family tree first. Defer graph ACLs, federation, ActivityPub, OpenRouter translation, and any claim that Facebook import will auto-build the family graph.

## Core Contradictions — REVISE

- `SPEC.md:11` promises automatic import and graph-based privacy as part of the product vision. `docs/implementation-plan.md:7` explicitly defers graph-distance privacy, imports, i18n, world map, birthday calendar, PWA, and ActivityPub. The spec is selling a product the Phase 1 plan does not build.
- `SPEC.md:45-48` promises Facebook permissions for friends and photos. `docs/implementation-plan.md:235-237` correctly says Phase 1 can only use `public_profile` and `email` without App Review, and that everyone must be added as a tester. The user journey is inaccurate.
- The repo plan is not HTMX. `docs/implementation-plan.md:554-565` describes server-rendered shells plus client-side `fetch()` and custom JS. That is a reasonable architecture, but it is not "FastAPI + HTMX". Pick one and design for it.
- `SPEC.md:287` says cache translations in SQLite. `SPEC.md:299` says "JSON files, NOT SQLite." That is an unresolved design decision, not a detail.
- `SPEC.md:160` calls federation "Phase 2". `SPEC.md:266-268` later makes federation/ActivityPub "Phase 5 optional". The roadmap is internally inconsistent.
- `SPEC.md:191-198` claims strong privacy and even a "client-side passphrase option", but the implementation plan has no model for encrypted fields, pending users, or access-controlled media.
- `SPEC.md:193` says "All data stored on Tyler's infrastructure" while the plan uses Railway, Meta, and potentially OpenRouter/R2. That copy is false as written.

## Data Model Completeness — REVISE

The current model is not strong enough for real family data.

### What breaks immediately

- `relationships.relationship_type` only supports `parent_child`, `spouse`, `sibling`, and `ex_spouse` (`SPEC.md:107`, `docs/implementation-plan.md:142-149`). This is too thin for adoption, step-parents, donor/gestational parents, guardianship, foster relationships, separated-but-not-divorced couples, annulments, and unmarried co-parents.
- `sibling` should not be a stored primary relationship. It is usually derived from shared parent links. Storing it directly creates contradiction risk with full siblings, half-siblings, step-siblings, and adopted siblings.
- `parent_child` has no subtype. You cannot distinguish biological vs adoptive vs step vs foster vs legal guardian. That is a hard blocker for a genealogy app.
- Same-sex couples are only superficially supported. The schema allows two spouses, but the surrounding logic assumes maternal/paternal branches and gendered kinship labels (`SPEC.md:158`, `docs/implementation-plan.md:206`, `docs/implementation-plan.md:664-669`).
- Remarriage is underspecified. A person can have multiple `spouse` and `ex_spouse` edges over time, but there is no union/marriage entity to hang dates, status, notes, or children-of-that-union semantics off of.
- Unknown parents are not modeled. "Missing parent edge" is not the same as "parent unknown". Real genealogy often needs "unknown father", "possibly X", or "not yet proven".
- Dates are too strict. `birth_date` and `death_date` are ISO dates only (`docs/implementation-plan.md:110-111`). Genealogy data is full of partial and fuzzy dates: year-only, month/year, ranges, "circa", "before", "after".
- `location` is overloaded. Current residence, birth place, death place, and burial place are not the same thing.
- The model has no provenance. `manually_added` and `ImportedAsset.data` are not enough. You need to know where a relationship came from, whether it is trusted, what import created it, and what external IDs it maps to.
- The model has no merge story. You will get duplicates from manual entry, OAuth login, Facebook import, and eventual GEDCOM import. There is no durable identity mapping or merge audit trail.

### The worst design mistake

- The plan turns the child into a fake person called "Our Family" (`docs/implementation-plan.md:1233`, `docs/implementation-plan.md:1258-1263`). That corrupts the data model to solve a display problem. The root person should be a real person in the database, with a UI alias or viewer-specific redaction. Do not put fake genealogy into the primary graph.

### What I would change

Verdict: REVISE.

Recommended minimum schema changes before implementation:

1. Remove stored `sibling` as a canonical edge. Derive sibling/half-sibling/step-sibling from parent links.
2. Replace `parent_child` with a dedicated table that includes `relationship_kind`, `source`, `confidence`, `notes`, and optional `start_date`/`end_date`.
3. Replace `spouse`/`ex_spouse` with a partnership/union model:
   `partnership(id, status, start_date, end_date, source, notes)`
   and a join table for participants.
4. Add `account_status` on people or users: `pending`, `active`, `suspended`, `rejected`.
5. Add external identity mapping: Facebook ID, GEDCOM XREF, import source record IDs.
6. Add date precision support:
   raw text plus normalized partial fields, or a small structured date model.
7. Treat `branch` as presentation metadata only. Do not use it as truth.
8. Store provenance on relationships and imported facts from day 1.

If you want to stay lean, the minimal MVP can still avoid a full event model. But it cannot avoid relationship subtypes, provenance, and duplicates.

## GEDCOM Import — DEFER FOR MVP, REVISE FOR LATER

Right now GEDCOM is not just underspecified. It is absent.

That is a problem because GEDCOM is the real interoperability format for family trees. If this app is meant to become durable family infrastructure, GEDCOM matters more than Facebook.

### Why the current plan is unrealistic

- There is no GEDCOM section in either document. That means there is no mapping strategy, no loss budget, no import staging, and no re-import story.
- GEDCOM is not a clean `Person` plus `Relationship` import. It uses person records, family records, event records, notes, sources, media, custom tags, partial dates, and vendor-specific quirks.
- Real GEDCOM files contain ugly data:
  unknown dates, approximate dates, duplicate names, multiple names, notes with genealogical context, living/deceased privacy flags, and custom `_TAG` extensions.
- If you import GEDCOM directly into the live graph with the current schema, you will either discard important information or invent false certainty.

### The Facebook import assumptions are also too optimistic

- `SPEC.md:139` assumes Facebook export contains usable family relationship data in `about_you/family_members.json`. Maybe sometimes. Definitely not reliably enough to design around.
- `SPEC.md:133-140` assumes an emailed Facebook export link can be ingested automatically. That is brittle. These flows often expire, require re-authentication, or are inconsistent across accounts and export formats.
- `SPEC.md:127` frames `user_friends` as "perfect for family". It is not. At best it is a weak hint once multiple people already use the app.

### What a realistic GEDCOM plan looks like

Verdict: DEFER from Phase 1. REVISE before Phase 2.

Recommendations:

1. Do not promise GEDCOM import in the MVP.
2. When you add it, build an import pipeline with a staging area, not direct writes into production tables.
3. Preserve raw source data and original external IDs.
4. Make import idempotent per source file and source record.
5. Require human review for merges and ambiguous relationships.
6. Scope v1 GEDCOM import narrowly:
   names, parent links, partner links, birth/death facts, notes, and source IDs.
7. Treat everything else as optional future enrichment.

If you want an import earlier than GEDCOM, JSON seed import is fine. Facebook should be a profile-enrichment path, not the core truth source.

## Security Model / 5-Layer Permissions — CUT FOR PHASE 1

The graph-distance ACL is clever. It is also the wrong thing to build first.

### Why it is too complex

- `SPEC.md:21-38` defines a five-layer computed ACL plus life-event mutations. That is not simple authorization. That is a policy engine.
- The rules are socially brittle. "Divorce drops to Layer 5" (`SPEC.md:35`) is not a safe generalization in families with co-parenting, step-parents, or amicable exes.
- Graph distance is not trust. A beloved step-parent may be socially closer than a blood relative. A dangerous close relative may need less access than a distant cousin.
- The policy is hard to explain, hard to audit, and easy to get wrong during tree edits. One bad relationship edit can silently broaden access.
- The plan does not implement it in Phase 1 anyway (`docs/implementation-plan.md:7`), which means Phase 1 has the privacy marketing but not the privacy controls.

### The current Phase 1 auth story has a real security hole

- All core read endpoints are `Auth = User` (`docs/implementation-plan.md:413-415`, `docs/implementation-plan.md:524-525`).
- New Facebook users who do not match anyone are auto-created (`docs/implementation-plan.md:333`) and then redirected to `/tree` (`docs/implementation-plan.md:401`).
- There is no pending state, no approval queue, and no scoped visibility. That means a newly created account can likely read the whole family directory in Phase 1.

That is the opposite of the product's privacy pitch.

### Media access is also unresolved

- The spec promises private buckets and signed URLs (`SPEC.md:195`).
- The plan writes photos to `/data/photos` and returns `"/photos/{person_id}.jpg"` (`docs/implementation-plan.md:360-363`, `docs/implementation-plan.md:481-483`).
- There is no access-control design for media. If photos are statically served, auth is bypassed. If they are behind signed URLs, the D3 tree and long-lived sessions need a refresh strategy.

### Simpler Phase 1 alternative

Verdict: CUT the 5-layer engine from MVP. REVISE to a small, testable permission model.

Recommended Phase 1 model:

1. User roles:
   `admin`, `member`, `pending`
2. Person visibility:
   `visible`, `hidden`, `memorial`
3. Field visibility:
   `members`, `admins`, `hidden`
4. Invite-only onboarding:
   users must claim a pre-created record or be approved before seeing the tree
5. Access-controlled photo serving:
   serve media through authenticated endpoints, not open static paths

If you still want graph-derived privacy later, add it as a helper for default visibility suggestions, not as the primary ACL.

## Federation — CUT

This is premature by at least one major version.

### Why it should not be in the spec right now

- Federation multiplies every hard problem you already have:
  identity, trust, permissions, deduplication, deletion, conflict resolution, source of truth, and auditability.
- `SPEC.md:166-175` defines a protocol without defining keys, trust establishment, replay protection, revocation, schema versioning, or conflict ownership.
- Shared nodes across two databases (`SPEC.md:168`) are a consistency trap. Who owns edits? What happens on deletion? What happens when one side changes a name or relationship?
- Cross-instance permission layers (`SPEC.md:169`) are fantasy until the local permission system itself is proven.
- It adds engineering cost now while solving no immediate family problem.

### Better alternative

Verdict: CUT from the active roadmap.

If cross-family data exchange ever matters, start with manual export/import of a redacted bundle:

- `family-export.json`
- selected photos
- explicit approval by both admins
- no live sync

That gets you 80 percent of the value without inventing a protocol.

## Translation via OpenRouter — DEFER

This is a privacy and correctness footgun.

### Problems

- The spec contradicts itself on storage (`SPEC.md:287` vs `SPEC.md:299`).
- Runtime LLM translation of kinship terms is risky. Relationship language is not just UI copy. It is domain-specific and culturally specific.
- LLM output will be inconsistent over time unless you pin prompts, models, and review output.
- Sending family-derived labels, names, or bios to OpenRouter may leak PII to a third party. That directly conflicts with the privacy posture of the app.
- Writing generated locale JSON files at runtime is awkward on Railway. If it is not on a persistent volume, it disappears on deploy. If it is on a volume, you now have concurrent file-write concerns and config drift. "Git-committable" from a production runtime is not a real plan.

### Better alternative

Verdict: DEFER runtime translation.

Recommendations:

1. Support only `en`, `ru`, and `es` initially.
2. Keep UI strings in static checked-in catalogs.
3. Keep relationship labels as internal keys with manually curated translations.
4. If you use OpenRouter at all, use it offline as an admin assistive tool, never as the runtime source of truth.

The app needs stable kinship language, not clever translation.

## Tech Stack — SHIP IT WITH REVISIONS

FastAPI + SQLite is fine for this use case. The stack is not the main problem. The architecture around it needs tightening.

### What is fine

- FastAPI is a reasonable backend for auth, CRUD, and simple JSON endpoints.
- SQLite is fine for a private family app with one deployed instance and low write concurrency.
- D3 is a defensible choice for the tree visualization.

### What needs revision

- If HTMX is the intended stack, use HTMX for the CRUD and admin surfaces. Right now the plan is halfway to a custom mini-SPA (`docs/implementation-plan.md:565`, `docs/implementation-plan.md:712`).
- The best split here is:
  server-rendered pages and fragments with HTMX for forms, lists, edits, and approval flows
  plus one isolated D3 "tree island" for pan/zoom visualization
- Async SQLAlchemy + `aiosqlite` is acceptable, but probably unnecessary complexity for a tiny app. A sync SQLAlchemy setup would be simpler to reason about and test. This is not a blocker, just a simplification opportunity.
- `branch` inheritance and color coding are UI concerns. Keep them out of core relationship logic.
- Cloudflare Pages + Workers (`SPEC.md:72`) does not fit the FastAPI + SQLite plan. Drop that alternative unless you are willing to redesign around Workers/D1.

### One more blunt point

Facebook as the primary auth and bootstrap mechanism is a weak product decision in 2026.

- Some relatives will not use Facebook.
- Some will not want to authorize Meta.
- Development-mode tester management is operationally annoying.
- Email matching is unreliable because Facebook email is not guaranteed.

Use Facebook as optional profile import or identity linking. Do not make it the only door into the product.

## Deployment / Railway — REVISE

Railway is acceptable if the goal is speed. It is not the clean "self-hosted" story the spec claims.

### Railway verdict

Verdict: REVISE, not reject.

Railway is a reasonable MVP host if you accept:

- one region
- a mounted volume for SQLite
- a separate backup strategy
- no illusion that this is fully on "Tyler's infrastructure"

### Problems in the current plan

- The app depends on a persistent volume (`docs/implementation-plan.md:1140-1146`). That is okay, but backups are treated as Phase 2. They should be Day 1.
- Media is co-located with the DB on the same volume. That simplifies setup but increases blast radius.
- `ADMIN_FACEBOOK_IDS` as a required env var (`docs/implementation-plan.md:1124`) is awkward because you do not know those IDs until after login. Seed admins by email or by seed record claim token instead.
- Running migrations on startup is tolerable for an MVP, but it is not ideal operational hygiene.
- The Docker install step is suspicious:
  `uv pip install --system --no-cache -r pyproject.toml`
  is not how I would want dependency installation specified in a production plan.

### Better deployment recommendation

If speed matters most:

- Keep Railway for the app
- move photos to object storage earlier
- add automated encrypted backups from day 1
- document restore steps and test them

If "self-hosted" matters more than speed:

- use a small VPS
- run the app in Docker behind Caddy or Nginx
- store SQLite on local disk
- back up DB and media to remote object storage with restore drills

Either way, Cloudflare Pages + Workers is not the same architecture and should be removed from the stack options.

## What Is Missing For The First 2 Weeks — REVISE

These are the features a real family will ask for almost immediately.

### 1. Invite and approval flow

This is the biggest missing product feature.

You need:

- invite links or claim tokens
- pending users
- admin approval before directory access
- a way to link a login to a pre-created person

Without this, the auth model is weak and the manual data-entry story gets messy.

### 2. Duplicate merge tool

You will create duplicates almost immediately through:

- manual seed data
- Facebook login
- later imports

You need a merge UI and merge audit trail early.

### 3. Backup and export

If this is family infrastructure, "how do we not lose it?" comes before federation.

You need:

- one-click DB backup
- one-click media backup
- documented restore
- export format for leaving the app later

### 4. Non-Facebook access path

Manual entry for non-Facebook relatives is not enough. They also need a way to log in.

Add at least one of:

- magic-link email login
- invite-code login
- admin-created passwordless claim flow

### 5. Search and list view

A tree alone becomes awkward quickly. Families will want:

- search by name
- list by branch
- list by country
- list of recently added people

### 6. Notes / provenance

Families will ask:

- "Who added this?"
- "How do we know this date?"
- "Is this biological or adoptive?"

Even a light notes/provenance system beats pretending the graph is self-evident.

## Recommended Re-Scope — SHIP IT

If you want a credible MVP, this is the version I would actually build.

### Phase 1

- real person model with better parent/partner links
- admin CRUD
- manual tree seeding
- invite-only auth
- approval queue
- tree viewer
- person cards
- photo upload
- search/list view
- backups

### Phase 1.5

- duplicate merge UI
- access-controlled media serving
- simple per-field visibility
- audit log for edits

### Later

- Facebook profile linking
- Facebook photo import if still worth the friction
- GEDCOM import with staging/review
- curated i18n

### Much later, if ever

- graph-based ACL suggestions
- federation
- ActivityPub
- OpenRouter runtime translation

## Final Call

Verdict by topic:

- Data model: REVISE
- GEDCOM import: DEFER
- 5-layer permission system: CUT for Phase 1
- Federation: CUT
- OpenRouter translation: DEFER
- FastAPI + SQLite: SHIP IT
- Railway: REVISE
- MVP scope: RE-SCOPE HARD

If you cut the fantasy features and fix the model and onboarding flow, this becomes a strong small product.

If you do not, you will build a pretty demo with brittle data, weak privacy, and no safe path to growth.
