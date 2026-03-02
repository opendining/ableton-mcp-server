"""Tests for Remote Script pure functions: find_items, find_item, serialize.

These are module-level functions in ableton/__init__.py that don't need
Ableton running. We mock the browser tree with simple objects.
"""

# We can't import from ableton/__init__.py directly because it imports
# _Framework.ControlSurface which only exists inside Ableton. Instead,
# exec the module-level functions into a namespace.
def _load_helpers():
    """Extract the pure functions from the remote script source."""
    from pathlib import Path
    src = (Path(__file__).parent.parent / "ableton" / "__init__.py").read_text(encoding="utf-8")

    # Extract everything after "# ---- Built-in helpers" and
    # "# ---- Serialization" — these are the module-level functions
    ns = {"json": __import__("json"), "time": __import__("time")}
    marker = "# ---- Built-in helpers"
    idx = src.index(marker)
    exec(src[idx:], ns)
    return ns


_ns = _load_helpers()
find_items = _ns["find_items"]
find_item = _ns["find_item"]
serialize = _ns["serialize"]


# ── Mock browser tree ────────────────────────────────────────────────────────


class MockBrowserItem:
    """Minimal mock of Ableton's BrowserItem."""

    def __init__(self, name, is_loadable=False, children=None):
        self.name = name
        self.is_loadable = is_loadable
        self.children = children or []


def make_drums_tree():
    """Mimics the real browser.drums structure that caused the 808 bug."""
    return MockBrowserItem("Drums", children=[
        # "Drum Hits" folder comes first alphabetically — depth-first would enter here
        MockBrowserItem("Drum Hits", children=[
            MockBrowserItem("Kick", children=[
                MockBrowserItem("Kick 808 Boom.wav", is_loadable=True),
                MockBrowserItem("Kick 808 Deep.wav", is_loadable=True),
                MockBrowserItem("Kick Acoustic.wav", is_loadable=True),
            ]),
            MockBrowserItem("Cowbell", children=[
                MockBrowserItem("Cowbell 808 DMX.wav", is_loadable=True),
            ]),
        ]),
        # Kits at top level — what we actually want
        MockBrowserItem("505 Core Kit.adg", is_loadable=True),
        MockBrowserItem("808 Core Kit.adg", is_loadable=True),
        MockBrowserItem("909 Core Kit.adg", is_loadable=True),
        MockBrowserItem("Boom Bap Kit.adg", is_loadable=True),
    ])


def make_instruments_tree():
    """Mimics browser.instruments with nested presets."""
    return MockBrowserItem("Instruments", children=[
        MockBrowserItem("Drift", children=[
            MockBrowserItem("Piano & Keys", children=[
                MockBrowserItem("Grand Piano.adg", is_loadable=True),
                MockBrowserItem("E-Piano Rhodish.adg", is_loadable=True),
            ]),
            MockBrowserItem("Synth Lead", children=[
                MockBrowserItem("Homebound Lead.adg", is_loadable=True),
            ]),
        ]),
        MockBrowserItem("Simpler", children=[
            MockBrowserItem("Piano Simple.adg", is_loadable=True),
        ]),
    ])


# ── find_items tests ─────────────────────────────────────────────────────────


class TestFindItems:
    def test_exact_match_ranked_first(self):
        """'808' should rank '808 Core Kit.adg' (starts-with) above 'Cowbell 808 DMX'."""
        tree = make_drums_tree()
        results = find_items(tree, "808")
        names = [r.name for r in results]
        assert names[0] == "808 Core Kit.adg"

    def test_substring_matches_included(self):
        tree = make_drums_tree()
        results = find_items(tree, "808")
        names = [r.name for r in results]
        assert "Cowbell 808 DMX.wav" in names
        assert "Kick 808 Boom.wav" in names

    def test_exact_name_beats_prefix(self):
        """If bare name exactly equals query, it should come before starts-with."""
        tree = MockBrowserItem("root", children=[
            MockBrowserItem("Reverb Extra.adg", is_loadable=True),
            MockBrowserItem("Reverb.adg", is_loadable=True),
        ])
        results = find_items(tree, "reverb")
        assert results[0].name == "Reverb.adg"

    def test_case_insensitive(self):
        tree = make_drums_tree()
        results = find_items(tree, "BOOM BAP")
        names = [r.name for r in results]
        assert "Boom Bap Kit.adg" in names

    def test_limit(self):
        tree = make_drums_tree()
        results = find_items(tree, "808", limit=2)
        assert len(results) <= 2

    def test_no_match_returns_empty(self):
        tree = make_drums_tree()
        results = find_items(tree, "xyznonexistent")
        assert results == []

    def test_max_depth_respected(self):
        """With max_depth=0, should only search the root's immediate children."""
        tree = make_drums_tree()
        results = find_items(tree, "808", max_depth=0)
        names = [r.name for r in results]
        # Should find the top-level kit but not the nested hits
        assert "808 Core Kit.adg" in names
        assert "Kick 808 Boom.wav" not in names

    def test_non_loadable_items_skipped(self):
        tree = make_drums_tree()
        results = find_items(tree, "Drum Hits")
        # "Drum Hits" is a folder, not loadable — should not appear
        assert all(r.is_loadable for r in results)

    def test_extension_stripped_for_matching(self):
        """'Grand Piano' should match 'Grand Piano.adg' as exact."""
        tree = make_instruments_tree()
        results = find_items(tree, "Grand Piano")
        assert results[0].name == "Grand Piano.adg"


# ── find_item tests ──────────────────────────────────────────────────────────


class TestFindItem:
    def test_returns_best_match(self):
        tree = make_drums_tree()
        result = find_item(tree, "808")
        assert result.name == "808 Core Kit.adg"

    def test_returns_none_on_no_match(self):
        tree = make_drums_tree()
        result = find_item(tree, "xyznonexistent")
        assert result is None

    def test_exact_match_preferred(self):
        tree = make_instruments_tree()
        result = find_item(tree, "Grand Piano")
        assert result.name == "Grand Piano.adg"


# ── serialize tests ──────────────────────────────────────────────────────────


class TestSerialize:
    def test_primitives(self):
        assert serialize(None) is None
        assert serialize(True) is True
        assert serialize(42) == 42
        assert serialize(3.14) == 3.14
        assert serialize("hello") == "hello"

    def test_bytes(self):
        assert serialize(b"hello") == "hello"

    def test_list(self):
        assert serialize([1, "two", 3.0]) == [1, "two", 3.0]

    def test_tuple(self):
        assert serialize((1, 2)) == [1, 2]

    def test_dict(self):
        assert serialize({"a": 1}) == {"a": 1}

    def test_set(self):
        result = serialize({3, 1, 2})
        assert result == [1, 2, 3]

    def test_nested(self):
        assert serialize({"a": [1, (2, 3)]}) == {"a": [1, [2, 3]]}

    def test_depth_limit(self):
        """Deeply nested objects should be stringified past depth 4."""
        deep = {"a": {"b": {"c": {"d": {"e": {"f": "too deep"}}}}}}
        result = serialize(deep)
        # Depth 0→a, 1→b, 2→c, 3→d, 4→e, 5→ stringified
        assert isinstance(result["a"]["b"]["c"]["d"]["e"], str)

    def test_named_object(self):
        """Objects with .name should serialize to a dict with 'name' key."""

        class FakeDevice:
            name = "Reverb"
            value = 0.5
            is_active = True

        result = serialize(FakeDevice())
        assert result["name"] == "Reverb"
        assert result["value"] == 0.5
        assert result["is_active"] is True

    def test_midi_note_object(self):
        """Objects with .pitch and .start_time should serialize as MIDI notes."""

        class FakeNote:
            pitch = 60
            start_time = 0.0
            duration = 0.5
            velocity = 100
            mute = False

        result = serialize(FakeNote())
        assert result == {
            "pitch": 60,
            "start_time": 0.0,
            "duration": 0.5,
            "velocity": 100,
            "mute": False,
        }

    def test_generic_iterable(self):
        """Generic iterables should be serialized as lists."""
        result = serialize(x * 2 for x in range(3))
        assert result == [0, 2, 4]
