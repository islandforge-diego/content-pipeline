#!/usr/bin/env python3
"""Turn a Google-Form intake response into a client config + brand context file.

Flow:
    1. Client fills the Island Forge intake form (docs/intake/create_intake_form.gs).
    2. Export the responses sheet to CSV (File -> Download -> CSV).
    3. Run:  python pipeline/intake_to_config.py responses.csv --slug acme
       -> writes config/clients/acme.json (from _template.json)
       -> writes config/clients/acme.brand.md (narrative brand context)
       -> prints a checklist of the technical fields YOU still fill in
          (Buffer channel ids, S3 bucket, preview repo/url).

Answers map to columns by matching the form's QUESTION TITLES (substring,
case-insensitive). If you reword a question, update FIELD_KEYS below.
No network and no AI calls — pure transcription.
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "config" / "clients" / "_template.json"

# logical field -> distinctive substring of the form question title
FIELD_KEYS = {
    "name": "business or show name",
    "tagline": "tagline",
    "audience": "who do you serve",
    "website": "website",
    "email": "contact email",
    "story": "your story",
    "voice": "describe your voice",
    "topics": "content topics",
    "donots": "hard do-nots",
    "vocab": "words or phrases",
    "c_primary": "primary color",
    "c_secondary": "secondary color",
    "c_accent": "accent color",
    "c_neutral": "neutral",
    "fonts": "fonts you use",
    "logo": "logo",
    "brandkit": "brand kit",
    "booking": "booking link",
    "keyword": "cta keyword",
    "course": "course or product",
    "links": "other key links",
    "platforms": "which platforms",
    "fb_url": "facebook page url",
    "ig": "instagram handle",
    "tt": "tiktok handle",
    "li": "linkedin profile",
    "yt": "youtube channel",
    "cadence": "how often",
    "post_time": "preferred posting time",
    "tz": "time zone",
    "stories": "daily instagram stories",
    "story_themes": "story themes",
    "partners": "sponsors or partners",
    "loved": "posts you love",
    "else": "anything else",
}

TZ_ALIASES = {
    "central": "America/Chicago", "chicago": "America/Chicago", "ct": "America/Chicago",
    "eastern": "America/New_York", "et": "America/New_York", "new york": "America/New_York",
    "mountain": "America/Denver", "mt": "America/Denver",
    "pacific": "America/Los_Angeles", "pt": "America/Los_Angeles", "los angeles": "America/Los_Angeles",
}
HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}")


def load_row(csv_path, row_index):
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit("No responses in CSV.")
    if row_index is None:
        return rows[-1], rows[0].keys()
    if row_index < 1 or row_index > len(rows):
        sys.exit(f"--row {row_index} out of range (1..{len(rows)}).")
    return rows[row_index - 1], rows[0].keys()


def resolver(row):
    """Return get(field_key) -> answer string, matching column titles by substring."""
    headers = list(row.keys())

    def get(key):
        needle = FIELD_KEYS[key].lower()
        for h in headers:
            if needle in (h or "").lower():
                return (row.get(h) or "").strip()
        return ""
    return get


def hex_or_blank(s):
    m = HEX_RE.search(s or "")
    return m.group(0).upper() if m else ""


def parse_time(s):
    """'3:00 PM' / '3 pm' / '15:00' -> 'HH:MM' (24h), or '' if unparseable."""
    s = (s or "").strip().lower()
    if not s:
        return ""
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", s)
    if not m:
        return ""
    hh = int(m.group(1)); mm = int(m.group(2) or 0); ap = m.group(3)
    if ap == "pm" and hh != 12:
        hh += 12
    if ap == "am" and hh == 12:
        hh = 0
    return f"{hh:02d}:{mm:02d}"


def tz_of(s):
    s = (s or "").strip().lower()
    if "/" in s:
        return s  # already a tz name
    for k, v in TZ_ALIASES.items():
        if k in s:
            return v
    return ""


def per_day_of(s):
    s = (s or "").lower()
    if "once a day" in s or "daily" in s:
        return 1
    return None  # leave template default, flag for review


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", help="exported Google Form responses CSV")
    ap.add_argument("--slug", required=True, help="client slug, e.g. acme")
    ap.add_argument("--row", type=int, default=None, help="1-based response row (default: latest)")
    ap.add_argument("--force", action="store_true", help="overwrite existing config")
    args = ap.parse_args()

    slug = args.slug.strip().lower()
    out_json = ROOT / "config" / "clients" / f"{slug}.json"
    out_md = ROOT / "config" / "clients" / f"{slug}.brand.md"
    if out_json.exists() and not args.force:
        sys.exit(f"{out_json} already exists. Use --force to overwrite.")

    row, _ = load_row(args.csv, args.row)
    get = resolver(row)
    cfg = json.loads(TEMPLATE.read_text())
    todos = []

    # ---- identity ----
    name = get("name") or "Client Name"
    cfg["slug"] = slug
    cfg["display_name"] = name
    cfg["brand"]["name"] = name
    cfg["brand"]["tagline"] = get("tagline")
    if get("voice"):
        cfg["brand"]["voice"] = get("voice")

    # ---- colors ----
    colormap = {"primary": "c_primary", "secondary": "c_secondary",
                "accent": "c_accent", "neutral": "c_neutral"}
    for slot, key in colormap.items():
        hx = hex_or_blank(get(key))
        if hx:
            cfg["brand"]["colors"][slot] = hx
        elif get(key):
            todos.append(f"Color '{slot}': client wrote “{get(key)}” — pick a hex.")
        else:
            todos.append(f"Color '{slot}': not provided — choose one.")
    # preview accent follows the brand accent (fallback primary) if we have a hex
    acc = hex_or_blank(get("c_accent")) or hex_or_blank(get("c_primary"))
    if acc:
        cfg["preview"]["theme"]["accent"] = acc

    # ---- fonts ----
    if get("fonts"):
        cfg["brand"]["fonts"]["display"] = get("fonts")
        todos.append("Fonts: client gave a free-text answer — split into display/body in config.")

    # ---- CTA / links ----
    booking = get("booking")
    if booking:
        cfg["brand"]["link_in_bio"] = booking
        cfg["cta"]["book_link"] = booking
        m = re.search(r"calendly\.com/([^?\s]+)", booking)
        if m:
            cfg["calendly"]["booking_slug"] = m.group(1)
        else:
            todos.append("Booking link isn't Calendly — set calendly.user_uri or leave KPIs manual.")
    else:
        todos.append("No booking link provided.")
    kw = (get("keyword") or "").strip().upper().split()
    if kw:
        cfg["brand"]["cta_keyword"] = kw[0]
        cfg["cta"]["default_keyword"] = kw[0]
    else:
        todos.append("No CTA keyword — pick one.")
    if get("course"):
        cfg["brand"]["course_platform"] = get("course")
    bk = get("brandkit")
    if "canva.com" in bk:
        m = re.search(r"/([A-Za-z0-9_-]{6,})", bk)
        if m:
            cfg["brand"]["canva_brand_kit_id"] = m.group(1)
    elif bk:
        todos.append(f"Brand kit/guide link: {bk}")

    # ---- hard rules ----
    rules = [r.strip(" -•\t") for r in re.split(r"[\n;]+", get("donots")) if r.strip(" -•\t")]
    if rules:
        cfg["brand"]["hard_rules"] = rules

    # ---- channels (handles only; ids connected in Buffer later) ----
    plats = get("platforms").lower()
    selected = [p for p in ["facebook", "instagram", "tiktok", "linkedin", "youtube"] if p in plats]
    if not selected:
        selected = ["facebook", "instagram", "tiktok", "linkedin", "youtube"]
    ch = cfg["buffer"]["channels"]
    if get("fb_url"):
        ch["facebook"]["name"] = get("fb_url")
    if get("ig"):
        ch["instagram"]["handle"] = get("ig").lstrip("@")
    if get("tt"):
        ch["tiktok"]["handle"] = get("tt").lstrip("@")
    if get("li"):
        ch["linkedin"]["name"] = get("li")
    if get("yt"):
        ch["youtube"]["name"] = get("yt")
    # prune to selected platforms
    cfg["buffer"]["channels"] = {k: v for k, v in ch.items() if k in selected}
    cfg["schedule"]["feed"]["reels_channels"] = [c for c in cfg["schedule"]["feed"]["reels_channels"] if c in selected]
    cfg["schedule"]["feed"]["image_channels"] = [c for c in cfg["schedule"]["feed"]["image_channels"] if c in selected]
    todos.append(f"Connect Buffer channels for {selected} and paste each channel id into buffer.channels.*.id.")

    # ---- schedule ----
    t = parse_time(get("post_time"))
    if t:
        cfg["schedule"]["feed"]["default_time"] = t
    tz = tz_of(get("tz"))
    if tz:
        cfg["buffer"]["timezone"] = tz
    elif get("tz"):
        todos.append(f"Time zone '{get('tz')}' unrecognized — set buffer.timezone manually.")
    pd = per_day_of(get("cadence"))
    if pd is not None:
        cfg["schedule"]["feed"]["per_day"] = pd
    elif get("cadence"):
        todos.append(f"Cadence '{get('cadence')}' — set schedule.feed.per_day.")
    if get("stories").lower().startswith("no"):
        cfg["schedule"]["stories"]["per_day"] = 0

    # ---- partners ----
    if get("partners"):
        cfg["partners"] = [{"note": get("partners")}]

    # ---- S3 + brand context wiring ----
    cfg["s3"]["bucket"] = f"{slug}-media"
    cfg["brand"]["context_file"] = f"config/clients/{slug}.brand.md"
    cfg["preview"]["data_file"] = f"content-preview/clients/{slug}/config.json"
    cfg["manual_metrics"]["followers"]["as_of"] = ""

    # ---- write config ----
    out_json.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

    # ---- write brand context md (narrative answers the AI uses for voice) ----
    md = [f"# {name} — Brand Context\n"]
    def block(title, val):
        if val:
            md.append(f"## {title}\n\n{val}\n")
    block("Tagline / mission", get("tagline"))
    block("Who they serve", get("audience"))
    block("Their story", get("story"))
    block("Voice", get("voice"))
    block("Content topics / pillars", get("topics"))
    block("Words/phrases they love or hate", get("vocab"))
    block("Hard do-nots", get("donots"))
    block("Story themes by day", get("story_themes"))
    block("Posts they love (style references)", get("loved"))
    block("Other links", get("links"))
    block("Anything else", get("else"))
    block("Logo", get("logo"))
    block("Website", get("website"))
    block("Contact email", get("email"))
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    # ---- report ----
    print(f"✓ wrote {out_json.relative_to(ROOT)}")
    print(f"✓ wrote {out_md.relative_to(ROOT)}")
    print("\nStill to do (technical / agency side):")
    base = [
        "Create the S3 bucket (Block Public Access ON; public 'media/' prefix) — see aws/ templates.",
        "Add content-preview/clients/{}/config.json + set preview.pages_repo / pages_url.".format(slug),
        "Confirm models block (caption/revise) — template defaults are fine for most.",
        "Add a {}.examples.md few-shot file once you have approved captions.".format(slug),
    ]
    for i, t in enumerate(todos + base, 1):
        print(f"  {i}. {t}")


if __name__ == "__main__":
    main()
