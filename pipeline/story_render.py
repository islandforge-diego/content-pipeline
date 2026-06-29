"""story_render.py — burn a light, native-style text overlay onto real story media.

Deliberately NOT a flyer: no brand card, no pill. Just the real photo/clip
cover-fit to 1080x1920 with a subtle bottom scrim for legibility and a clean
bold-sans line low on the frame, the way someone types text on their own story.

The text overlay is drawn once with Pillow (a transparent 1080x1920 PNG) and
composited onto photos directly and onto videos via ffmpeg's `overlay` filter
(works on any ffmpeg build, unlike `drawtext` which needs libfreetype).
"""
import subprocess
import tempfile
import textwrap
from pathlib import Path

W, H = 1080, 1920

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Helvetica.ttc",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _font_path():
    for p in _FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def _overlay_layer(overlay):
    """A transparent 1080x1920 RGBA layer: bottom scrim + native-style text line."""
    from PIL import Image, ImageDraw, ImageFont

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in range(520):  # subtle bottom gradient scrim (not a card)
        d.line([(0, H - 520 + i), (W, H - 520 + i)], fill=(0, 0, 0, int(150 * i / 520)))

    if overlay:
        fp = _font_path()
        font = ImageFont.truetype(fp, 72) if fp else ImageFont.load_default()
        lines = textwrap.wrap(overlay, width=22) or [overlay]
        line_h = (font.getbbox("Ay")[3] - font.getbbox("Ay")[1]) + 18
        y = H - 230 - max(0, len(lines) - 1) * line_h
        for ln in lines:
            w = d.textlength(ln, font=font)
            x = (W - w) / 2
            d.text((x + 3, y + 3), ln, font=font, fill=(0, 0, 0, 160))   # shadow
            d.text((x, y), ln, font=font, fill=(255, 255, 255, 255))
            y += line_h
    return layer


def render_photo_story(image_path, overlay, out_path):
    """Cover-crop a photo to 1080x1920 and composite the overlay."""
    from PIL import Image

    img = Image.open(image_path).convert("RGB")
    scale = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)))
    left, top = (img.width - W) // 2, (img.height - H) // 2
    img = img.crop((left, top, left + W, top + H)).convert("RGBA")
    img.alpha_composite(_overlay_layer(overlay))
    img.convert("RGB").save(out_path, quality=92)
    return str(out_path)


def render_video_story(video_path, overlay, out_path):
    """Cover-crop a clip to 1080x1920 and composite the overlay PNG (ffmpeg overlay)."""
    png = tempfile.mktemp(suffix=".png")
    _overlay_layer(overlay).save(png)
    try:
        filt = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H}[v];[v][1:v]overlay=0:0")
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", str(video_path), "-i", png,
             "-filter_complex", filt, "-c:a", "copy", "-c:v", "libx264",
             "-pix_fmt", "yuv420p", str(out_path)],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg story render failed:\n{r.stderr[-400:]}")
    finally:
        Path(png).unlink(missing_ok=True)
    return str(out_path)


def render_story(media_path, overlay, out_path, kind):
    """Render an authentic story for a photo or video. kind: 'image' | 'reel'."""
    if kind == "image":
        return render_photo_story(media_path, overlay, out_path)
    return render_video_story(media_path, overlay, out_path)
