# Platform Integration Research — Open Questions

## Must Research Before Build

### WhatsApp
- [ ] **wacli capabilities**: Can it monitor a group chat in real-time? Pull new messages since last check? Extract media? What are the ToS risks?
- [ ] **WhatsApp Business API**: Current pricing tiers (per-message by country). Template approval process. Monthly costs for family of 50. Can it READ from groups or only SEND?
- [ ] **WhatsApp Web automation**: Can a browser agent (Playwright/Puppeteer) scrape a group chat reliably? How often does WhatsApp change the DOM? Session persistence?
- [ ] **WhatsApp Cloud API vs On-Premise API**: Differences, costs, self-hosting options
- [ ] **Group export automation**: Can the export be triggered programmatically or only manually from the phone?

### Facebook / Meta
- [ ] **Facebook data export**: Can it be triggered via API? Or only manually from Settings? How often can you request it?
- [ ] **Facebook Graph API**: What's still accessible in 2026? Profile photos? Friends list? Family relationships? (Historically restricted more each year)
- [ ] **Facebook Messenger API**: Can a bot be in a Messenger group? Read messages? Send media?
- [ ] **Instagram Basic Display API / Graph API**: Can it pull a user's posts? Their media? Is there a data export API?
- [ ] **Browser agent approach**: Can an AI agent automate Facebook data exports, Instagram media downloads, etc.?

### Telegram
- [ ] **Bot API group monitoring**: Can a bot silently monitor a group and extract messages + media? (Yes, if added as admin — but verify current API)
- [ ] **Russian shutdown status**: Current state of Telegram access in Russia. VPN workarounds? Impact on reliability?
- [ ] **Bot API limits**: Rate limits on sending media messages to multiple users

### Signal
- [ ] **OpenClaw bridge capabilities**: Can it send photos? Receive photos? Handle group messages?
- [ ] **signal-cli / signald**: Current state of unofficial Signal automation tools
- [ ] **ToS risk**: Does Signal ToS prohibit automated messaging? What's the enforcement reality?

### SMS/MMS
- [ ] **Twilio international SMS delivery rates**: Reliability by country. Russia specifically.
- [ ] **Twilio MMS**: Confirm US/CA only limitation. Any workarounds?
- [ ] **Alternative SMS providers**: Vonage, MessageBird, Plivo — do any support international MMS?
- [ ] **RCS**: Current state of Rich Communication Services. Google Messages adoption. Can Twilio send RCS?

### iMessage
- [ ] **BlueBubbles / OpenClaw iMessage bridge**: Can it send photos? Group messages?
- [ ] **Beeper / Texts.com**: Do any iMessage bridges still work post-Apple crackdown?
- [ ] **Reality check**: iMessage is the dominant family messaging app in North America. If we crack this, it's huge.

### Creative / Fudge Solutions
- [ ] **AI browser agents**: Can Playwright + LLM automate platform interactions that lack APIs? What's the cost/reliability?
- [ ] **IFTTT / Zapier / Make**: Any existing automations for WhatsApp→webhook, Instagram→webhook?
- [ ] **Matrix bridges**: Matrix has bridges for WhatsApp, Telegram, Signal, Facebook. Could Family Book use Matrix as the universal bridge layer instead of building each integration?
- [ ] **Mautrix bridges**: Specifically mautrix-whatsapp, mautrix-telegram, mautrix-signal, mautrix-facebook. Open source. Self-hosted.
- [ ] **Beeper's multi-protocol approach**: What did they learn? What broke? What worked?

## The Matrix Bridge Hypothesis

This might be the most promising creative solution: instead of building 6 separate channel integrations, use **Matrix (or Mautrix) bridges** as the universal translation layer.

```
WhatsApp ←→ Mautrix-WhatsApp ←→ Matrix ←→ Family Book
Telegram ←→ Mautrix-Telegram ←→ Matrix ←→ Family Book  
Signal   ←→ Mautrix-Signal   ←→ Matrix ←→ Family Book
Facebook ←→ Mautrix-Facebook ←→ Matrix ←→ Family Book
iMessage ←→ Matrix-iMessage  ←→ Matrix ←→ Family Book
SMS      ←→ Matrix-SMS       ←→ Matrix ←→ Family Book
```

Family Book would only need ONE integration (Matrix client) instead of six. The bridges handle the platform-specific complexity. They're open source, actively maintained, and already solve most of the hard problems.

**Research needed:**
- [ ] Current state of Mautrix bridges (reliability, features, limitations)
- [ ] Self-hosting requirements (RAM, CPU, complexity)
- [ ] Can bridges handle media (photos, videos) bidirectionally?
- [ ] Latency: real-time or noticeable delay?
- [ ] ToS risks per platform (same as direct integration)

## Cost Model Thinking

Families would pay for this. $5-10/month shared across a family of 30-50 people is less than Netflix.

| Tier | Channels | Cost | Notes |
|------|----------|------|-------|
| Free | Email only | $0 | Email delivery + web archive |
| Family | Email + 2 channels (e.g., WhatsApp + Telegram) | $5/mo | Covers messaging API costs |
| Premium | All channels + browser agent automation | $10/mo | Full platform ingestion |

Hosting (Railway) + messaging APIs + storage = real costs that a small monthly fee covers easily.
