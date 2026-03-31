# Domain Setup — Family Book

> Generated: 2026-03-24  
> Railway project: `family-book` (production)  
> Railway URL: https://family-book-production.up.railway.app

## Current Status

| Domain | Railway Custom Domain | DNS Status | What To Do |
|---|---|---|---|
| `family.martin.fm` | ✅ Added | ❌ Points to Netlify (75.2.60.5) — meta-refresh redirect | Update DNS at dyna-ns.net |
| `volodin.online` | ✅ Added (2026-03-24) | ❌ Points to old Readymag (192.64.119.192) | Update DNS at Namecheap |
| `www.volodin.online` | ✅ Added (2026-03-24) | ❌ Not configured | Update DNS at Namecheap |

---

## 1. family.martin.fm

### Problem
DNS is an A record pointing to Netlify (75.2.60.5), which serves a tiny HTML page with `<meta http-equiv='refresh'>` redirecting to Railway. This works but:
- Adds a redirect hop (slower)
- SSL cert is Netlify's, not Railway's
- No proper HTTPS termination at Railway

### Required DNS Change
**DNS Provider:** dyna-ns.net (nameservers: `ns1.dyna-ns.net`, `ns2.dyna-ns.net`)

| Action | Host | Type | Value |
|---|---|---|---|
| **Delete** existing | `family` | A | `75.2.60.5` |
| **Add** new | `family` | CNAME | `5cecnyka.up.railway.app` |

### Steps
1. Log in to your DNS provider for `martin.fm` (dyna-ns.net)
2. Find the `family` subdomain record (currently an A record → 75.2.60.5)
3. Delete that A record
4. Create a new CNAME record:
   - **Host/Name:** `family`
   - **Type:** CNAME
   - **Value/Target:** `5cecnyka.up.railway.app`
   - **TTL:** 300 (or lowest available)
5. Wait 5–15 minutes for propagation
6. Verify: `dig family.martin.fm CNAME +short` should return `5cecnyka.up.railway.app`
7. Visit https://family.martin.fm — should load Family Book directly (no redirect)
8. Check Railway dashboard → the domain should show a green checkmark once DNS propagates

### After DNS Update
- Railway will automatically provision an SSL certificate via Let's Encrypt
- The Netlify site/redirect can be deleted (it will no longer be needed)

---

## 2. volodin.online

### Problem
DNS points to old Readymag site at `192.64.119.192`. Need to point to Railway instead.

### Required DNS Changes
**DNS Provider:** Namecheap (nameservers: `dns1.registrar-servers.com`, `dns2.registrar-servers.com`)

| Action | Host | Type | Value |
|---|---|---|---|
| **Delete** existing | `@` | A | `192.64.119.192` |
| **Add** new | `@` | CNAME | `y2xgaw83.up.railway.app` |
| **Add** new | `www` | CNAME | `84cnh6ai.up.railway.app` |

> **Note:** Namecheap supports CNAME on the root domain when using their BasicDNS/FreeDNS nameservers. They implement this as ALIAS/ANAME internally.

### Steps
1. Log in to [Namecheap](https://www.namecheap.com/) → Domain List → `volodin.online` → **Manage**
2. Go to **Advanced DNS** tab
3. **Delete** the existing A record for `@` (Host: `@`, Value: `192.64.119.192`)
4. **Delete** any other A/CNAME records you don't need (check for Readymag records)
5. **Add** a new record:
   - **Type:** CNAME
   - **Host:** `@`
   - **Value:** `y2xgaw83.up.railway.app`
   - **TTL:** Automatic
6. **Add** another record:
   - **Type:** CNAME
   - **Host:** `www`
   - **Value:** `84cnh6ai.up.railway.app`
   - **TTL:** Automatic
7. **Save all changes**
8. Wait 5–30 minutes for propagation (Namecheap is usually fast)
9. Verify:
   ```bash
   dig volodin.online A +short        # Should resolve to Railway IP
   dig www.volodin.online CNAME +short # Should return 84cnh6ai.up.railway.app
   ```
10. Visit https://volodin.online — should load Family Book
11. Check Railway dashboard → both domains should show green checkmarks

### If Namecheap Won't Accept CNAME on Root (@)
Some configurations don't allow CNAME on the bare domain. If that happens:
1. Use a **URL Redirect** instead:
   - **Source URL:** `volodin.online`
   - **Destination URL:** `https://www.volodin.online`
   - **Type:** Permanent (301)
2. Then only the `www` CNAME is needed, and `www.volodin.online` becomes the canonical URL

---

## 3. Verification Commands

After making DNS changes, run these to verify:

```bash
# family.martin.fm
dig family.martin.fm CNAME +short
# Expected: 5cecnyka.up.railway.app

curl -sI https://family.martin.fm | head -5
# Expected: HTTP/2 200, server: railway-edge

# volodin.online
dig volodin.online +short
# Expected: Railway IP (not 192.64.119.192)

curl -sI https://volodin.online | head -5
# Expected: HTTP/2 200, server: railway-edge

# www.volodin.online
dig www.volodin.online CNAME +short
# Expected: 84cnh6ai.up.railway.app
```

---

## 4. Railway Custom Domains (Reference)

All domains were added via Railway CLI. To manage:

```bash
cd ~/Dropbox/Code/family-book

# List all domains
railway domain --json

# Add a new custom domain
railway domain example.com --service family-book --json

# Remove a domain (via Railway dashboard or API)
# CLI doesn't support domain removal — use https://railway.com dashboard
```

### Railway Domain IDs (for API use)
| Domain | Railway ID |
|---|---|
| `family.martin.fm` | `efea1fdd-0d32-4a31-b756-6b2298dcaa31` |
| `volodin.online` | `0ef4f8af-1de3-41c8-9cf6-c85f0035b92a` |
| `www.volodin.online` | `1b70b284-4419-44d8-82f2-a1807270a946` |
| `volodin.space` | `32e9d1b9-323e-438c-b82e-6a3ee082eece` |
| `www.volodin.space` | `86d43fad-3bae-465d-b9b0-f93d222e173b` |

---

## 5. App Environment Variables

After domains are working, update `BASE_URL` in Railway environment variables to the preferred canonical domain:

```bash
cd ~/Dropbox/Code/family-book

# Current value:
# BASE_URL=https://family-book-production.up.railway.app

# Update to preferred domain (pick one):
railway variables --set "BASE_URL=https://volodin.online"
# or
railway variables --set "BASE_URL=https://family.martin.fm"
```

**Why:** The app uses `BASE_URL` for:
- CORS `allow_origins` (in `app/middleware/security.py`)
- Magic link URLs in emails
- Any absolute URL generation

If you want BOTH domains to work with CORS, the app code would need a small update to accept multiple origins. For now, pick one canonical domain and have the other redirect to it (or update the CORS middleware to allow both).
