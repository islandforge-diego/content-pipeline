"""Config validity, brand-store presence, and ffmpeg frame extraction."""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLIENTS = ROOT / "config" / "clients"

REQUIRED_TOP = ["slug", "display_name", "brand", "buffer", "schedule", "s3", "cta", "models"]


@pytest.mark.parametrize("cfg_path", sorted(CLIENTS.glob("*.json")))
def test_client_config_valid(cfg_path):
    cfg = json.loads(cfg_path.read_text())
    for key in REQUIRED_TOP:
        assert key in cfg, f"{cfg_path.name} missing '{key}'"
    # CTA routing must name platforms
    assert cfg["cta"]["manychat_platforms"]
    assert cfg["cta"]["link_platforms"]


def test_deba_brand_store_files_exist_and_clean(deba_config):
    for ref_key in ("context_file", "examples_file"):
        ref = deba_config["brand"].get(ref_key)
        assert ref, f"deba brand.{ref_key} not set"
        p = ROOT / ref
        assert p.exists(), f"{ref} missing"
        # style rule: brand store must not teach em dashes
        assert "—" not in p.read_text(), f"{ref} contains an em dash"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_extract_frames_from_generated_video():
    import frames
    tmp = Path(tempfile.mktemp(suffix=".mp4"))
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=10",
         "-pix_fmt", "yuv420p", str(tmp)],
        capture_output=True,
    )
    try:
        out = frames.extract_frames(str(tmp), count=3)
        assert len(out) == 3
        assert all(f["media_type"] == "image/jpeg" and f["data"] for f in out)
    finally:
        tmp.unlink(missing_ok=True)
