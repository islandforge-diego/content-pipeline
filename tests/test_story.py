"""Tests for story text parsing, rendering, and Buffer story input."""
import subprocess
import tempfile
from pathlib import Path

import pytest

import story_gen
import story_render
import buffer_api


def test_story_parse_overlay_and_sticker():
    raw = "@@@overlay@@@\nfirst deal, done 🏡\n@@@sticker@@@\nPoll: Flip or hold?"
    out = story_gen._parse(raw)
    assert out["overlay"] == "first deal, done 🏡"
    assert out["sticker"].startswith("Poll:")


def test_story_font_available():
    # at least the fallback path resolves to None without raising
    fp = story_render._font_path()
    assert fp is None or Path(fp).exists()


def test_overlay_layer_is_story_sized():
    layer = story_render._overlay_layer("she said yes")
    assert layer.size == (1080, 1920)
    assert layer.mode == "RGBA"


def test_story_reminder_input_is_notification_story():
    # exercise the payload shape create_story_reminder builds (without calling Buffer)
    # by checking the metadata/scheduling contract via a tiny monkeypatch
    captured = {}

    def fake_graphql(query, variables, token):
        captured.update(variables["input"])
        return {"createPost": {"__typename": "PostActionSuccess", "post": {"id": "x"}}}

    orig = buffer_api._graphql
    buffer_api._graphql = fake_graphql
    try:
        buffer_api.create_story_reminder("ch1", "https://x/s.jpg", "2026-07-01T07:00:00-05:00",
                                         "Poll: this or that?", "image", "tok")
    finally:
        buffer_api._graphql = orig
    assert captured["schedulingType"] == "notification"
    assert captured["metadata"]["instagram"]["type"] == "story"
    assert captured["assets"][0]["image"]["url"].endswith("s.jpg")
    assert captured["text"] == "Poll: this or that?"


@pytest.mark.skipif(__import__("shutil").which("ffmpeg") is None, reason="ffmpeg not installed")
def test_render_video_story_outputs_vertical():
    vid = Path(tempfile.mktemp(suffix=".mp4"))
    out = Path(tempfile.mktemp(suffix=".mp4"))
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=640x480:rate=15",
                    "-pix_fmt", "yuv420p", str(vid)], capture_output=True)
    try:
        story_render.render_video_story(str(vid), "hello", str(out))
        dims = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                               "-show_entries", "stream=width,height", "-of", "csv=p=0", str(out)],
                              capture_output=True, text=True).stdout.strip()
        assert dims == "1080,1920"
    finally:
        vid.unlink(missing_ok=True); out.unlink(missing_ok=True)
