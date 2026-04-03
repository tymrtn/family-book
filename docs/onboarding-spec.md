# Onboarding Flow — From Demo to Living Family Book

## The Problem

Right now a fresh deploy seeds 26 demo persons, 16 moments, 40 reactions, and 15 comments.
There is no way to remove this demo data, no "claim this site" flow, and no guided path
from anonymous visitor to functioning family admin.

## The Journey (5 steps)

### Step 1: Landing — Anonymous Visitor

**URL:** `/` (not logged in)

What they see:
- Site title + tagline ("Our living room, not the mall")
- "Explore the demo family" link → `/demo` (existing, read-only)
- "Claim this site" button (only visible if site is UNCLAIMED)
- "Log in" link (only visible if site IS claimed)

**Key concept: CLAIMED vs UNCLAIMED state.**

A new deploy starts UNCLAIMED. The site has demo data and no real admin.
Once someone claims it, the site becomes CLAIMED and the "Claim" button disappears forever.

Store this as `site_state` in a `site_config` table or a simple JSON file at `/data/site.json`:
```json
{
  "state": "unclaimed",    // unclaimed | claimed
  "claimed_at": null,
  "claimed_by": null,
  "site_title": "Volodin Family Book",
  "accent": "forest"
}
```

### Step 2: Claim — "This is MY family book now"

**URL:** `/claim` (only accessible when state=unclaimed)

A simple form:
- Your name (first + last)
- Your email (becomes admin email, used for magic link login)
- Family name (becomes site title, e.g. "Volodin Family Book")
- Password (optional, for immediate login without waiting for magic link)

On submit:
1. Create a Person record for the claimer (`is_admin=true`)
2. Create a session (log them in immediately)
3. Set `site_state = "claimed"`
4. Redirect to `/setup` (Step 3)

**Security:** Once claimed, `/claim` returns 404. No race condition — use DB transaction.

### Step 3: Setup Wizard — "Build your family"

**URL:** `/setup` (only accessible to admin, only shown once, skippable)

A multi-step wizard (single page with HTMX step transitions, NOT a SPA):

**Step 3a: Clean house**
"Your Family Book came with a demo family. Ready to start fresh?"

Two buttons:
- **"Remove demo data"** → deletes all seed data (persons, relationships, moments, reactions, comments where `source='seed'` or matching seed IDs). Keeps the admin's own record.
- **"Keep demo data"** → leaves it (maybe they want to explore first). Can always remove later from admin panel.

Implementation: All seed data has deterministic IDs (from `family_tree.json`). The cleanup query deletes all records whose IDs appear in the seed file. This is safe because real user data will have random UUIDs.

**Step 3b: Set up your tree root**
"Who is the center of this family tree?"

- This is usually a child (the person the tree is "for") or a couple
- Pick: "Myself" / "My child" / "My partner and I"
- If child: enter child's name + birth year → creates Person with `is_root=true`
- The root person's name is redacted in the UI (shows as "Our Family")

**Step 3c: Add your first family members**
Quick-add form (repeatable):
- Name (first + last)
- Relationship to you (parent / child / sibling / partner)
- Email (optional — needed for invite links)
- Branch (optional — e.g. "martin", "volodin")

Each "Add" creates a Person record + the appropriate ParentChild/Partnership edge.
Show a mini tree visualization updating in real-time as they add people.

"Add more later" button to skip ahead.

**Step 3d: Invite your family**
For each person with an email, show:
- Name + relationship
- "Send invite" button → generates invite link, sends via Envelope magic link email
- Copy link button (for sharing via WhatsApp/Telegram manually)

"Do this later" button.

**Step 3e: Done!**
"Your Family Book is ready. Welcome home."
→ Redirect to `/` (now shows the real family feed, or empty state if no moments yet)

### Step 4: Living with the site — Admin Panel additions

**`/admin` needs a new section: "Demo Data"**

If any seed data remains in the database:
- Show count: "26 demo persons, 16 demo moments still in your database"
- "Remove all demo data" button (same action as Step 3a)
- This section disappears once no seed data remains

**`/admin` needs: "Invite Management" improvements**

Current: can create invites. Needs:
- Pending invites list with status (sent / claimed / expired)
- Re-send button for unclaimed invites
- Bulk invite: paste a list of emails, auto-create Person records + send invites
- Copy shareable invite link for each person

### Step 5: The New Member Experience

When a family member clicks their invite link:

**URL:** `/invite/{token}`

Current flow (keep, but enhance):
1. See welcome page: "Welcome, [Name]! [Admin] invited you to the [Family] Family Book."
2. Show their relationship: "You're listed as [Admin's mother]"
3. "Join" button → claims invite, creates session, logs in
4. Redirect to guided first visit:

**First visit for new members** (`/welcome` or just smart `/` behavior):
- Brief tour overlay (3-4 steps, dismissable):
  1. "This is your family tree" → highlights tree nav
  2. "Here's your profile" → link to edit their own bio/photo
  3. "Share photos" → shows the + button / share sheet
  4. "That's it! Explore your family."
- After tour: land on home feed

**Profile completion nudge:**
- On their first 3 visits, show a gentle banner: "Add a profile photo" / "Write a short bio"
- Not blocking, not annoying, just present

## Technical Implementation

### Database changes

Add to `site_config` table (or use existing `site_settings`):
```sql
ALTER TABLE site_settings ADD COLUMN site_state TEXT NOT NULL DEFAULT 'unclaimed';
ALTER TABLE site_settings ADD COLUMN claimed_at TEXT;
ALTER TABLE site_settings ADD COLUMN claimed_by TEXT; -- FK to persons.id
```

### Seed data identification

Option A (preferred): Tag all seed data with `source='seed'` during seeding.
- Already partially there: seed.py could set `source='seed'` on all records
- Moments already have a source field
- Persons have a source field
- Relationships have a source field

Option B: Use the deterministic IDs from family_tree.json at cleanup time.
- Read the JSON, collect all IDs, DELETE WHERE id IN (...)
- Works but fragile if someone manually edits a seed record

**Use both:** Tag with source='seed' AND use ID matching as a safety net.

### New routes

| Route | Method | Auth | Purpose |
|-------|--------|------|---------|
| `/claim` | GET | none | Show claim form (404 if claimed) |
| `/claim` | POST | none | Process claim (404 if claimed) |
| `/setup` | GET | admin | Setup wizard |
| `/setup/clean` | POST | admin | Remove demo data |
| `/setup/root` | POST | admin | Set tree root |
| `/setup/add-member` | POST | admin | Quick-add family member |
| `/setup/complete` | POST | admin | Mark setup done |
| `/admin/demo-cleanup` | POST | admin | Remove demo data (from admin panel) |
| `/welcome` | GET | member | First-visit tour (shows once) |

### Middleware: Unclaimed redirect

If `site_state == 'unclaimed'` and request is not for:
- `/` (landing), `/claim`, `/demo/*`, `/health`, `/static/*`, `/login`

Then redirect to `/` with a message. Don't let people access `/admin`, `/tree`, etc.
on an unclaimed site.

### Demo data cleanup query

```python
async def remove_demo_data(db: AsyncSession) -> dict:
    """Remove all seed/demo data. Returns counts of deleted records."""
    import json
    
    seed_path = os.path.join(settings.BASE_DIR, "data", "family_tree.json")
    with open(seed_path) as f:
        seed = json.load(f)
    
    # Collect all seed IDs
    person_ids = {p["id"] for p in seed.get("persons", [])}
    moment_ids = {m["id"] for m in seed.get("moments", [])}
    reaction_ids = {r["id"] for r in seed.get("moment_reactions", [])}
    comment_ids = {c["id"] for c in seed.get("moment_comments", [])}
    rel_ids = {r["id"] for r in seed.get("parent_child", [])}
    partnership_ids = {p["id"] for p in seed.get("partnerships", [])}
    
    # Don't delete the admin who claimed the site!
    # (Their person record won't be in the seed file anyway)
    
    counts = {}
    counts["comments"] = await _delete_by_ids(db, MomentComment, comment_ids)
    counts["reactions"] = await _delete_by_ids(db, MomentReaction, reaction_ids)
    counts["moments"] = await _delete_by_ids(db, Moment, moment_ids)
    counts["partnerships"] = await _delete_by_ids(db, Partnership, partnership_ids)
    counts["parent_child"] = await _delete_by_ids(db, ParentChild, rel_ids)
    counts["persons"] = await _delete_by_ids(db, Person, person_ids)
    
    # Also delete any media files that were only referenced by seed moments
    # (cleanup orphaned files)
    
    await db.commit()
    return counts
```

## Design Principles

1. **Demo is preview, not prerequisite.** The demo should feel like a model home tour, not something you have to live in before getting your own house.

2. **Claiming is permanent and instant.** No "are you sure?" loops. One form, one click, you're the admin.

3. **Cleanup is safe.** Demo data has predictable IDs. Real data has random UUIDs. They don't collide. Ever.

4. **Setup is optional.** Every step of the wizard has a "skip" / "do this later" option. The site works fine with zero setup — it's just empty.

5. **Invites are the onramp.** Family members don't create accounts. The admin creates their Person record and sends them an invite. The invite IS the account creation.

6. **First visit is warm.** When Бабушка clicks her invite link on WhatsApp, she should see her name, feel welcomed, and know this is her family's place. Not a generic SaaS onboarding.

7. **No data loss without confirmation.** The "remove demo data" action gets one clear confirmation. After that, it's gone. No "undo" — but also no ambiguity about what was deleted.
