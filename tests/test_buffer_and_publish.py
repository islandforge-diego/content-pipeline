"""Unit tests for buffer_api payload building and publish channel routing."""
import buffer_api
import publish


# ---- buffer_api.build_create_post_input (pure) ----

def test_build_input_has_required_fields():
    p = buffer_api.build_create_post_input("ch1", "hi", "https://x/v.mp4", "2026-06-30T15:00:00-05:00", "reel")
    # the two fields whose absence caused the 0/5 failures
    assert p["schedulingType"] == "automatic"
    assert p["mode"] == "customScheduled"
    assert p["channelId"] == "ch1"
    assert p["dueAt"].startswith("2026-06-30")


def test_build_input_video_vs_image_asset():
    v = buffer_api.build_create_post_input("c", "t", "u", "d", "reel")
    i = buffer_api.build_create_post_input("c", "t", "u", "d", "image")
    assert list(v["assets"][0]) == ["video"]
    assert list(i["assets"][0]) == ["image"]
    assert v["assets"][0]["video"]["url"] == "u"


def test_build_input_draft_flag():
    assert buffer_api.build_create_post_input("c", "t", "u", "d", "reel", as_draft=True)["saveToDraft"] is True
    assert buffer_api.build_create_post_input("c", "t", "u", "d", "reel", as_draft=False)["saveToDraft"] is False


def test_metadata_instagram_reel_has_type_and_feed():
    p = buffer_api.build_create_post_input("c", "t", "u", "d", "reel", platform="instagram")
    assert p["metadata"]["instagram"]["type"] == "reel"
    assert p["metadata"]["instagram"]["shouldShareToFeed"] is True


def test_metadata_facebook_image_is_post():
    p = buffer_api.build_create_post_input("c", "t", "u", "d", "image", platform="facebook")
    assert p["metadata"]["facebook"]["type"] == "post"


def test_metadata_youtube_has_required_fields():
    p = buffer_api.build_create_post_input("c", "Big hook line\nrest", "u", "d", "reel",
                                           platform="youtube", opts={"youtube_category_id": "27"})
    yt = p["metadata"]["youtube"]
    assert yt["title"] == "Big hook line"
    assert yt["categoryId"] == "27"
    # privacy + madeForKids are required to avoid Buffer's UnexpectedError
    assert yt["privacy"] == "public"
    assert yt["madeForKids"] is False


def test_metadata_facebook_video_defaults_to_post():
    p = buffer_api.build_create_post_input("c", "t", "u", "d", "reel", platform="facebook")
    assert p["metadata"]["facebook"]["type"] == "post"  # reels error; default to post


def test_metadata_absent_for_linkedin_tiktok():
    for plat in ("linkedin", "tiktok"):
        p = buffer_api.build_create_post_input("c", "t", "u", "d", "reel", platform=plat)
        assert "metadata" not in p


# ---- publish.target_channels (config-driven routing) ----

def test_target_channels_reel_all_five(deba_config):
    assert publish.target_channels(deba_config, "reel") == \
        deba_config["schedule"]["feed"]["reels_channels"]


def test_target_channels_image_excludes_tiktok_youtube(deba_config):
    chans = publish.target_channels(deba_config, "image")
    assert "tiktok" not in chans and "youtube" not in chans
    assert "instagram" in chans
