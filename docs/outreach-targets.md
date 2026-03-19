# Family Book — Outreach Targets

> **Prepared:** 2026-03-19
> **Status:** DRAFT — For Tyler to review and post manually
> **Rule:** Be genuinely useful. No spam. Only comment where Family Book adds real value to the conversation.

---

## 1. awesome-selfhosted/awesome-selfhosted

- **URL:** https://github.com/awesome-selfhosted/awesome-selfhosted
- **Stars:** 280,920
- **Section:** Genealogy (currently lists: Genea.app, Genealogy by MGeurts, GeneWeb, Gramps Web, webtrees)
- **Action:** Submit a PR to add Family Book to the Genealogy section
- **Why it fits:** Family Book is MIT-licensed, self-hosted, and fills a gap — none of the listed tools import from WhatsApp/iMessage or focus on modern chat-based family archiving.

**Suggested PR description:**
```
Add Family Book to Genealogy section

Family Book is a self-hosted family tree and archive built with FastAPI, HTMX, and SQLite.
It focuses on privacy-first family history with planned WhatsApp/iMessage import,
multi-language support (en/es/ru), and a simple SQLite-based data model.

- Website: https://github.com/tymrtn/family-book
- License: MIT
- Stack: Python/FastAPI + HTMX + SQLite
```

---

## 2. rajasegar/awesome-htmx

- **URL:** https://github.com/rajasegar/awesome-htmx
- **Stars:** 2,273
- **Action:** Submit a PR to add Family Book under the "Apps" or "Real-World Examples" section
- **Why it fits:** Family Book is a real-world, production-grade HTMX + FastAPI app — exactly what this list's audience is looking for.

**Suggested PR description:**
```
Add Family Book to real-world apps

Family Book is a self-hosted family tree app built with FastAPI + HTMX + D3.js.
Uses HTMX for interactive family tree navigation, media uploads, timeline/moments,
and real-time search. A non-trivial example of HTMX in a full-stack Python app.

https://github.com/tymrtn/family-book
```

---

## 3. PyHAT-stack/awesome-python-htmx

- **URL:** https://github.com/PyHAT-stack/awesome-python-htmx
- **Stars:** 1,308
- **Action:** Submit a PR to add Family Book as a real-world project
- **Why it fits:** Family Book is specifically Python (FastAPI) + HTMX — the exact stack this list curates.

**Suggested PR description:**
```
Add Family Book — FastAPI + HTMX family tree app

Family Book is a privacy-first, self-hosted family tree and archive.
Built with FastAPI + HTMX + Jinja2 + D3.js + SQLite.
Features interactive tree visualization, media gallery with SHA-256 dedup,
a family timeline with comments/reactions, and multi-language support.

https://github.com/tymrtn/family-book
```

---

## 4. gramps-project/gramps-web (Discussions)

- **URL:** https://github.com/gramps-project/gramps-web/discussions
- **Stars:** 1,305
- **Action:** Comment in a relevant discussion (or create a new one) about alternative approaches to self-hosted genealogy
- **Why it fits:** Gramps Web users are actively looking for self-hosted genealogy tools. Family Book takes a different approach (modern stack, chat import, no GEDCOM dependency) that may interest users whose needs don't align with Gramps' desktop-first model.

**Suggested comment (for a relevant discussion about alternatives or modern features):**
```
Interesting discussion! I've been building a different take on self-hosted genealogy
called Family Book (https://github.com/tymrtn/family-book). It's FastAPI + HTMX + SQLite,
focused on being dead-simple to deploy (one Docker container, SQLite file = your entire database).

The angle is a bit different from Gramps — less about GEDCOM interop and more about
capturing family stories from modern sources (WhatsApp chats, iMessage exports, voice notes).
Still early but MIT-licensed and actively developed. Would love feedback from folks
who've thought deeply about this space.
```

---

## 5. fisharebest/webtrees (Issues/Discussions)

- **URL:** https://github.com/fisharebest/webtrees
- **Stars:** 729
- **Action:** Look for open issues about "modern UI", "mobile-friendly", or "media management" and comment with Family Book as a complementary tool
- **Why it fits:** webtrees is PHP-based and GEDCOM-centric. Users frustrated with its UI or wanting a simpler deployment may find Family Book appealing as an alternative or complement.

**Suggested comment (on a relevant issue about modern UI/UX):**
```
I ran into similar frustrations and ended up building Family Book
(https://github.com/tymrtn/family-book) — a self-hosted family tree app
with a more modern stack (FastAPI + HTMX + D3.js, single SQLite file).
Different philosophy from webtrees (no GEDCOM, focused on simplicity and chat imports),
but might be interesting to folks looking for a lighter-weight alternative.
Not trying to replace webtrees — just a different approach to the same problem!
```

---

## 6. ReagentX/imessage-exporter

- **URL:** https://github.com/ReagentX/imessage-exporter
- **Stars:** 4,980
- **Action:** Open an issue or comment about "what do people do with their exported messages?" with Family Book as a downstream consumer
- **Why it fits:** imessage-exporter users export their messages but then... what? Family Book's planned iMessage import feature would be a natural next step.

**Suggested comment/issue:**
```
Title: Showcase: Using exported iMessages as family archive input

Love this tool! I'm building a self-hosted family tree app called Family Book
(https://github.com/tymrtn/family-book) and planning to support importing
iMessage exports as "Moments" in a family timeline. The idea is that those
exported conversations with grandparents, family group chats, etc. become
part of a searchable, private family archive.

Would be curious if other users have found interesting downstream uses
for their exported data. Happy to share more about the integration
when it's ready.
```

---

## 7. KnugiHK/WhatsApp-Chat-Exporter

- **URL:** https://github.com/KnugiHK/WhatsApp-Chat-Exporter
- **Stars:** 987
- **Action:** Similar to imessage-exporter — comment about downstream use case for exported WhatsApp data
- **Why it fits:** Same logic. People export WhatsApp chats for preservation. Family Book would be where those exports live permanently.

**Suggested comment:**
```
Great tool! I'm working on a self-hosted family tree app called Family Book
(https://github.com/tymrtn/family-book) that will support importing WhatsApp
exports as family "Moments" — the idea being that group chats with family
are a goldmine of stories, photos, and memories that deserve better than
sitting in a backup file.

Planning to support the HTML/JSON output format from this tool as an import source.
Would love to know if there are any gotchas with the export format I should be aware of.
```

---

## 8. r/selfhosted (Reddit)

- **URL:** https://www.reddit.com/r/selfhosted/
- **Relevant threads:**
  - https://www.reddit.com/r/selfhosted/comments/xihl3y/ ("Is there an open source self hostable multi user family tree project?")
  - https://www.reddit.com/r/selfhosted/comments/113wvss/ ("Open source family tree maker?")
  - https://www.reddit.com/r/selfhosted/comments/10gmi3f/ ("Self hosted Family Tree software?")
- **Action:** Post a "Show /r/selfhosted" or comment on a relevant thread
- **Why it fits:** This is THE community for self-hosted software discovery. Multiple threads asking for exactly what Family Book is.

**Suggested post:**
```
Title: I built a self-hosted family tree app — Family Book (FastAPI + HTMX + SQLite)

Hey r/selfhosted! I've been building Family Book, a privacy-first family tree
and archive app. Single Docker container, SQLite database (your whole family tree
is one file you can back up), and no external dependencies.

What makes it different from webtrees/Gramps:
- Modern stack: FastAPI + HTMX + D3.js (no PHP, no Java)
- Planned WhatsApp/iMessage import (turn family chats into a searchable archive)
- Multi-language (en/es/ru)
- "Moments" timeline for family events with comments and reactions
- Media gallery with automatic dedup

MIT licensed, actively developed. Would love feedback!

https://github.com/tymrtn/family-book
```

---

## 9. geneanet/geneweb

- **URL:** https://github.com/geneanet/geneweb
- **Stars:** 371
- **Action:** Look for discussions about modernization, web UI, or alternative approaches
- **Why it fits:** GeneWeb is mature but OCaml-based, which limits contributor pool. Family Book's Python stack may attract users who want something more hackable.

**Suggested comment (on relevant issue about modernization):**
```
Interesting project! I've been exploring a similar space with Family Book
(https://github.com/tymrtn/family-book) — taking a more modern approach
with FastAPI + HTMX + SQLite. Different trade-offs (no GEDCOM, less mature,
but much simpler to deploy and extend). Would be curious about your thoughts
on the genealogy software landscape — feels like there's room for multiple
approaches.
```

---

## 10. Hacker News (Show HN)

- **URL:** https://news.ycombinator.com/
- **Action:** Submit a "Show HN" post when the WhatsApp/iMessage import feature lands
- **Why it fits:** HN loves self-hosted tools, privacy-first software, and interesting tech stacks. The "turn your WhatsApp family chats into a permanent archive" angle is compelling.

**Suggested post (save for when chat import ships):**
```
Title: Show HN: Family Book – Self-hosted family tree that imports WhatsApp/iMessage chats

Body: I built Family Book because my family's history was scattered across
WhatsApp groups, iMessage threads, and photo albums nobody organized.

It's a self-hosted family tree + archive: FastAPI + HTMX + SQLite.
Deploy with Docker, import your data, own it forever.

The key insight: modern family history isn't just names and dates — it's
the group chat where grandma told the story about the war. The voice note
your dad sent on his birthday. Family Book treats these as first-class
"Moments" alongside the traditional genealogy data.

MIT licensed. Single SQLite file = your whole family.

https://github.com/tymrtn/family-book
```

---

## Priority Order

1. **awesome-selfhosted PR** — highest visibility, 280K stars, easy PR
2. **awesome-htmx PR** — great for developer discovery
3. **awesome-python-htmx PR** — same, Python-specific
4. **r/selfhosted post** — direct audience, high engagement
5. **imessage-exporter comment** — 5K stars, natural fit
6. **WhatsApp-Chat-Exporter comment** — natural downstream use case
7. **Gramps Web discussion** — engaged genealogy community
8. **Show HN** — save for when chat import feature ships
9. **webtrees comment** — be careful with tone, established community
10. **GeneWeb comment** — smaller but relevant audience

---

## Notes

- **Timing:** PRs to awesome lists can be submitted now. Reddit/HN posts work best when there's a demo or compelling screenshot to share.
- **Screenshots:** Prepare 2-3 polished screenshots (tree view, moments timeline, media gallery) before posting to Reddit/HN.
- **Don't rush HN:** Wait until WhatsApp/iMessage import actually works. The story is 10x better with "import your family WhatsApp group" as a real feature.
- **Be genuine:** Every comment should add value to the conversation it's in. If it feels like an ad, rewrite it.
