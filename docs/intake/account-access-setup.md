# Account Access Setup (companion to the intake form)

How a new client gives Island Forge access to post on their behalf — **without ever
sharing a password.** Send this alongside (or right after) the intake form.

> **We never ask for your passwords.** Access is granted through each platform's own
> "add a manager/admin" tools, or by you approving a connection while logged in yourself.
> You stay in control and can remove our access at any time. If a platform ever shows a
> password box to *us*, we stop — that's not how this works.

The end state for every channel: it's connected in our scheduler (Buffer), and we drop
its channel ID into your config. Here's how each one gets connected.

---

## Facebook Page + Instagram  ← do these together
Instagram posting requires a **Business or Creator** IG account **linked to a Facebook Page**.

**Preferred — grant us Page access (no password):**
1. Make sure your Instagram is a Business/Creator account and linked to your Facebook Page
   (IG app → Settings → *Account type and tools*; and *Linked accounts* on the Page).
2. In **Meta Business Suite** → **Settings → People** (or **Partners**), add our account
   with **admin / full content** access to the Page.
3. Tell us when it's done — we connect the Page **and** the linked IG from our own login.

**Fallback:** we hop on a 15-min call, you click "Connect" and log into your own
Facebook/Instagram in the popup, and approve. Done.

## LinkedIn
- **Company Page:** add our profile as a **Page admin** (your Page → *Admin tools →
  Manage admins → Add admin*). We connect from our login.
- **Personal profile:** you approve the connection yourself on our onboarding call (LinkedIn
  doesn't allow delegating a personal profile).

## YouTube
- Easiest if your channel is a **Brand Account**: add our Google account as a **Manager**
  (YouTube → *Settings → Permissions → Invite*, or via your channel's Google account).
  We connect from our login.
- **Fallback:** approve the connection on our call while signed into your Google account.

## TikTok
TikTok has limited delegation, so this one is almost always the **call** path:
- On our onboarding call, you log into your own TikTok in the connect popup and approve.
- (Optional, advanced: TikTok **Business Center** can grant partner access if you already
  use it — tell us and we'll send a partner request instead.)

---

## The 15-minute connection call (covers anything above)
For anything that can't be delegated ahead of time, we book one short screen-share:
for each platform you click **Connect**, log into **your own** account in the popup, and
hit **Approve**. We never see your login details, and your two-factor stays on your phone.

## Removing access (whenever you want)
- Facebook/Instagram: Meta Business Suite → People/Partners → remove us.
- LinkedIn: Page → Manage admins → remove.
- YouTube: channel permissions → remove our Google account.
- Any channel: you can also disconnect it from the platform's "connected apps" settings.

---

### Agency-side note (Island Forge)
- The intake form collects **handles/URLs only** — never credentials.
- Once a channel is connected in Buffer, copy its **channel ID** into
  `config/clients/<slug>.json → buffer.channels.<platform>.id`.
- Keep an onboarding checklist per client: delegated-access requested → connected in
  Buffer → channel ID in config. The `intake_to_config.py` TODO list flags the channels
  still needing IDs.
- If a client offers to "just send the password," decline and use OAuth/delegated access —
  it's safer for both sides and survives password/2FA changes.
