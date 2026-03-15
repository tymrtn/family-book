# CLAUDE.md — Family Book Build Guide

## What This Is
Family Book is a private, self-hosted family tree and archive with sovereign data ownership. Read SPEC.md (the complete 2000+ line specification) before touching any code.

## Tech Stack
- **Backend:** Python 3.12 + FastAPI + SQLAlchemy + Alembic
- **Database:** SQLite (WAL mode) on persistent volume at `/data/family.db`
- **Frontend:** Jinja2 templates + HTMX + D3.js (tree visualization only)
- **Auth:** Session cookies (HttpOnly, Secure, SameSite=Lax)
- **Media:** Stored at `/data/media/`, served through authenticated endpoint

## Local Development
```bash
# Setup
cp .env.example .env  # Edit with your values
uv sync
uv run alembic upgrade head
uv run python -m app.seed  # Optional: load seed data

# Run
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Test
uv run pytest
```

## Database Migrations
```bash
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
uv run alembic downgrade -1  # Rollback
```

## Deploy (Railway)
```bash
railway up
```
Railway runs the Dockerfile. Persistent volume at `/data`. Health check at `/health`.

## Backup / Restore
```bash
# Backup (also runs daily via cron)
sqlite3 /data/family.db ".backup /data/backups/family-$(date +%Y%m%d).db"
gzip /data/backups/family-*.db

# Restore
cp backup.db /data/family.db
uv run alembic upgrade head
```
**Restore procedure MUST be tested before go-live. Record test date here: _____**

## Key Architecture Rules
1. **HTMX for everything except the tree.** D3.js is used ONLY for the tree visualization. Everything else is server-rendered HTML + HTMX.
2. **No SPA frameworks.** No React, Vue, or Angular. Vanilla JS + HTMX + D3.
3. **All media served through authenticated endpoints.** Never serve media as static files. Always check session auth.
4. **Root person redaction.** The Person with `is_root=true` has their name redacted in ALL API responses and templates. Use `display_name` (computed server-side), never raw `first_name`/`last_name`.
5. **Source tracking.** Every Person, ParentChild, Partnership, Media, and Moment has a `source` field. Always set it correctly.
6. **Dedup by hash.** All media imports must check SHA-256 file hash before creating records.
7. **Audit everything.** All mutations to Person, ParentChild, Partnership create AuditLog entries.

## Environment Variables
See SPEC.md § Deployment > Environment Variables for the complete list.

## Matrix / Bridges
See docker-compose.yml for the Conduit + Mautrix bridge topology. Bridge setup:
1. Start Conduit
2. Register bridge bot users
3. Authenticate each bridge with its platform (WhatsApp QR, Telegram auth, etc.)
4. Start Family Book — it joins the family room and listens for events

## Project Structure (expected)
```
app/
  main.py          # FastAPI app + startup
  models/          # SQLAlchemy models
  routes/          # API + page routes
  services/        # Business logic
  templates/       # Jinja2 templates
  static/          # CSS, JS, D3
  importers/       # WhatsApp, Messenger, GEDCOM parsers
  notifications/   # Push router + channel adapters
  matrix/          # Matrix client integration
alembic/           # Migrations
data/              # SQLite + media + backups (persistent volume)
locales/           # i18n JSON files
scripts/           # Admin CLI scripts
docker-compose.yml # Family Book + Conduit + bridges
Dockerfile
SPEC.md            # THE spec. Read it.
CLAUDE.md          # This file.
```
