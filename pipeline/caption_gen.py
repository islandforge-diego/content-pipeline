"""caption_gen.py — generate platform-specific captions via Claude API."""
import json
import anthropic

PLATFORM_STYLES = {
    "instagram": "conversational, emojis welcome, 125–200 words, end with call to action pointing to 'link in bio'",
    "facebook":  "community-focused, slightly longer, 150–250 words, end with the CTA keyword",
    "tiktok":    "punchy hook as first line, high energy, 80–120 words, hashtags are fine",
    "linkedin":  "professional but warm, educational tone, 150–200 words, minimal hashtags",
    "youtube":   "description-style, first two sentences must stand alone in search preview, 150–200 words, include CTA keyword",
}


def generate_captions(client: dict, transcript: str, kind: str, platforms: list) -> dict:
    """Return a dict of {platform: caption_text} for the given platforms.

    Args:
        client:     Parsed config/clients/<slug>.json
        transcript: Video transcript or brief description for images
        kind:       'reel' | 'image'
        platforms:  List of platform names to generate for
    """
    brand = client["brand"]

    platform_block = "\n".join(
        f"  {p}: {PLATFORM_STYLES.get(p, 'engaging, on-brand, 100–200 words')}"
        for p in platforms
    )

    prompt = f"""You are writing social media captions for {brand['name']}.

Brand voice: {brand['voice']}
Tagline: {brand['tagline']}
Hard rules (never break these):
{chr(10).join('  - ' + r for r in brand['hard_rules'])}
CTA keyword: {brand['cta_keyword']}
Link in bio: {brand['link_in_bio']}

Content ({kind}) transcript / description:
{transcript}

Write captions for these platforms using the style notes below:
{platform_block}

Return ONLY a valid JSON object — no markdown fences, no explanation. Keys are platform names, values are caption strings."""

    api = anthropic.Anthropic()
    message = api.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown code fences if the model adds them anyway
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    return json.loads(raw)


def revise_caption(client: dict, platform: str, current_text: str, feedback: str, context: str = "") -> str:
    """Revise a single caption based on quick user feedback. Returns plain text.

    Args:
        client:       Parsed config/clients/<slug>.json
        platform:     Platform name (instagram, facebook, ...)
        current_text: The caption as it stands now
        feedback:     User's instruction (e.g. "make it punchier", "drop the emojis")
        context:      Optional transcript/brief for grounding
    """
    brand = client["brand"]
    style = PLATFORM_STYLES.get(platform, "engaging, on-brand, 100–200 words")

    prompt = f"""Revise this {platform} caption for {brand['name']}.

Brand voice: {brand['voice']}
Hard rules (never break these):
{chr(10).join('  - ' + r for r in brand['hard_rules'])}
CTA keyword: {brand['cta_keyword']}
Link in bio: {brand['link_in_bio']}
Platform style: {style}
{f'Content context: {context}' if context else ''}

Current caption:
{current_text}

Requested change: {feedback}

Return ONLY the revised caption text — no quotes, no markdown, no explanation."""

    api = anthropic.Anthropic()
    message = api.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()
