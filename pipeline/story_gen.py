"""story_gen.py — AI text for authentic IG Stories.

Deba wants stories to feel real, not like flyer graphics. So this writes a SHORT,
casual overlay line (the kind someone types on their own story) plus an interactive
sticker prompt (poll or question) in the brand voice, for the day's theme.
"""
import re

import anthropic
from caption_gen import _system_blocks, _model, _sanitize

_SECTION_RE = re.compile(r"^@@@\s*(overlay|sticker)\s*@@@\s*$", re.IGNORECASE | re.MULTILINE)


def _parse(text):
    out = {}
    matches = list(_SECTION_RE.finditer(text))
    for i, m in enumerate(matches):
        key = m.group(1).lower()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[key] = text[m.end():end].strip()
    return out


def generate_story(client, theme="", brief=""):
    """Return {'overlay': str, 'sticker': str} for an authentic IG story.

    overlay = a few words to lay over the photo/clip (casual, real, not salesy).
    sticker = the interactive sticker prompt Deba taps in-app (poll/question).
    """
    prompt = f"""Write text for ONE authentic Instagram Story for this brand.

This is a real, in-the-moment story, NOT a flyer or ad. It sits over a candid
photo or short clip the creator took.
{f'Theme of the day: {theme}' if theme else ''}
{f'What the story is about: {brief}' if brief else ''}

Give me two things:
1) overlay: a SHORT line (max ~8 words) to lay over the media. Casual and human,
   like something you'd actually type on your own story. No hashtags, no link, and
   NO emojis (they don't render on the card).
2) sticker: ONE interactive sticker prompt for Deba to tap in-app — either a poll
   ("This or that?" with two options) or a question-box prompt. Keep it natural and
   on-theme. Prefix it with "Poll:" or "Question:".

Format exactly:
@@@overlay@@@
<line>
@@@sticker@@@
<prompt>"""

    api = anthropic.Anthropic()
    msg = api.messages.create(
        model=_model(client, "revise"),  # short + cheap
        max_tokens=400,
        system=_system_blocks(client),
        messages=[{"role": "user", "content": prompt}],
    )
    parsed = _parse(msg.content[0].text)
    return {
        "overlay": _sanitize(parsed.get("overlay", "")),
        "sticker": _sanitize(parsed.get("sticker", "")),
    }
