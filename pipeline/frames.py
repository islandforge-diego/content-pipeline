"""frames.py — pull a few screenshots from a video for visual caption context.

Uses ffmpeg to grab N evenly-spaced frames, downscaled small, and returns them
as base64 JPEGs ready for Claude's vision input. Kept deliberately lean (few
small frames) to keep token cost low.
"""
import base64
import json
import subprocess
import tempfile
from pathlib import Path


def _duration(video_path: str) -> float:
    """Return video duration in seconds (0.0 if it can't be probed)."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", str(video_path)],
            capture_output=True, text=True,
        )
        return float(json.loads(out.stdout)["format"]["duration"])
    except Exception:
        return 0.0


def extract_frames(video_path: str, count: int = 3, width: int = 512) -> list:
    """Return up to `count` base64 JPEG frames evenly spaced through the video.

    Each item: {"media_type": "image/jpeg", "data": "<base64>"}.
    Returns [] if ffmpeg/ffprobe are unavailable or extraction fails.
    """
    dur = _duration(video_path)
    # Evenly spaced timestamps; if duration unknown, just grab from the start.
    if dur > 0:
        times = [dur * (i + 1) / (count + 1) for i in range(count)]
    else:
        times = [1.0 * i for i in range(count)]

    frames = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, t in enumerate(times):
            out = Path(tmp) / f"f{i}.jpg"
            r = subprocess.run(
                ["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(video_path),
                 "-frames:v", "1", "-vf", f"scale={width}:-1", "-q:v", "5", str(out)],
                capture_output=True, text=True,
            )
            if r.returncode == 0 and out.exists():
                frames.append({
                    "media_type": "image/jpeg",
                    "data": base64.b64encode(out.read_bytes()).decode("ascii"),
                })
    return frames
