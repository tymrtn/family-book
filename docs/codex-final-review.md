# Codex Final Gap Review

Main finding: the spec is strong on product intent and user experience, but several core areas still lack the persisted state, API surface, and integration contracts needed for deterministic implementation. The biggest gaps are auth/onboarding, media ingestion, notifications, Matrix, memorial mode, and build/deploy artifacts.

## MUST FIX

1. Auth onboarding has no persisted model
Section: `Authentication & Authorization > Account States`, `API Surface > Auth Endpoints`, `Invite Endpoints`, `Admin Endpoints`
What's missing: There is no `Invite` entity, no magic-link token entity, and no persisted `account_state` or approval/suspension field on `Person`. The spec promises single-use invites, active invite lookup/revoke, pending approval, suspend/approve endpoints, and a pending-only status view, but the data model only has `UserSession`.
Verdict: MUST FIX

2. Root-person redaction has no API contract
Section: `Core Concepts > Root Person`, `API Surface > Person Endpoints`, `Tree Endpoint`
What's missing: The spec says the root person's real name is never exposed in templates, API responses, or client code, but `PersonSummary` and `TreeData.persons` still expose `first_name` and `last_name`. The API needs explicit redacted fields or an explicit display-name rule so the build agent does not guess where redaction happens.
Verdict: MUST FIX

3. The media model cannot represent the content the product promises
Section: `Data Model > Photo`, `Data Model > Moment`, `Moments Feed`, `WhatsApp Group Export Ingestion`, `Facebook Messenger Group Chat`, `docs/vision-draft.md > TikTok`, `docs/vision-draft.md > Instagram`
What's missing: There is no general media entity for video, audio, stickers/GIFs, or external embeds. `Photo` only stores images, `Moment.kind` lacks `audio` and any embed/link shape, and the `source` enums do not cover email, share sheet, Matrix, Telegram, Messenger, or direct embed imports.
Verdict: MUST FIX

4. The WhatsApp bootstrap importer has no implementable persistence/API layer
Section: `WhatsApp Group Export Ingestion`, `Pages`, `API Surface`, `Phase Plan > Bootstrap`
What's missing: The parser references `WhatsappImportBatch.date_format`, admin review state, pause/resume, preview, duplicate review, sender mappings, and batch progress, but none of those tables or endpoints exist. There is no API for upload, preview, save mappings, continue/cancel import, or resume a paused batch. New Person records can be created from WhatsApp contacts, but `Person.source` also has no `whatsapp_import` value.
Verdict: MUST FIX

5. Memorial mode is missing its actual API and storage contract
Section: `Memorial Mode`, `Pages`, `API Surface`, `Family Governance`
What's missing: The spec describes pre-planning, mark-as-deceased, memorial activation, tributes, annual remembrance, and a distinct memorial page, but there is no `MemorialPlan` or equivalent model, no memorial route, no endpoints for pre-plan CRUD, no endpoint allowing immediate family to mark someone deceased, and no tribute create/hide/list API. `Tribute` is defined later but not integrated into the main data model or API surface.
Verdict: MUST FIX

6. The notification router is only routing tables, not a build contract
Section: `Grandparent Experience > Push Channels`, `Two-Way Reactions via Push`, `Push Notification Preferences`, `Phase Plan > Notifications`
What's missing: There is no `Notification`, `NotificationDelivery`, or `NotificationPreference` schema; no outbound routing API/worker contract; no digest schema; no retry/failure model; and no inbound callback/webhook contracts for SMS replies, Telegram button callbacks, email reaction links, or Signal/OpenClaw events.
Verdict: MUST FIX

7. Matrix integration is still conceptual
Section: `Matrix as Universal Bridge Layer`, `Facebook Groups & Messenger Integration`, `Ingestion Architecture`
What's missing: The spec does not define the Matrix event types Family Book consumes, room-to-family mapping, Matrix user-to-Person mapping, idempotency keys, media download flow, outbound message format, reaction mapping, bridge provisioning rules, or admin setup contract. It explains why Matrix is attractive, but not how the app actually talks to it.
Verdict: MUST FIX

8. Envelope inbound ingestion is promised but not specified
Section: `Ingestion Architecture`, `Facebook Data Export Ingestion`, `docs/vision-draft.md > Email (Envelope)`
What's missing: There is no inbound webhook/API contract for Envelope, no payload schema, no signature/authentication model, no download/extraction flow for forwarded export emails, and no failure/admin review path when sender matching or attachment parsing fails.
Verdict: MUST FIX

9. PWA share sheet integration is promised but unspecced
Section: `Ingestion Architecture > Share sheet (PWA)`, `docs/vision-draft.md > What Changes In The Spec`
What's missing: There is no web app manifest contract, no `share_target` definition, no receiving endpoint, no auth/session expectation for shared content, no supported media matrix, and no fallback behavior when the user is not logged in.
Verdict: MUST FIX

10. Several feature-list endpoints are missing from the API surface
Section: `Phase Plan`, `GEDCOM Import`, `Duplicate Detection & Merge`, `Moments Feed`, `Person Card Component`, `Family Graph API`
What's missing: The API surface does not include GEDCOM upload/review/accept/reject/merge endpoints, WhatsApp import endpoints, duplicate merge/unmerge endpoints, a person-card fragment endpoint for `/people/{id}/card`, an SSE endpoint for live Moments, memorial endpoints, or API key management endpoints for the agent API.
Verdict: MUST FIX

11. Facebook Groups/Messenger import is not detailed enough to implement safely
Section: `Facebook Groups & Messenger Integration`
What's missing: The Facebook Group path has no export file layout, parser rules, or review flow at all. Messenger has one sample JSON object, but no full attachment schema, no staged review contract, no mapping for comments vs Moments, and no details for multi-file exports, deleted content, or mixed attachment sets. Compared with the WhatsApp section, this is still high-level.
Verdict: MUST FIX

12. The env var table is missing required config for promised integrations
Section: `Deployment > Environment Variables`, plus `Grandparent Experience`, `Matrix as Universal Bridge Layer`, `OpenRouter`, `WhatsApp Profile Sync`
What's missing: The table does not include vars for Twilio, WhatsApp Business, Telegram bot, Signal/OpenClaw, Matrix/Conduit/bridges, inbound Envelope auth, `wacli`, or the offline OpenRouter locale script. At minimum the spec needs canonical names for those configs so the build agent does not invent them.
Verdict: MUST FIX

13. `CLAUDE.md` is referenced as required but does not exist
Section: `Phase Plan > Foundation`, `Backup Strategy`
What's missing: The file itself. It should at least contain local bootstrap commands, migration/seed commands, Railway deploy steps, backup/restore runbook, the tested restore date, env var source-of-truth, smoke-test commands, and the Matrix/bridge bring-up notes once Compose exists.
Verdict: MUST FIX

14. Docker Compose is referenced but not written
Section: `Matrix as Universal Bridge Layer > Self-hosting requirements`
What's missing: The actual `docker-compose.yml` or equivalent for Family Book + Conduit + bridges, plus service names, volumes, health checks, dependency order, and env references. Right now the build agent would have to invent the whole topology.
Verdict: MUST FIX

15. Cross-doc strategy and phasing for WhatsApp are inconsistent
Section: `SPEC.md > Matrix as Universal Bridge Layer`, `SPEC.md > Grandparent Experience`, `SPEC.md > WhatsApp Group Export Ingestion`, `docs/vision-draft.md > WhatsApp`, `docs/vision-draft.md > Phasing`
What's missing: One authoritative answer to "what is WhatsApp in this product?" The vision draft says manual bridge, no bot/API automation, and Phase 3 historical import. The spec says WhatsApp export is the primary bootstrap now, real-time bridge is under Matrix, and outbound notifications may go through WhatsApp Business. Build order and integration surface change depending on which doc wins.
Verdict: MUST FIX

16. Family-governance approval rules do not connect to executable flows
Section: `Family Governance`, `Moments API Endpoints`, `Memorial Mode`, `Graph-Distance Privacy`
What's missing: There is no approval/vote entity, no workflow API, and no resolution of direct contradictions such as "both parents must approve a minor's photos" vs `POST /api/moments` by a member, or "memorial creation = majority of immediate family" vs "admin or any immediate family member marks the person as deceased".
Verdict: MUST FIX

17. Upload validation contradicts the media features
Section: `Security > Input Validation`, `Moments Feed`, `WhatsApp Group Export Ingestion`, `Facebook Messenger Group Chat`
What's missing: The accepted upload/storage MIME set for video, audio, and other media. The security section only allows image uploads, but the product promises direct video upload, WhatsApp video import, audio Moments, stickers, GIFs, and inline playback.
Verdict: MUST FIX

## SHOULD FIX

18. Later role/privacy/preference state is introduced but not modeled
Section: `Roles`, `Graph-Distance Privacy > Admin Overrides`, `Grandparent Roles`, `Push Notification Preferences`, `Adaptive Home Screen`
What's missing: There is no place to store `branch_admin`, `privacy_layer_override`, push preference fields, `visit_count`, or any explicit `last_activity` rule beyond raw session usage. Some of this could be derived, but the spec never says what is persisted vs computed.
Verdict: SHOULD FIX

19. Agent API auth is missing its own data model and admin management flow
Section: `Family Graph API`, `API Key Scoping`, `AuditLog`
What's missing: There is no `ApiKey` or `AgentClient` entity, no issuance/revocation endpoints, no key-rotation policy, and the audit log schema does not currently cover API key lifecycle events even though the section says they are audit-logged.
Verdict: SHOULD FIX

20. Health and startup contracts disagree across sections
Section: `API Surface > Health Endpoint`, `Deployment > Build & Start`, `Deployment > Health Check`
What's missing: One canonical health response and one canonical startup contract. The health endpoint returns different payloads in two places, and the startup sequence requires migrations/seed loading while the provided Dockerfile snippet only shows app startup.
Verdict: SHOULD FIX

21. Seed-data guidance conflicts with the bootstrap story
Section: `WhatsApp Group Export Ingestion`, `Seed Data`, `Phase Plan > Bootstrap`
What's missing: A clear statement of whether JSON seed data is required, optional bootstrap, or only a fallback/manual supplement. Today the spec says "not manual JSON seed files" and also makes `data/family_tree.json` part of bootstrap/startup.
Verdict: SHOULD FIX

22. Pages/routes are incomplete for features already described in UI text
Section: `Pages`, `Person Card Component`, `Search & List Views`, `Memorial in the Tree`
What's missing: The Pages table omits `/admin/import/gedcom`, `/birthdays`, `/map`, the person-card fragment route, and any memorial page route even though those flows are described elsewhere.
Verdict: SHOULD FIX

23. TikTok/Instagram embed support is promised without storage/render details
Section: `docs/vision-draft.md > TikTok`, `docs/vision-draft.md > Instagram`, `Phase Plan > Data Liberation`
What's missing: There is no field or entity for external URLs/oEmbed metadata, no render contract for embeds in `MomentCard`, and no import path for link-only Moments.
Verdict: SHOULD FIX

## NICE TO HAVE

24. The vision diagram introduces Google OAuth but the spec never acknowledges it
Section: `docs/vision-draft.md > Platform Integration Architecture`
What's missing: Either a short spec section for Google OAuth or an explicit note that the diagram is illustrative and Google is out of scope. Right now it is a dangling identity provider in the architecture picture.
Verdict: NICE TO HAVE
