"""caption_gen.py — generate platform-specific captions via Claude API.

Pulls authentic brand voice from the client's config plus an optional long-form
context file (brand.context_file). Can use video frames for visual grounding and
applies platform-aware CTAs (ManyChat comment-keyword vs. real booking link).
"""
import json
from pathlib import Path

import anthropic

MODEL = "claude-haiku-4-5-20251001"

# Repo root = two levels up from this file (pipeline/ -> repo)
ROOT = Path(__file__).resolve().parent.parent

PLATFORM_STYLES = {
    "instagram": "conversational, emoji-forward, punchy hook first line, 125–200 words, hashtag block at end",
    "facebook":  "warm and community-minded, 150–250 words, light on hashtags",
    "tiktok":    "punchy hook as first line, high energy, 80–120 words, a few hashtags",
    "linkedin":  "professional but warm, reframe the lesson as insight, 150–200 words, few hashtags",
    "youtube":   "description-style; first two sentences must stand alone in search; 150–200 words",
}


def _load_brand_context(client: dict) -> str:
    """Return the long-form brand context file contents, or '' if none."""
    ref = client.get("brand", {}).get("context_file")
    if not ref:
        return ""
    p = (ROOT / ref) if not Path(ref).is_absolute() else Path(ref)
    return p.read_text() if p.exists() else ""


def _cta_rules(client: dict, platforms: list) -> str:
    """Build per-platform CTA instructions from the client's cta config."""
    cta = client.get("cta", {})
    manychat = set(cta.get("manychat_platforms", []))
    link_platforms = set(cta.get("link_platforms", []))
    keyword = cta.get("default_keyword") or client.get("brand", {}).get("cta_keyword", "")
    book_link = cta.get("book_link") or client.get("brand", {}).get("link_in_bio", "")

    lines = []
    for p in platforms:
        if p in manychat:
            lines.append(
                f"  {p}: END with a comment-keyword CTA like `Comment \"{keyword}\" 👇`. "
                f"ManyChat auto-DMs commenters. Pick a SHORT keyword relevant to THIS post "
                f"(e.g. START, INFO, ME) or use \"{keyword}\". Do NOT include a raw link."
            )
        elif p in link_platforms:
            lines.append(
                f"  {p}: ManyChat does NOT run here — do NOT say 'comment a word'. "
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


def _brand_header(client: dict) -> str:
    brand = client["brand"]
    ctx = _load_brand_context(client)
    return f"""You are writing social media captions for {brand['name']}.

Brand voice: {brand['voice']}
Tagline: {brand['tagline']}
Hard rules (never break these):
{chr(10).join('  - ' + r for r in brand['hard_rules'])}

EXTENDED BRAND CONTEXT:
{ctx if ctx else '(none provided)'}"""


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return raw


def generate_captions(client: dict, transcript: str, kind: str, platforms: list,
                      frames: list = None, extra_context: str = "") -> dict:
    """Return {platform: caption_text}.

    Args:
        client:        Parsed config/clients/<slug>.json
        transcript:    Video transcript, or brief description for images
        kind:          'reel' | 'image'
        platforms:     Platforms to generate for
        frames:        Optional list of base64 image dicts (video screenshots) for vision
        extra_context: Optional user-supplied context about the piece
    """
    style_block = "\n".join(
        f"  {p}: {PLATFORM_STYLES.get(p, 'engaging, on-brand, 100–200 words')}"
        for p in platforms
    )

    prompt = f"""{_brand_header(client)}

Content type: {kind}
{f'Creator-supplied context: {extra_context}' if extra_context else ''}
Transcript / description:
{transcript or '(none — rely on the attached frames and context)'}
{'Attached: frames sampled from the video — use what you SEE for added detail.' if frames else ''}

Write a caption for each platform. Match these per-platform styles:
{style_block}

CTA rules (follow exactly — this matters):
{_cta_rules(client, platforms)}

Make every CTA specific to THIS post's topic.

Return ONLY a valid JSON object — no markdown fences, no commentary. Keys are the
platform names ({', '.join(platforms)}); values are the caption strings."""

    api = anthropic.Anthropic()
    message = api.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": _content_blocks(prompt, frames)}],
    )
    return json.loads(_strip_fences(message.content[0].text))


def revise_caption(client: dict, platform: str, current_text: str, feedback: str, context: str = "") -> str:
    """Revise a single caption based on quick user feedback. Returns plain text."""
    style = PLATFORM_STYLES.get(platform, "engaging, on-brand, 100–200 words")
    prompt = f"""{_brand_header(client)}

Revise this {platform} caption. Platform style: {style}
CTA rules:
{_cta_rules(client, [platform])}
{f'Content context: {context}' if context else ''}

Current caption:
{current_text}

Requested change: {feedback}

Return ONLY the revised caption text — no quotes, no markdown, no explanation."""

    api = anthropic.Anthropic()
    message = api.messages.create(
        model=MODEL, max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def revise_all(client: dict, captions: dict, feedback: str, context: str = "") -> dict:
    """Apply one piece of feedback to ALL captions in a single API call.

    Returns an updated {platform: caption_text} dict (same keys as input).
    """
    platforms = list(captions.keys())
    current = json.dumps(captions, indent=2)
    prompt = f"""{_brand_header(client)}

Here are the current captions as JSON:
{current}

Apply this change to EVERY caption, keeping each platform's style and CTA rules:
{_cta_rules(client, platforms)}

Requested change (applies to all platforms): {feedback}
{f'Content context: {context}' if context else ''}

Return ONLY a valid JSON object with the same keys ({', '.join(platforms)}) and the
revised caption strings — no markdown fences, no commentary."""

    api = anthropic.Anthropic()
    message = api.messages.create(
        model=MODEL, max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(_strip_fences(message.content[0].text))
