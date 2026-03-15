# Family Book — The Real Vision

## What Is It, Actually?

Not a family tree app. Not a genealogy tool. Not a private social network.

**Family Book is the family's living room — digital, sovereign, and permanent.**

It's the coffee table photo album that never gets lost in a move. It's the wall of framed photos at grandma's house, except grandma is in Moscow and the photos update themselves. It's the place where Tyler's daughter — at 4, at 14, at 40 — can open a single page and see every face, every name, every story, every connection that makes her who she is.

The tree is the skeleton. The life is everything else.

## What Keeps It Alive?

A family tree app dies the day it's completed. You enter everyone, draw the lines, and then what? Nobody opens it again until someone dies or gets married.

Family Book stays alive because **life keeps happening:**

### The Engine: Moments

The beating heart is **Moments** — a reverse-chronological feed of family life, scoped by relationship and geography.

- Luna took her first steps (video, 12 seconds, Tyler uploaded)
- Бабушка Наташа made pelmeni with Дедушка (photo, Moscow)
- Cousin Dmitri graduated university (photo + note, Calgary)
- Tía María's new puppy (photo, Madrid)
- Uncle Mike caught a fish THIS BIG (photo, Vancouver Island)
- Baby announcement: Tyler's sister is expecting (milestone)
- Memorial: Дедушка Борис passed away, January 12 (memorial, photo gallery of his life)

**This is what Facebook does well.** The feed. The ambient awareness of family life. The "oh, cousin Sasha is in Barcelona this week!" serendipity.

Family Book steals that engine and puts it in the living room. No ads. No algorithm deciding what you see. No selling your baby photos to train AI models. No "memories from 6 years ago" that Facebook uses to keep you scrolling.

Moments are:
- **Posted by family members** (photo/video/text, mobile upload)
- **Auto-generated from milestones** (birthday approaching, anniversary, new baby, memorial date)
- **Imported from connected platforms** (see below)
- **Scoped by permission layer** — Layer 2 family sees grandkids' first steps. Layer 5 distant cousins see "a new photo was added" but not the photo itself.

### The Glue: Milestones

Milestones are the structural events that shape the tree AND generate Moments:

| Milestone | Tree Effect | Moment Generated |
|-----------|------------|------------------|
| Birth / New baby | New Person + ParentChild edges | "Welcome to the family! [name] was born [date]" + photo |
| First steps, first words | None (enrichment) | Photo/video Moment |
| First day of school | None | Photo Moment + age computation |
| Graduation | None | Photo Moment |
| Engagement | New Partnership(kind=engaged) | "Congratulations! [name] and [name] are engaged!" |
| Marriage | Partnership status → married | "Wedding! [name] and [name] got married [date]" + photo gallery |
| Divorce | Partnership status → dissolved | No auto-Moment (sensitive). Admin discretion. |
| New home / moved | Person.residence updated | "[name] moved to [city]!" (optional, member chooses to share) |
| Travel | None (enrichment) | "Family trip to [place]!" + photos |
| Death | Person.is_living → false, visibility → memorial | Memorial Moment with photo gallery of their life |
| Anniversary | None (computed) | Auto-generated: "[names]'s 25th wedding anniversary!" |
| Birthday | None (computed) | Auto-generated: "Happy birthday [name]! 🎂" with age |

### The Value Proposition Per Audience

**For Tyler's daughter (4 now, 14 later, 40 eventually):**
- At 4: Tap faces, see names, hear "that's your бабушка in Russia!"
- At 14: Scroll the Moments feed, see family across three countries, feel connected to cousins she's met twice
- At 40: The complete archive. Every photo, every milestone, every face. The thing she'll show HER kids.
- **What Facebook can't do:** Facebook wasn't designed to last 40 years. Accounts get deleted, policies change, photos get compressed, memories get algorithmed. Family Book is a sovereign archive.

**For Бабушка Наташа (Moscow):**
- Opens Family Book on her phone, sees yesterday's photo of her granddaughter at the park in Madrid
- Doesn't need Facebook. Doesn't need Instagram. Doesn't need to understand Telegram channels.
- One website. In Russian. With her granddaughter's face.
- **Why she'll actually use it:** New photos of the kids. That's it. That's the killer feature for grandparents.

**For Cousin Dmitri (Calgary):**
- Sees the family he barely knows in Russia connected by name, face, and relationship label
- Uploads his graduation photo, his whole extended family sees it
- Discovers his second cousin in Spain is also into skiing
- **Why he'll actually use it:** The tree gives him context. The Moments give him connection.

**For Tyler and Yuliya (admins):**
- Single place to share kid photos that ISN'T Meta's servers
- Extended family stays connected without Tyler being the human router
- The family archive survives any platform's business model changes
- **Why they'll maintain it:** It replaces 4-5 WhatsApp groups, a Facebook account they don't want, and the anxiety of "are these photos backed up?"

## Platform Integration — Where Each Fits

### SMS / MMS (primary notification channel — universal)
**Role:** The notification backbone. Every family member on Earth can receive a text message.

**Why SMS wins:**
- Бабушка in Moscow has SMS. Aunt Shelley in Calgary has SMS. Every phone everywhere has SMS.
- No app to install. No bot to add. No API pricing games.
- iMessage, SMS, WhatsApp — families already share baby photos through these channels because they *feel* sovereign and private. Family Book should feel the same way.
- MMS supports photos directly in the message — grandma sees the baby photo in her texts without tapping a link.

**Integration:**
- **Outbound notifications:** SMS with a deep link to the latest Moments. "3 new photos from Tyler! → martin.fm/moments"
- **MMS option:** For milestone photos (first steps, birthdays), send the photo directly as MMS. Бабушка sees it without opening a browser.
- **Birthday reminders:** SMS: "Дядя Саша's birthday is tomorrow! 🎂 → martin.fm/people/uuid"
- **Weekly digest:** SMS: "This week in your family: 5 new photos, Dmitri graduated! → martin.fm/moments"
- **Inbound (future):** Reply with a photo → it gets added to Moments (requires MMS ingestion pipeline, Phase 3+)

**Implementation:**
- Twilio or similar SMS/MMS API (proven, global reach, simple pricing per message)
- Phone numbers already in Person.contact_whatsapp / Person.contact_signal fields (rename to contact_phone or add dedicated field)
- International SMS: Twilio handles routing to Russia, Canada, Spain, US
- Cost: ~$0.01-0.05 per SMS depending on country. For a family of 30-50 people, weekly digest = $1-2/month total.

**The sovereignty angle:** If the SMS setup is clean and efficient, it becomes part of the overall data sovereignty story. Your notifications don't go through Meta or Telegram's servers. They go through the phone network — the most decentralized communication infrastructure humans have built.

### WhatsApp (natural bridge — where families already live)
**Role:** Not a bot integration. A human bridge.

**Reality:** Most close families already have a WhatsApp group. Baby photos, travel updates, birthday wishes — they're all there already. Family Book doesn't need to replace this or automate it.

**Integration (light touch):**
- **Manual bridge:** Tyler (or any admin) shares Family Book links in the family WhatsApp group: "New photos up! → martin.fm/moments"
- **Profile photo sync:** wacli can passively pull profile photos (low-risk, personal account automation)
- **No bot, no Business API, no automation.** WhatsApp is the existing family channel. Family Book is the archive. They complement each other without needing an API bridge.
- **Data export:** WhatsApp chat export (built-in feature) can be ingested by Family Book for historical photo recovery (Phase 3)

**Verdict:** WhatsApp integration is a *human* workflow, not a technical one. The family WhatsApp group continues to exist. Family Book is where the data lives permanently.

### Email (Envelope)
**Role:** Ingestion pipeline for data exports + magic link auth + milestone notifications.

**Integration:**
- **Magic link auth:** Primary login method for family members who don't use Facebook
- **Facebook data export:** Forward the Facebook download email → Envelope parses and stages
- **Milestone notifications:** Weekly digest email: "This week in your family: 3 new photos, Dmitri's birthday tomorrow"
- **Photo ingestion:** Email photos to family@martin.fm → auto-attached to sender's Person record
- **Why it fits:** Email is universal. Every family member has it. Zero onboarding friction for notifications.

### Facebook (reluctant but necessary)
**Role:** Optional identity linking + profile photo enrichment + data export ingestion.

**Integration:**
- **OAuth:** Optional "Connect with Facebook" to link identity and import profile photo
- **Data export:** One-time family data import (photos, profile, friend connections) via Envelope pipeline
- **Not a login method.** Not the primary anything. A data source that some family members will use.
- **Why it fits:** Some relatives have 15 years of family photos on Facebook. That data is valuable. Import it, then ignore Facebook.
- **Reality check:** Facebook's Graph API has been steadily restricting access. Build for a future where Facebook gives you nothing.

### TikTok
**Role:** Content import for younger family members who live on TikTok.

**Integration:**
- **Manual:** Family members share TikTok links in Moments ("Look what Cousin Anna posted!")
- **Auto-import (Phase 3+):** If TikTok provides data export, ingest videos → Family Book
- **Embed:** TikTok links in Moments render as embedded video players (oEmbed)
- **Why it fits:** Teenage cousins won't upload to Family Book. They'll upload to TikTok. Let them crosspost with minimal friction. The video of your 16-year-old cousin's dance recital should be in the family archive even if it started on TikTok.

### Instagram
**Role:** Similar to TikTok — content import for visually-oriented family members.

**Integration:**
- **Manual crosspost:** Share Instagram links in Moments
- **Data export import:** Instagram provides data download (JSON + media). Same pipeline as Facebook export.
- **Embed:** Instagram oEmbed for linked posts
- **Why it fits:** Travel photos, food photos, life updates. The stuff families already share on Instagram but scattered across individual accounts.

### Telegram (optional — power users + Russian family)
**Role:** Rich bot interface for family members who use Telegram.

**Reality:** The Russian side of the family uses Telegram, but even that may be temporary (regulatory pressure). Telegram is a strong *optional* channel, not the primary one.

**Integration:**
- **Family Book Telegram Bot:** For family members who prefer it. Photo upload, commands, inline keyboards.
- **Notifications:** Milestone alerts, birthday reminders, Moments digest — via bot
- **Bot commands:** `/recent` (latest Moments), `/birthday` (upcoming), `/upload` (add photo)
- **Why it's optional, not primary:** Not everyone uses Telegram. SMS reaches everyone. Telegram is the rich-UI bonus for those who want it.

### Signal (optional — privacy maximalists)
**Role:** Alternative channel for family members who prioritize privacy above all.

**Integration:**
- OpenClaw has demonstrated Signal as a viable portal into private systems
- Photo ingestion: send photos to a Signal number → Family Book receives via OpenClaw bridge
- Notifications: milestone alerts, digest
- **Trade-off:** Signal's bot/automation story is less mature. OpenClaw bridges this but adds dependency.
- **Verdict:** Nice-to-have for Phase 3+. Philosophically aligned with data sovereignty.

### Mastodon / ActivityPub (Phase 4+)
**Role:** Federated family presence for the post-platform future.

**Integration:**
- **GoToSocial instance** on `social.martin.fm` (lightweight, single-user instance is fine)
- **Moments → posts:** Family Moments (with appropriate visibility) cross-post to the fediverse
- **Follow from anywhere:** Family members with Mastodon/Pixelfed accounts follow the family instance
- **Federation between Family Books:** When two families connect, their GoToSocial instances federate naturally
- **Why it fits:** This is the long game. Platforms die. Protocols survive. ActivityPub is the protocol bet for family presence.

### Platform Integration Architecture

```
                    ┌──────────────────────────┐
                    │     Family Book Core      │
                    │  (SQLite + FastAPI + D3)  │
                    └────────────┬─────────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            │                    │                     │
     ┌──────▼──────┐    ┌───────▼───────┐    ┌───────▼───────┐
     │   Inbound    │    │    Outbound   │    │   Identity    │
     │  Ingestion   │    │ Notifications │    │   Linking     │
     └──────┬───────┘    └───────┬───────┘    └───────┬───────┘
            │                    │                     │
    ┌───────┼────────┐   ┌──────┼──────┐       ┌──────┼──────┐
    │       │        │   │      │      │       │      │      │
  Email  TikTok  Facebook SMS/MMS Email   Facebook  Google  Magic
(Envelope)(oEmbed)(Export) (Twilio)(SMTP)  (OAuth)  (OAuth) Link
    │       │        │      │      │       
  Photos  Links   Photos  Photos  Digest   
  Exports Embeds  Profile  Links  Weekly   
  
  Optional: Telegram bot (power users)
  Optional: Signal (via OpenClaw bridge)
  WhatsApp: human bridge (admin shares links in family group)
```

## Data Sovereignty — The Real Pitch

Here's what Tyler is actually building, even if he hasn't said it this way yet:

**Family Book is a data sovereignty platform for families.**

Every photo Tyler's daughter has ever taken. Every video of her first steps. Every picture of Бабушка making pelmeni. Every shot from the family trip to Navacerrada. All of this currently lives on:
- Meta's servers (Facebook, Instagram, WhatsApp)
- ByteDance's servers (TikTok)
- Apple's servers (iCloud)
- Google's servers (Google Photos)

Each of these companies:
- Can change their terms of service tomorrow
- Can delete your account for any reason
- Can use your family photos to train AI models
- Can compress, crop, or algorithmically filter your memories
- Will eventually shut down, get acquired, or pivot

Family Book says: **your family's data lives on your infrastructure, under your control, backed up to YOUR storage, accessible by YOUR family, forever.**

This isn't anti-technology. It's anti-dependency. You use Facebook TO IMPORT. You use WhatsApp TO NOTIFY. You use TikTok TO EMBED. But the source of truth — the canonical archive of your family — lives in a SQLite database that you can hold in your hand.

A SQLite file is the most durable digital artifact humans have invented. It will be readable in 50 years. Can you say that about your Facebook account?

## What Makes It Fresh — The Content Loop

The death spiral of family apps: build → populate → nobody updates → app dies.

Family Book breaks this with three content loops:

### Loop 1: Baby Photos (the killer app)
- New parents are DESPERATE to share baby photos with family
- But they don't want those photos on Facebook/Instagram (privacy, AI training, digital footprint)
- Family Book is the answer: private, family-only, sovereign
- Every new baby photo is a Moment that pulls grandparents back to the app
- This is the engine. This is what Бабушка checks every morning.

### Loop 2: Auto-Generated Milestones
- Birthday reminders create engagement without anyone posting
- Anniversary milestones remind the family of happy events
- Memorial dates honor the departed
- "X years ago today" WITHOUT the Facebook manipulation — just honest memory
- These keep the app alive even when nobody actively posts

### Loop 3: Travel & Life Updates
- "We're in Barcelona this week!" + photos
- Replaces the WhatsApp group status update
- Stays in the archive (WhatsApp messages get buried)
- Visible to the right people (Layer 2 sees vacation photos, Layer 5 just sees you traveled)

### Loop 4: Platform Import (passive)
- WhatsApp profile photo sync keeps faces current
- Instagram/TikTok crossposting brings content in with minimal effort
- Facebook data export is a one-time bonanza of historical photos
- Family members don't need to "use" Family Book actively — their existing platform behavior feeds it

## The 40-Year Test

Close your eyes. It's 2066.

Tyler's daughter is 45. She has kids of her own. Tyler is 84.

She opens Family Book on whatever device exists in 2066. She sees:
- Her great-grandmother Наташа, who she barely remembers, smiling in a kitchen in Moscow
- The video of her own first steps, uploaded when she was 1
- Her dad's handwritten (typed, but still) bio from when he was 44 and building this thing
- Her wedding photos, imported from whatever platform existed in 2048
- Her children's faces, uploaded yesterday by their grandmother Yuliya
- The complete graph of who she is, where she came from, and who loves her

Facebook won't exist in 2066. Instagram won't exist in 2066. Family Book — or its SQLite backup — will.

**That's the product.**

## What Changes In The Spec

The current spec (v2) is architecturally sound but emotionally dead. It describes a database with views. It needs:

1. **Moments** — a new core entity. Reverse-chronological feed of family life. The main screen after the tree.
2. **Milestones** — structured life events that affect the tree AND generate Moments.
3. **Platform ingestion pipeline** — generalized inbound from WhatsApp, email, TikTok, Instagram, Facebook.
4. **Notification engine** — outbound to WhatsApp, email, Telegram. Birthday reminders, new Moments digest, milestone alerts.
5. **Media-first design** — photos and videos are the primary content, not text fields. The UI should feel like a photo album, not a database form.
6. **The root person's view** — design the entire UX for a 4-year-old tapping faces on an iPad. Then for a 14-year-old scrolling Moments. Then for a 40-year-old searching the archive.
7. **"Forward to Family Book"** — the lowest-friction ingestion path. Email a photo. WhatsApp a video. It shows up in Moments.
8. **Memorial mode** — when someone dies, their profile becomes a memorial with a curated photo gallery, a bio, and a timeline of their life events. This is sacred. Design it with reverence.

## Phasing (revised with the real vision)

### Phase 1 — The Tree + Cards + Admin (still the foundation)
Everything in spec v2 Phase 1. This is the skeleton.

### Phase 1.5 — Moments + Media (the life)
- Moments entity (photo/video/text/milestone, posted by family member or auto-generated)
- Moments feed (reverse-chronological, main screen for logged-in members)
- Photo/video upload to Moments (mobile-optimized)
- Auto-generated milestone Moments (birthdays, anniversaries)
- Memorial mode for deceased persons

### Phase 2 — Notifications + Ingestion (the glue)
- SMS/MMS notifications via Twilio (birthday reminders, milestone alerts, weekly digest with deep links)
- MMS photo delivery for key moments (grandma sees the photo in her texts)
- Email ingestion via Envelope (forward photos → Moments)
- Email notifications (weekly digest, milestone alerts)
- Magic link + invite improvements
- i18n (en, ru, es)

### Phase 3 — Platform Import + Optional Channels (the data liberation)
- Facebook data export ingestion (one-time photo + profile import)
- Instagram data export ingestion
- WhatsApp chat export ingestion (historical photo recovery)
- TikTok/Instagram oEmbed in Moments
- GEDCOM import pipeline
- Telegram bot (optional, for power users + Russian family)
- Signal bridge via OpenClaw (optional, for privacy maximalists)

### Phase 4 — Privacy Engine + Federation
- Graph-distance ACL
- Life-event mutations
- Federation between Family Book instances
- ActivityPub / GoToSocial

---

*"Facebook is the mall. This is our living room. And we own the house."*
