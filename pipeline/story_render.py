"""story_render.py — burn a light, native-style text overlay onto real story media.

Deliberately NOT a flyer: no brand card, no pill. Just the real photo/clip
cover-fit to 1080x1920 with a subtle scrim for legibility and a clean line of
text in the brand's display font.

Design choices (from Deba's brand + feedback):
  - Text uses the client's brand display font (Georgia Bold), not a generic sans.
  - No emojis (they don't render reliably with a TTF) — stripped before drawing.
  - Text sits in the TOP third, leaving the middle/bottom clear for the
    interactive sticker Deba adds in-app.

Text is drawn once with Pillow (a transparent 1080x1920 PNG) and composited onto
photos directly and onto videos via ffmpeg's `overlay` filter (works on any
ffmpeg build, unlike `drawtext` which needs libfreetype).
"""
import re
import subprocess
import tempfile
import textwrap
from pathlib import Path

W, H = 1080, 1920

_FONT_DIRS = [
    Path("/System/Library/Fonts"), Path("/System/Library/Fonts/Supplemental"),
    Path("/Library/Fonts"), Path.home() / "Library/Fonts",
    Path("C:/Windows/Fonts"), Path("/usr/share/fonts"), Path("/usr/local/share/fonts"),
]
_EXTS = (".ttf", ".ttc", ".otf")

# Strip emoji / pictographs (they render as tofu boxes with a normal TTF).
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF\U00002B00-\U00002BFF\U0001F000-\U0001F0FF️‍]"
)


def _strip_emoji(text):
    return re.sub(r"\s{2,}", " ", _EMOJI_RE.sub("", text or "")).strip()


def _find_font_file(name):
    norm = name.lower().replace(" ", "").replace("-", "")
    for d in _FONT_DIRS:
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if f.suffix.lower() in _EXTS and f.stem.lower().replace(" ", "").replace("-", "") == norm:
                return str(f)
    return None


def resolve_font(name=None):
    """Find a TTF for the brand display font, with sensible fallbacks."""
    candidates = [name]
    if name and "bold" not in name.lower():
        candidates.append(name + " Bold")
    candidates += ["Georgia Bold", "Georgia", "LiberationSerif-Bold", "Arial Bold", "DejaVuSans-Bold"]
    for c in candidates:
        if not c:
            continue
        p = _find_font_file(c)
        if p:
            return p
    return None


def _overlay_layer(overlay, font_name=None):
    """Transparent 1080x1920 RGBA: top scrim + brand-font text in the top third."""
    from PIL import Image, ImageDraw, ImageFont

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # top gradient scrim (darkest at the very top, fading down) for legibility
    for i in range(540):
        d.line([(0, i), (W, i)], fill=(0, 0, 0, int(150 * (540 - i) / 540)))

    overlay = _strip_emoji(overlay)
    if overlay:
        fp = resolve_font(font_name)
        font = ImageFont.truetype(fp, 76) if fp else ImageFont.load_default()
        lines = textwrap.wrap(overlay, width=20) or [overlay]
        line_h = (font.getbbox("Ay")[3] - font.getbbox("Ay")[1]) + 20
        y = 180  # top third
        for ln in lines:
            w = d.textlength(ln, font=font)
            x = (W - w) / 2
            d.text((x + 3, y + 3), ln, font=font, fill=(0, 0, 0, 160))   # shadow
            d.text((x, y), ln, font=font, fill=(255, 255, 255, 255))
            y += line_h
    return layer


def render_photo_story(image_path, overlay, out_path, font_name=None):
    """Cover-crop a photo to 1080x1920 and composite the overlay."""
    from PIL import Image

    img = Image.open(image_path).convert("RGB")
    scale = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)))
    left, top = (img.width - W) // 2, (img.height - H) // 2
    img = img.crop((left, top, left + W, top + H)).convert("RGBA")
    img.alpha_composite(_overlay_layer(overlay, font_name))
    img.convert("RGB").save(out_path, quality=92)
    return str(out_path)


def render_video_story(video_path, overlay, out_path, font_name=None):
    """Cover-crop a clip to 1080x1920 and composite the overlay PNG (ffmpeg overlay)."""
    png = tempfile.mktemp(suffix=".png")
    _overlay_layer(overlay, font_name).save(png)
    try:
        filt = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H}[v];[v][1:v]overlay=0:0")
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", str(video_path), "-i", png,
             "-filter_complex", filt, "-c:a", "copy", "-c:v", "libx264",
             "-pix_fmt", "yuv420p", str(out_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg story render failed:\n{r.stderr[-400:]}")
    finally:
        Path(png).unlink(missing_ok=True)
    return str(out_path)


def render_story(media_path, overlay, out_path, kind, font_name=None):
    """Render an authentic story for a photo or video. kind: 'image' | 'reel'."""
    if kind == "image":
        return render_photo_story(media_path, overlay, out_path, font_name)
    return render_video_story(media_path, overlay, out_path, font_name)
