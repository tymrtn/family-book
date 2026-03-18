# 📖 Family Book

A private, self-hosted family tree and archive. Built for families who want to own their memories.

## What It Is

Family Book is a web app for preserving your family's story — people, relationships, photos, moments, and memories — in a place you control. No cloud services. No subscriptions. No data mining. Your family's history belongs to your family.

## Features

- **Family Tree** — Interactive D3.js visualization with branches, partnerships, and multi-generational navigation
- **Person Profiles** — Birth dates, locations, languages, patronymics, maiden names, and custom fields
- **Media Gallery** — Photo and document uploads with SHA-256 dedup and authenticated serving
- **Moments** — A family timeline of events, milestones, and stories with comments and emoji reactions
- **Privacy by Design** — Graph-distance privacy: the family tree structure IS the permission system
- **Multi-Language** — English, Spanish, Russian (extensible via JSON locale files)
- **PWA** — Install on your phone as a native-feeling app
- **Backup** — Automated daily SQLite backups with restore verification
- **Self-Hosted** — Deploy to Railway, Docker, or any server. You own the data.

## Tech Stack

- **Backend:** Python 3.12 + FastAPI + SQLAlchemy + Alembic
- **Frontend:** Jinja2 templates + HTMX + D3.js (tree only)
- **Database:** SQLite (WAL mode) on persistent volume
- **Auth:** Magic link (passwordless) via email
- **Media:** Stored locally, served through authenticated endpoints
- **Deploy:** Docker + Railway (one-click) or any container host

## Quick Start

```bash
# Clone
git clone https://github.com/tymrtn/family-book.git
cd family-book

# Setup
cp .env.example .env  # Edit with your values
uv sync
uv run alembic upgrade head
uv run python -m app.seed  # Optional: load demo family

# Run
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open [localhost:8000](http://localhost:8000)

## Deploy to Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/template)

```bash
railway up
```

Railway runs the Dockerfile. Persistent volume at `/data`. Health check at `/health`.

## Architecture

```
app/
  main.py          # FastAPI app
  models/          # SQLAlchemy models (Person, Partnership, ParentChild, Media, Moment)
  routes/          # API + page routes
  services/        # Business logic
  templates/       # Jinja2 + HTMX templates
  static/          # CSS, JS, D3 tree
  importers/       # WhatsApp, Messenger, GEDCOM parsers (planned)
  matrix/          # Matrix bridge integration (planned)
data/              # SQLite + media + backups (persistent volume)
locales/           # i18n JSON files (en, es, ru)
```

## Design Principles

1. **HTMX for everything except the tree.** D3.js is used ONLY for tree visualization. No SPA frameworks.
2. **Privacy is structural.** Graph distance in the family tree determines what you can see. No access control lists — the tree IS the permission system.
3. **Source tracking.** Every fact has a source: manual entry, GEDCOM import, WhatsApp message, photo EXIF.
4. **Never destroy originals.** Media dedup by SHA-256 hash. Originals preserved.
5. **Self-hosted first.** No external service dependencies for core functionality.

## Roadmap

- [x] Core models + API (Phase 1)
- [x] Media, Moments, Comments, Reactions (Phase 2A)
- [x] HTMX frontend — tree, profiles, gallery, moments (Phase 2B)
- [x] Docker, backup, i18n, PWA (Phase 3)
- [ ] WhatsApp import via Matrix bridge
- [ ] GEDCOM import/export
- [ ] Facebook/Messenger photo import
- [ ] Notifications (push, email, Matrix)
- [ ] Advanced search and timeline filtering

## License

MIT

## Author

Built with love for Luna. 🌙
