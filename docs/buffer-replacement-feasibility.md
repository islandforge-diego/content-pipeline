# Feasibility Spike: Replacing Buffer with Direct Platform APIs

_Prepared 2026-06-30 for the Content Pipeline (Island Forge). Decision doc — no code yet._

> **DECISION (2026-06-30): Keep Buffer; build its cost into client pricing.** Not worth
> inheriting 5 platform audits + permanent token maintenance to save ~$300/yr/client. Plan:
> **Essentials @ $5/channel/mo (annual)** = $25/mo for Deba's 5 channels. Bill each client a flat
> ~$25–30/mo platform fee; Buffer's volume discount past 10 total channels (→$3.33, then $2.50,
> then $1.67/ch) becomes agency margin. Revisit only if a platform changes terms or scale makes
> the build clearly pay back. Details below kept for that future revisit.

## The question
Can the pipeline publish and pull analytics **directly** to FB / IG / TikTok / LinkedIn /
YouTube, dropping Buffer's per-channel cost — given we already host media on S3?

## TL;DR
Technically yes for most platforms, but **the cost isn't the code — it's that each platform
makes _you_ hold the API approvals, OAuth tokens, and verification that Buffer currently holds
for you.** Realistic path is ~2–3 weeks of engineering spread over **1–2 months of calendar
time dominated by platform approvals**, plus permanent token/credential maintenance. Two things
never come back regardless of effort. Worth it as the agency scales clients; **not** worth it
for one client.

---

## Per-platform reality (publish + analytics)

| Platform | Publish API | Analytics API | Approval gate | Calendar time |
|---|---|---|---|---|
| **Facebook Page** | ✅ Graph API | ✅ Page Insights | Meta App Review + **Business Verification** | 1–3 wks |
| **Instagram** (Business) | ✅ Graph API (`instagram_business_content_publish`) | ✅ IG Insights | Same Meta app covers IG + FB | 1–3 wks |
| **YouTube** | ✅ Data API v3 `videos.insert` | ✅ YouTube Analytics API | Google OAuth verification (`youtube.upload`) | 1–4 wks |
| **TikTok** | ⚠️ Content Posting API | ⚠️ Display/Data API | **App audit** (2–4 wks, multiple rounds) | 3–6 wks |
| **LinkedIn** | ⚠️ Posts API (`w_organization_social`) | ⚠️ org analytics | Community Management API use-case review | variable |

One Meta app covers **both IG and FB Page** — that's why Meta is the highest-leverage first step.

### Approval friction, ranked
1. **TikTok — worst.** Until your app passes audit, every post is forced **SELF_ONLY** (only the
   creator sees it), max **5 users**, accounts must be **private** at post time. Audit takes
   2–4 weeks with multiple feedback rounds. **Unusable for real client posting until audited.**
2. **Meta (IG + FB).** App Review (per-permission screencast showing the full user journey) **plus
   Business Verification** (legal business docs). The Jan 2025 scope rename means the current
   permissions are `instagram_business_basic` + `instagram_business_content_publish`.
3. **YouTube.** OAuth verification required. Apps that haven't passed Google's compliance audit
   can **only upload as private** — public publishing needs the verified/audited project.
   `youtube.upload` may trigger restricted-scope review (possible annual CASA security
   assessment — confirm during build). Quota: a video upload costs **1,600 units**; default
   **10,000 units/day = ~6 uploads/day** (fine for our volume).
4. **LinkedIn.** Company-page posting (`w_organization_social`) needs the Community Management
   API approved — a separate use-case review on top of basic access. Personal-profile posting
   (`w_member_social`) is easier but isn't the channel we publish to.

---

## What never comes back (hard platform limits, not Buffer's)
- **Deba's personal FB profile** — her largest audience — has **no publish or analytics API at
  all**. Already manual today; stays manual forever. (This is why the Performance tab's FB numbers
  come from a manual dashboard export.)
- **IG interactive story stickers** (polls / questions) — **no API**. Still needs the in-app tap.
  Identical to today's Buffer "story reminder" flow.
- **IG Reels audio** — the Graph API **can't attach Instagram's music library**. Any trending
  sound must be **baked into the video file** before upload (editor step). Buffer has the same limit.
- **IG Reels via API** — only 5–90s, 9:16 land in the Reels tab; outside that posts as plain video.
  Fine for our format.

---

## Credentials checklist (what you'd register / provide)
**Meta (IG + FB Page)**
- [ ] Meta Developer account + an App
- [ ] **Business Verification** (legal business docs for Island Forge)
- [ ] Confirm Deba's IG is a **Business** account, linked to the FB Page
- [ ] Public **privacy policy URL**
- [ ] App Review submission + screencast per permission

**Google / YouTube**
- [ ] Google Cloud project + OAuth consent screen
- [ ] App verification (channel ownership, `youtube.upload` scope)

**TikTok**
- [ ] TikTok for Developers account + app
- [ ] Content Posting API access + **audit submission**

**LinkedIn**
- [ ] LinkedIn Developer app
- [ ] Community Management API access request (use-case review), page admin

---

## Cost comparison
- **Buffer Essentials:** $5/channel/mo (annual) or $6/channel/mo (monthly).
- **Deba (5 channels):** ~**$25/mo = $300/yr** annual, or $360/yr monthly.
- **Scales per client:** 5 clients ≈ $1,500/yr · 10 clients ≈ $3,000/yr (Buffer discounts after
  10 channels total).
- **Direct build:** one-time ~2–3 eng-weeks + approvals, then ongoing token-refresh / breakage
  maintenance (FB re-auth, scope deprecations like the Jan 2025 rename, TikTok re-audits).

**Break-even logic:** at **one** client, replacing Buffer loses — the build + maintenance dwarfs
$300/yr. The economics **flip as you add clients**: Buffer cost is per-client recurring; the
direct-publish layer is built once and reused across every client config. That's also an agency
moat (clients can't easily leave the stack).

---

## Recommended path (if/when we proceed)
**Phased, lowest-risk, never go dark:**
1. **Meta first** — IG + FB Page publish + insights (one app, one approval, two biggest
   automatable channels). Run **alongside Buffer** until proven on real posts.
2. **YouTube** next (clean API, low volume).
3. **Defer TikTok + LinkedIn** until their audits/reviews clear — keep them on Buffer meanwhile.
4. Once a platform is proven, drop it from Buffer → Buffer bill shrinks channel by channel.

Keep the manual seams we already have (FB personal, IG story stickers) — they don't change.

## Alternative considered
**Self-host an open-source scheduler (Postiz / Mixpost).** Saves building the publish/UI layer,
but you **still register your own Meta/TikTok/LinkedIn/Google apps and pass the same approvals** —
it removes ~the easy 20% (code) and none of the hard 80% (approvals). Worth a look only if we want
a ready-made UI rather than extending our own web UI.

## Open items to confirm during build
- Is Deba's IG already a **Business** account linked to the Page? (blocks Meta path if not)
- Does `youtube.upload` trigger restricted-scope CASA assessment for our project type?
- Island Forge business docs ready for Meta Business Verification?

---

_Sources: Meta for Developers (Instagram Platform / Content Publishing), TikTok for Developers
(Content Posting API), Microsoft Learn (LinkedIn Community Management / Posts API), Google for
Developers (YouTube Data API quota), Buffer pricing 2026._
