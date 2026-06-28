"""caption_gen.py — generate platform-specific captions via Claude API.

Pulls authentic brand voice from the client's config plus an optional long-form
context file (brand.context_file). Can use video frames for visual grounding and
applies platform-aware CTAs (ManyChat comment-keyword vs. real booking link).
"""
import json
import re
from pathlib import Path

import anthropic

# Sonnet writes the first draft (voice fidelity where it matters); Haiku handles
# the cheap quick-feedback revisions. Overridable per client via config "models".
DEFAULT_MODELS = {
    "caption": "claude-sonnet-4-6",
    "revise": "claude-haiku-4-5-20251001",
}

# Repo root = two levels up from this file (pipeline/ -> repo)
ROOT = Path(__file__).resolve().parent.parent


def _model(client: dict, task: str) -> str:
    return client.get("models", {}).get(task) or DEFAULT_MODELS[task]


# --- Style enforcement (belt-and-suspenders; the prompt asks, this guarantees) ---

STYLE_RULES = (
    "STYLE RULES (strict, non-negotiable):\n"
    "  - NEVER use em dashes (—) or long dashes. Use a comma, period, or new line.\n"
    "  - NEVER place two or more emojis in a row. Use at most ONE emoji at a time, "
    "separated by words. (e.g. `Comment \"INVESTOR\" 👇` is fine; `❤️🏡` is not.)\n"
    "  - NEVER invent, change, shorten, or pluralize the ManyChat CTA keyword. Use the "
    "exact keyword you are given."
)

_EMOJI = (
    "[\U0001F300-\U0001FAFF\U00002600-\U000026FF\U00002700-\U000027BF"
    "\U0001F1E6-\U0001F1FF\U00002190-\U000021FF\U00002B00-\U00002BFF"
    "\U0001F000-\U0001F0FF]"
    "[\U0001F3FB-\U0001F3FF]?️?"
)
_GRAPHEME = f"(?:{_EMOJI}(?:‍{_EMOJI})*)"
_EMOJI_RUN = re.compile(f"({_GRAPHEME})(?:\\s*{_GRAPHEME})+")


def _sanitize(text: str) -> str:
    """Mechanically enforce the style rules the model may ignore:
    strip em dashes and collapse any run of consecutive emojis to the first."""
    text = re.sub(r"\s*[—―]\s*", ", ", text)   # em dash / horizontal bar -> comma
    text = re.sub(r",\s*,", ",", text)           # tidy any doubled commas
    text = _EMOJI_RUN.sub(lambda m: m.group(1), text)  # emoji run -> first emoji
    return text.strip()

PLATFORM_STYLES = {
    "instagram": "conversational, emoji-forward, punchy hook first line, 125–200 words, hashtag block at end",
    "facebook":  "warm and community-minded, 150–250 words, light on hashtags",
    "tiktok":    "punchy hook as first line, high energy, 80–120 words, a few hashtags",
    "linkedin":  "professional but warm, reframe the lesson as insight, 150–200 words, few hashtags",
    "youtube":   "description-style; first two sentences must stand alone in search; 150–200 words",
}


def _load_file(ref: str) -> str:
    """Load a config-referenced file (relative to repo root), or '' if missing."""
    if not ref:
        return ""
    p = (ROOT / ref) if not Path(ref).is_absolute() else Path(ref)
    return p.read_text() if p.exists() else ""


def _cta_rules(client: dict, platforms: list, keyword: str = "") -> str:
    """Build per-platform CTA instructions from the client's cta config.

    `keyword` is the ManyChat keyword chosen for THIS post. The model must use it
    exactly and never invent its own.
    """
    cta = client.get("cta", {})
    manychat = set(cta.get("manychat_platforms", []))
    link_platforms = set(cta.get("link_platforms", []))
    kw = (keyword or "").strip() or cta.get("default_keyword") or client.get("brand", {}).get("cta_keyword", "")
    book_link = cta.get("book_link") or client.get("brand", {}).get("link_in_bio", "")

    lines = []
    for p in platforms:
        if p in manychat:
            lines.append(
                f"  {p}: END with a comment-keyword CTA using EXACTLY this keyword: "
                f"\"{kw}\" (e.g. `Comment \"{kw}\" 👇`). This keyword triggers a ManyChat "
                f"automation, so do NOT invent, change, shorten, translate, or pluralize it. "
                f"Do NOT include a raw link."
            )
        elif p in link_platforms:
            lines.append(
                f"  {p}: ManyChat does NOT run here, so do NOT say 'comment a word'. "
                f"END with a relevant invitation AND the booking link: {book_link}"
            )
        else:
            lines.append(f"  {p}: end with a clear, post-relevant call to action.")
    return "\n".join(lines)


def _content_blocks(text_prompt: str, frames: list = None) -> list:
    """Assemble a user-message content array with optional vision frames."""
    blocks = []
    for fr in (frames or []):
        blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": fr["media_type"], "data": fr["data"]},
        })
    blocks.append({"type": "text", "text": text_prompt})
    return blocks


def _system_prompt(client: dict) -> str:
    """The authoritative brand voice. Sent as the API system prompt so the model
    treats it as binding instruction, not just content to consider."""
    brand = client["brand"]
    ctx = _load_file(brand.get("context_file"))
    examples = _load_file(brand.get("examples_file"))

    parts = [
        f"You are the social media copywriter for {brand['name']}.",
        f"You write in this brand's voice and never break character.",
        "",
        f"BRAND VOICE: {brand['voice']}",
        f"TAGLINE: {brand['tagline']}",
        "",
        "HARD RULES (never break these):",
        *[f"  - {r}" for r in brand["hard_rules"]],
        "",
        STYLE_RULES,
    ]
    if ctx:
        parts += ["", "BRAND GUIDELINES & CONTEXT:", ctx]
    if examples:
        parts += [
            "",
            "APPROVED EXAMPLES — study these closely and match their voice, structure, "
            "rhythm, emoji use and CTA style. Write FRESH copy that sounds like them; "
            "never copy verbatim.",
            examples,
        ]
    return "\n".join(parts)


def _system_blocks(client: dict) -> list:
    """System prompt as a cacheable block. The brand store is identical across
    calls, so prompt caching avoids re-billing those input tokens within ~5 min."""
    return [{
        "type": "text",
        "text": _system_prompt(client),
        "cache_control": {"type": "ephemeral"},
    }]


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return raw


# Captions are multi-line and full of quotes/emojis/hashtags, which routinely
# break strict JSON. We have the model delimit each caption with a sentinel line
# instead, then split on it — robust to any caption content.
_SECTION_RE = re.compile(r"^@@@\s*([A-Za-z]+)\s*@@@\s*$", re.MULTILINE)

_FORMAT_INSTRUCTIONS = (
    "Format your reply as plain text (NOT JSON). Before each platform's caption, "
    "put a line containing exactly `@@@platform@@@` (lowercase platform name). "
    "Example:\n@@@instagram@@@\n<caption>\n@@@facebook@@@\n<caption>\n"
    "No other commentary."
)


def _parse_sections(text: str, platforms: list) -> dict:
    """Split a `@@@platform@@@`-delimited reply into {platform: caption}.

    Falls back to JSON if no sentinels are present (older-style replies).
    """
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        return json.loads(_strip_fences(text))
    out = {}
    for i, m in enumerate(matches):
        name = m.group(1).lower()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[name] = text[m.end():end].strip()
    # keep only requested platforms (ignore any stray sections)
    return {p: out[p] for p in platforms if p in out} or out


def generate_captions(client: dict, transcript: str, kind: str, platforms: list,
                      frames: list = None, extra_context: str = "", cta_keyword: str = "") -> dict:
    """Return {platform: caption_text}.

    Args:
        client:        Parsed config/clients/<slug>.json
        transcript:    Video transcript, or brief description for images
        kind:          'reel' | 'image'
        platforms:     Platforms to generate for
        frames:        Optional list of base64 image dicts (video screenshots) for vision
        extra_context: Optional user-supplied context about the piece
        cta_keyword:   Exact ManyChat keyword to use for this post (never invented)
    """
    style_block = "\n".join(
        f"  {p}: {PLATFORM_STYLES.get(p, 'engaging, on-brand, 100-200 words')}"
        for p in platforms
    )

    prompt = f"""Write captions for this new post.

Content type: {kind}
{f'Creator-supplied context: {extra_context}' if extra_context else ''}
Transcript / description:
{transcript or '(none, rely on the attached frames and context)'}
{'Attached: frames sampled from the video, use what you SEE for added detail.' if frames else ''}

Write a caption for each platform. Match these per-platform styles:
{style_block}

CTA rules (follow exactly, this matters):
{_cta_rules(client, platforms, cta_keyword)}

Make every CTA specific to THIS post's topic, and keep the brand voice from the
system instructions and approved examples. Obey the STYLE RULES.

Platforms to write for: {', '.join(platforms)}.
{_FORMAT_INSTRUCTIONS}"""

    api = anthropic.Anthropic()
    message = api.messages.create(
        model=_model(client, "caption"),
        max_tokens=2000,
        system=_system_blocks(client),
        messages=[{"role": "user", "content": _content_blocks(prompt, frames)}],
    )
    caps = _parse_sections(message.content[0].text, platforms)
    return {p: _sanitize(t) for p, t in caps.items()}


def revise_caption(client: dict, platform: str, current_text: str, feedback: str,
                   context: str = "", cta_keyword: str = "") -> str:
    """Revise a single caption based on quick user feedback. Returns plain text."""
    style = PLATFORM_STYLES.get(platform, "engaging, on-brand, 100-200 words")
    prompt = f"""Revise this {platform} caption, keeping the brand voice from the
system instructions and approved examples. Obey the STYLE RULES.

Platform style: {style}
CTA rules:
{_cta_rules(client, [platform], cta_keyword)}
{f'Content context: {context}' if context else ''}

Current caption:
{current_text}

Requested change: {feedback}

Return ONLY the revised caption text, no quotes, no markdown, no explanation."""

    api = anthropic.Anthropic()
    message = api.messages.create(
        model=_model(client, "revise"), max_tokens=1000,
        system=_system_blocks(client),
        messages=[{"role": "user", "content": prompt}],
    )
    return _sanitize(message.content[0].text.strip())


def revise_all(client: dict, captions: dict, feedback: str, context: str = "", cta_keyword: str = "") -> dict:
    """Apply one piece of feedback to ALL captions in a single API call.

    Returns an updated {platform: caption_text} dict (same keys as input).
    """
    platforms = list(captions.keys())
    current = "\n".join(f"@@@{p}@@@\n{t}" for p, t in captions.items())
    prompt = f"""Here are the current captions (each preceded by its @@@platform@@@ marker):
{current}

Apply this change to EVERY caption, keeping each platform's style, CTA rules, the
brand voice from the system instructions and approved examples, and the STYLE RULES:
{_cta_rules(client, platforms, cta_keyword)}

Requested change (applies to all platforms): {feedback}
{f'Content context: {context}' if context else ''}

Platforms: {', '.join(platforms)}.
{_FORMAT_INSTRUCTIONS}"""

    api = anthropic.Anthropic()
    message = api.messages.create(
        model=_model(client, "revise"), max_tokens=2000,
        system=_system_blocks(client),
        messages=[{"role": "user", "content": prompt}],
    )
    caps = _parse_sections(message.content[0].text, platforms)
    return {p: _sanitize(t) for p, t in caps.items()}
