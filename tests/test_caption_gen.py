"""Unit tests for caption_gen — all pure, no API calls."""
import caption_gen as cg


# ---- _sanitize: style rules ----

def test_sanitize_strips_em_dashes():
    assert "—" not in cg._sanitize("The first house — but it changes your life.")
    assert cg._sanitize("a — b") == "a, b"


def test_sanitize_keeps_number_ranges_endash():
    # en dash in ranges is not an em dash; leave it
    assert "$340K–$310K" in cg._sanitize("Range $340K–$310K stays")


def test_sanitize_collapses_emoji_runs():
    assert cg._sanitize("results ❤️🏡") == "results ❤️"
    assert cg._sanitize("✨🏡💰 energy") == "✨ energy"


def test_sanitize_keeps_single_separated_emojis():
    txt = 'Know your ARV 🏡 before you buy. Comment "FLIP" 👇'
    assert cg._sanitize(txt) == txt


# ---- _cta_rules: exact keyword, manychat vs link ----

def test_cta_rules_uses_exact_keyword(deba_config):
    rules = cg._cta_rules(deba_config, ["instagram"], keyword="BLUEPRINT")
    assert 'BLUEPRINT' in rules
    assert "not invent" in rules.lower()  # forbids inventing a keyword


def test_cta_rules_link_platform_gets_booking_link(deba_config):
    rules = cg._cta_rules(deba_config, ["linkedin"], keyword="BLUEPRINT")
    assert "calendly.com/bookdeba" in rules
    assert "BLUEPRINT" not in rules  # link platforms don't use the keyword


def test_cta_rules_falls_back_to_default_keyword(deba_config):
    rules = cg._cta_rules(deba_config, ["instagram"], keyword="")
    assert deba_config["cta"]["default_keyword"] in rules


# ---- _parse_sections: robust caption splitting ----

def test_parse_sections_handles_quotes_emojis_newlines():
    raw = '@@@instagram@@@\nLine one "quoted" 🏡\n\n#tags\n@@@linkedin@@@\nPro copy.'
    out = cg._parse_sections(raw, ["instagram", "linkedin"])
    assert set(out) == {"instagram", "linkedin"}
    assert out["instagram"].endswith("#tags")
    assert "quoted" in out["instagram"]


def test_parse_sections_only_requested_platforms():
    raw = "@@@instagram@@@\nA\n@@@tiktok@@@\nB"
    out = cg._parse_sections(raw, ["instagram"])
    assert list(out) == ["instagram"]


# ---- system prompt assembly ----

def test_system_prompt_includes_brand_store(deba_config):
    sp = cg._system_prompt(deba_config)
    assert "HARD RULES" in sp
    assert "APPROVED EXAMPLES" in sp          # examples file loaded
    assert "never promise specific ROI" in sp  # hard rule present


def test_system_blocks_are_cacheable(deba_config):
    blocks = cg._system_blocks(deba_config)
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}


def test_model_resolution(deba_config):
    assert cg._model(deba_config, "caption") == "claude-sonnet-4-6"
    assert cg._model(deba_config, "revise") == "claude-haiku-4-5-20251001"
    assert cg._model({}, "caption") == cg.DEFAULT_MODELS["caption"]
