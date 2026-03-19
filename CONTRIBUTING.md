# Contributing to Family Book

Thanks for wanting to help! Family Book is a community project — every contribution matters, whether it's fixing a typo, adding a feature, or improving docs.

## Getting Started

### Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** — fast Python package manager (replaces pip/venv)
- **SQLite 3** — comes with most systems
- **Git**

### Setup

```bash
# Clone and enter the repo
git clone https://github.com/tymrtn/family-book.git
cd family-book

# Copy environment config
cp .env.example .env
# Edit .env — at minimum, set SECRET_KEY and FERNET_KEY:
#   SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
#   FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Install dependencies
uv sync

# Create the database
uv run alembic upgrade head

# (Optional) Load demo data — a fictional family tree for testing
uv run python -m app.seed

# Start the dev server
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open [http://localhost:8000](http://localhost:8000) and you're in.

Or just use the **Makefile** shortcuts:

```bash
make dev      # Start dev server with auto-reload
make test     # Run tests
make seed     # Load demo data
make migrate  # Run migrations
make build    # Build Docker image
```

## Running Tests

```bash
# All tests
uv run pytest

# With verbose output
uv run pytest -v

# A specific test file
uv run pytest tests/test_api.py

# A specific test
uv run pytest tests/test_api.py::test_create_person
```

Tests use an in-memory SQLite database and don't touch your dev data.

## Code Style

We don't have a strict linter config (yet), but please follow these conventions:

- **Follow existing patterns.** Look at how existing routes, models, and templates are structured. Do that.
- **Type hints everywhere** in Python code. FastAPI relies on them.
- **No SPA frameworks.** Jinja2 templates + HTMX for frontend. D3.js only for the tree. See `CLAUDE.md` for the rationale.
- **SQLAlchemy models** go in `app/models/`. Routes in `app/routes/`. Business logic in `app/services/`.
- **Every mutation gets an audit log entry.** If you add a new model that changes user data, add audit logging.
- **Source tracking.** Every new model that represents family data should have a `source` field.
- **Templates:** Keep them simple. Server-rendered HTML. Use HTMX attributes for interactivity.
- **Tests for every new feature.** If it touches the API, write a test. Look at `tests/` for examples.

### Architecture Rules (from CLAUDE.md)

These are non-negotiable:

1. **HTMX for everything except the tree.** D3.js is for tree visualization only.
2. **No React/Vue/Angular.** Vanilla JS + HTMX + D3.
3. **All media served through authenticated endpoints.** Never as static files.
4. **Root person redaction.** `is_root=true` person has name redacted in API responses.
5. **Source tracking** on every data model.
6. **Dedup by SHA-256 hash** for all media.
7. **Audit log** for all mutations.

## Submitting a Pull Request

1. **Fork the repo** and create a feature branch from `main`:
   ```bash
   git checkout -b feature/my-awesome-thing
   ```

2. **Make your changes.** Commit early and often. Write clear commit messages.

3. **Run the tests:**
   ```bash
   make test
   ```

4. **Push and open a PR** against `main`:
   ```bash
   git push origin feature/my-awesome-thing
   ```

5. **Describe what you did** in the PR. Include screenshots for UI changes.

6. **One feature per PR.** Small, focused PRs get reviewed faster.

### PR Checklist

- [ ] Tests pass (`uv run pytest`)
- [ ] New features have tests
- [ ] No SPA frameworks introduced
- [ ] Follows existing code patterns
- [ ] Audit logging added for new mutations
- [ ] Commit messages are clear

## Good First Issues

New to the project? Here are some great places to start:

- **🌍 Add a new locale** — Copy `locales/en.json`, translate it, add the language to the config. Every new language makes Family Book accessible to more families.
- **📝 Improve templates** — Better mobile responsiveness, accessibility improvements (ARIA labels, keyboard navigation).
- **🧪 Add more tests** — Edge cases in existing endpoints, UI smoke tests, import validation.
- **📖 Documentation** — Improve setup guides, add screenshots, write a deployment tutorial for a specific platform (DigitalOcean, Fly.io, etc.).
- **🎨 CSS improvements** — Better dark mode, print stylesheet for family trees, responsive tweaks.
- **🔍 Search improvements** — Better fuzzy matching for names, search by relationship, search within date ranges.

Look at [open issues](https://github.com/tymrtn/family-book/issues) for more ideas, or open a new issue to discuss a feature before building it.

## Questions?

Open an issue or start a discussion. We're friendly. 🌙
