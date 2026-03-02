"""Tests for the API reference tools and search helpers.

These tests import from server.server, which attempts a TCP ping to Ableton
at module load time. That call is non-fatal (logs a warning and continues),
so tests run fine without Ableton.
"""

import json

from server.server import (
    _stem,
    _tokenize,
    _stems_close,
    _match,
    _CLASSES,
    _ENUMS,
    api,
    search_api,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


class TestStem:
    def test_no_suffix(self):
        assert _stem("warp") == "warp"
        assert _stem("tempo") == "tempo"

    def test_strip_ization(self):
        assert _stem("quantization") == "quant"

    def test_strip_ing(self):
        assert _stem("playing") == "play"
        assert _stem("warping") == "warp"

    def test_strip_ed(self):
        assert _stem("muted") == "mut"

    def test_strip_ized(self):
        assert _stem("quantized") == "quant"

    def test_strip_s(self):
        assert _stem("loops") == "loop"
        assert _stem("tracks") == "track"

    def test_short_words_unchanged(self):
        # Words too short for suffix stripping should pass through
        assert _stem("in") == "in"
        assert _stem("on") == "on"


class TestTokenize:
    def test_simple(self):
        assert _tokenize("loop_start") == ["loop", "start"]

    def test_spaces(self):
        assert _tokenize("loop start") == ["loop", "start"]

    def test_mixed(self):
        assert _tokenize("Audio warp_mode (0=Beats)") == [
            "audio", "warp", "mode", "0", "beats"
        ]

    def test_empty(self):
        assert _tokenize("") == []


class TestStemsClose:
    def test_exact_match(self):
        assert _stems_close("warp", "warp")

    def test_prefix_match(self):
        # "quant" (5) vs "quantize" (8): 5/8 = 0.625 >= 0.6
        assert _stems_close("quant", "quantize")

    def test_rejects_short_prefix(self):
        # "none" (4) vs "nonexistent" (11): 4/11 = 0.36 < 0.6
        assert not _stems_close("none", "nonexistent")

    def test_symmetric(self):
        assert _stems_close("quant", "quantize") == _stems_close("quantize", "quant")

    def test_no_overlap(self):
        assert not _stems_close("warp", "tempo")


class TestMatch:
    def test_single_word(self):
        assert _match(["tempo"], "song tempo bpm")

    def test_single_word_miss(self):
        assert not _match(["tempo"], "volume panning sends")

    def test_multi_word_all_present(self):
        assert _match(["loop", "start"], "loop_start in beats")

    def test_multi_word_partial_miss(self):
        assert not _match(["loop", "start"], "loop_end in beats")

    def test_stemmed_match(self):
        # "quantize" stem matches "quant" stem of "quantization"
        stems = [_stem("quantize")]
        assert _match(stems, "clip_trigger_quantization")

    def test_underscore_equals_space(self):
        assert _match([_stem("warp"), _stem("mode")], "warp_mode")


# ── Data integrity ───────────────────────────────────────────────────────────


class TestDataIntegrity:
    def test_classes_loaded(self):
        assert len(_CLASSES) >= 11

    def test_enums_loaded(self):
        assert len(_ENUMS) >= 1

    def test_every_class_has_required_keys(self):
        for name, cls in _CLASSES.items():
            assert "description" in cls, f"{name} missing description"
            assert "access" in cls, f"{name} missing access"

    def test_every_property_has_required_keys(self):
        for cls_name, cls in _CLASSES.items():
            for prop_name, prop in cls.get("properties", {}).items():
                assert "type" in prop, f"{cls_name}.{prop_name} missing type"
                assert "access" in prop, f"{cls_name}.{prop_name} missing access"
                assert prop["access"] in ("r", "rw"), (
                    f"{cls_name}.{prop_name} has invalid access: {prop['access']}"
                )
                assert "description" in prop, f"{cls_name}.{prop_name} missing description"

    def test_every_method_has_required_keys(self):
        for cls_name, cls in _CLASSES.items():
            for method_name, method in cls.get("methods", {}).items():
                assert "signature" in method, f"{cls_name}.{method_name} missing signature"
                assert "description" in method, f"{cls_name}.{method_name} missing description"

    def test_expected_classes_present(self):
        expected = {"Song", "Track", "Clip", "ClipSlot", "Device",
                    "DeviceParameter", "MixerDevice", "Browser",
                    "BrowserItem", "Scene", "Chain", "Song.View", "DrumPad"}
        assert expected.issubset(_CLASSES.keys())

    def test_enums_have_values(self):
        for enum_name, enum in _ENUMS.items():
            if enum_name == "description":
                continue
            assert "values" in enum, f"enum {enum_name} missing values"
            assert "used_by" in enum, f"enum {enum_name} missing used_by"


# ── api() tool ───────────────────────────────────────────────────────────────


class TestApi:
    def test_no_arg_returns_index(self):
        result = json.loads(api())
        assert "Song" in result
        assert "Track" in result
        for cls in result.values():
            assert "description" in cls
            assert "access" in cls
            # Index should NOT include full properties/methods
            assert "properties" not in cls

    def test_class_lookup(self):
        result = json.loads(api("Song"))
        assert "Song" in result
        assert "properties" in result["Song"]
        assert "methods" in result["Song"]
        assert "tempo" in result["Song"]["properties"]

    def test_case_insensitive(self):
        result_lower = json.loads(api("song"))
        result_upper = json.loads(api("Song"))
        assert result_lower == result_upper

    def test_unknown_class(self):
        result = json.loads(api("FakeClass"))
        assert "error" in result
        assert "available" in result

    def test_dotted_path_property(self):
        result = json.loads(api("Song.tempo"))
        key = "Song.tempo"
        assert key in result
        assert result[key]["kind"] == "property"
        assert result[key]["type"] == "float"

    def test_dotted_path_method(self):
        result = json.loads(api("Clip.quantize"))
        key = "Clip.quantize"
        assert key in result
        assert result[key]["kind"] == "method"
        assert "signature" in result[key]

    def test_dotted_path_case_insensitive(self):
        result = json.loads(api("song.TEMPO"))
        assert "Song.tempo" in result

    def test_dotted_path_unknown_member(self):
        result = json.loads(api("Song.nonexistent"))
        assert "error" in result
        assert "members" in result

    def test_dotted_class_name_song_view(self):
        result = json.loads(api("Song.View"))
        assert "Song.View" in result
        assert "properties" in result["Song.View"]
        assert "selected_track" in result["Song.View"]["properties"]

    def test_enums(self):
        result = json.loads(api("enums"))
        assert "warp_mode" in result
        assert "launch_mode" in result
        assert "values" in result["warp_mode"]


# ── search_api() tool ───────────────────────────────────────────────────────


class TestSearchApi:
    def test_tempo(self):
        result = json.loads(search_api("tempo"))
        assert "_summary" in result
        # Should find Song.tempo at minimum
        assert "Song" in result
        assert "tempo" in result["Song"].get("properties", {})

    def test_quantize_finds_quantization(self):
        result = json.loads(search_api("quantize"))
        # Should find Clip.quantize method
        assert "Clip" in result
        assert "quantize" in result["Clip"].get("methods", {})
        # Should also find Song.clip_trigger_quantization via stemming
        assert "Song" in result
        assert "clip_trigger_quantization" in result["Song"].get("properties", {})

    def test_warp(self):
        result = json.loads(search_api("warp"))
        assert "Clip" in result
        assert "warp_mode" in result["Clip"].get("properties", {})
        assert "warping" in result["Clip"].get("properties", {})

    def test_multi_word_loop_start(self):
        result = json.loads(search_api("loop start"))
        # Should find loop_start but NOT loop_end
        all_props = {}
        for cls in result.values():
            if isinstance(cls, dict) and "properties" in cls:
                all_props.update(cls["properties"])
        assert "loop_start" in all_props
        assert "loop_end" not in all_props

    def test_mute_across_classes(self):
        result = json.loads(search_api("mute"))
        classes_with_mute = [k for k in result if not k.startswith("_")]
        assert len(classes_with_mute) >= 3  # Track, Chain, DrumPad at minimum

    def test_no_results(self):
        result = json.loads(search_api("xyznonexistent"))
        assert "message" in result

    def test_empty_query(self):
        result = json.loads(search_api("   "))
        assert "message" in result

    def test_summary_header(self):
        result = json.loads(search_api("tempo"))
        assert "_summary" in result
        assert "Found" in result["_summary"]

    def test_no_class_flooding(self):
        """Searching 'track' should NOT dump all Track properties."""
        result = json.loads(search_api("track"))
        if "Track" in result:
            track_props = result["Track"].get("properties", {})
            # Should only include members that actually match "track",
            # not every single property on Track
            total_track_props = len(_CLASSES["Track"]["properties"])
            assert len(track_props) < total_track_props

    def test_enum_results(self):
        result = json.loads(search_api("warp"))
        if "_enums" in result:
            assert "warp_mode" in result["_enums"]
