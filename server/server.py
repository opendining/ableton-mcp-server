# Ableton Live MCP v2 — MCP Server
#
# Thin bridge between MCP clients (Claude, etc.) and Ableton Live.
# Connects to the Remote Script's TCP server inside Ableton and
# exposes tools for executing Python code and browsing the Live API.

import json
import logging
import re
import socket
from pathlib import Path

from mcp.server.fastmcp import FastMCP

log = logging.getLogger("ableton-live-mcp")
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)

HOST = "127.0.0.1"
PORT = 16619


# ---------------------------------------------------------------------------
# TCP link to the Remote Script inside Ableton
# ---------------------------------------------------------------------------


class _Ableton:
    """Callable NDJSON client. Maintains a persistent TCP connection
    to the Remote Script, auto-connects on first use, retries once
    on failure.

    Usage:
        _ableton(code="song.tempo")   -> {"status": "ok", "result": 120.0}
        _ableton(ping=True)           -> {"status": "ok", "pong": True}
    """

    def __init__(self):
        self._sock = None
        self._rfile = None

    def __call__(self, **message):
        """Send a message to Ableton and return the parsed response."""
        last_err = None
        for _ in range(2):
            try:
                self._ensure_connected()
                self._sock.sendall(json.dumps(message).encode() + b"\n")
                line = self._rfile.readline()
                if not line:
                    raise ConnectionError("Connection closed")
                return json.loads(line)
            except Exception as err:
                last_err = err
                log.warning("Ableton: %s", err)
                self._reset()
        return {
            "status": "error",
            "error": f"Cannot reach Ableton: {last_err}",
            "hint": "Is Ableton running with AbletonLiveMCP enabled?",
        }

    def _ensure_connected(self):
        if self._sock is None:
            s = socket.create_connection((HOST, PORT), timeout=5)
            s.settimeout(30)
            self._sock, self._rfile = s, s.makefile("rb")
            log.info("Connected to Ableton on port %d", PORT)

    def _reset(self):
        for r in (self._rfile, self._sock):
            try:
                r and r.close()
            except Exception:
                pass
        self._sock = self._rfile = None


_ableton = _Ableton()

# Check connectivity at startup
_startup = _ableton(ping=True)
if _startup.get("pong"):
    log.info("Ableton is reachable")
else:
    log.warning("Ableton not reachable at startup: %s", _startup.get("error", "unknown"))


# ---------------------------------------------------------------------------
# API reference registry
# ---------------------------------------------------------------------------


def _load_api_reference():
    path = Path(__file__).parent / "api_reference.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        log.info("Loaded API reference (%d entries) from %s", len(data), path.name)
        return data
    except Exception as exc:
        log.warning("Could not load api_reference.json: %s", exc)
        return {}


API_REF = _load_api_reference()

# Separate classes from the _enums metadata key
_ENUMS = API_REF.pop("_enums", {})
_CLASSES = API_REF  # everything left is a class


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------


def _stem(word):
    """Reduce a word to a rough stem so quantize/quantization/quantized match."""
    w = word.lower()
    # Order matters: longest suffixes first
    for suffix in (
        "ization",
        "ation",
        "tion",
        "ising",
        "izing",
        "ting",
        "ing",
        "ised",
        "ized",
        "ted",
        "ed",
        "es",
        "s",
    ):
        if len(w) > len(suffix) + 2 and w.endswith(suffix):
            return w[: -len(suffix)]
    return w


def _tokenize(text):
    """Split text into lowercase tokens, treating underscores and spaces alike."""
    return re.findall(r"[a-z0-9]+", text.lower().replace("_", " "))


def _stems_close(a, b):
    """True if stems a and b are close enough to count as a match.
    Allows prefix matching only when the shorter stem is at least 60%
    of the longer one (prevents 'none' matching 'nonexistent')."""
    if a == b:
        return True
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    return long.startswith(short) and len(short) >= len(long) * 0.6


def _match(query_stems, text):
    """True if every query stem matches at least one token stem in text."""
    text_stems = {_stem(t) for t in _tokenize(text)}
    return all(any(_stems_close(qs, ts) for ts in text_stems) for qs in query_stems)


# ---------------------------------------------------------------------------
# MCP server and tools
# ---------------------------------------------------------------------------

mcp = FastMCP("AbletonLiveMCP")


@mcp.resource("ableton-live-mcp://guide", mime_type="text/markdown")
def agent_guide() -> str:
    """Tips, gotchas, and recipes for AI agents controlling Ableton Live."""
    guide = Path(__file__).parent.parent / "CLAUDE.md"
    try:
        return guide.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "Agent guide not found. See the project README."


@mcp.resource("ableton-live-mcp://api/quick-reference", mime_type="text/markdown")
def api_quick_reference() -> str:
    """Compact cheat sheet of the most-used Live API properties and methods."""
    md = Path(__file__).parent / "api_reference.md"
    try:
        return md.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "API quick reference not found."


@mcp.tool()
def execute(code: str) -> str:
    """Execute Python code inside Ableton Live and return the result.

    The code runs in a fresh namespace each call with these variables:

        song     — the Live Set (tempo, tracks, scenes, transport)
        app      — the Live Application (browser, version info)
        tracks   — shortcut for song.tracks (stale after mutations!)
        returns  — shortcut for song.return_tracks
        master   — shortcut for song.master_track
        browser  — app.browser for loading instruments/effects/sounds
        Live     — the Live module (e.g. Live.Clip.MidiNoteSpecification)
        MidiNoteSpecification — shortcut, no import needed
        find_item  — find_item(browser.instruments, "Piano") -> best BrowserItem or None
        find_items — find_items(browser.drums, "808") -> ranked list of BrowserItems
        find_track — find_track("Bass") -> Track or None
        load_to    — load_to(track, browser.instruments, "Piano") -> find + select + load
        log      — write to Ableton's Log.txt
        json     — the json module
        time     — the time module

    Expressions like `song.tempo` are eval'd and return their value.
    Statements like `song.tempo = 140` are exec'd — assign to `result`
    to return data from a statement block.

    Tips:
    - Each call is a fresh scope — define helpers in the same block.
    - After creating/deleting tracks, use find_track(name) or song.tracks (not `tracks`).
    - Add time.sleep(0.3) between consecutive load_to / browser.load_item calls.
    - Use api() and search_api() to explore the Live API reference.
    - Read the ableton-live-mcp://guide resource for the full agent guide.
    """
    preview = code.strip().replace("\n", " | ")[:120]
    log.info(">>> %s", preview)

    resp = _ableton(code=code)
    status = resp.get("status", "unknown")

    if status == "ok":
        log.info("<<< OK (%.3fs)", resp.get("elapsed", 0))
    else:
        log.error("<<< ERROR: %s", resp.get("error", "unknown"))

    return json.dumps(resp, indent=2, default=str)


@mcp.tool()
def api(class_name: str = None) -> str:
    """Browse the Ableton Live API reference by class.

    No argument: list all classes with descriptions and access paths.
    With class name: show full details (properties, methods) for that class.
    With dotted path: show a single member — e.g. api("Song.tempo").
    Special: api("enums") shows all enum/constant tables.

    Examples: api(), api("Song"), api("clip"), api("Song.tempo"), api("enums").
    """
    if not class_name:
        index = {
            name: {"description": cls["description"], "access": cls["access"]}
            for name, cls in _CLASSES.items()
        }
        return json.dumps(index, indent=2)

    raw = class_name.strip()
    query = raw.lower()

    # api("enums") — return all enum tables
    if query == "enums":
        return json.dumps(_ENUMS, indent=2)

    # Check if the full name (including dot) is a class — e.g. "Song.View"
    for name, cls in _CLASSES.items():
        if name.lower() == query:
            return json.dumps({name: cls}, indent=2)

    # Dotted path: api("Song.tempo") → single member
    if "." in raw:
        cls_part, member_part = raw.split(".", 1)
        cls_key = cls_part.strip().lower()
        member_key = member_part.strip().lower()
        for name, cls in _CLASSES.items():
            if name.lower() == cls_key:
                # Search properties then methods
                for prop_name, prop in cls.get("properties", {}).items():
                    if prop_name.lower() == member_key:
                        return json.dumps(
                            {
                                f"{name}.{prop_name}": {
                                    "kind": "property",
                                    "access_path": cls["access"],
                                    **prop,
                                },
                            },
                            indent=2,
                        )
                for method_name, method in cls.get("methods", {}).items():
                    if method_name.lower() == member_key:
                        return json.dumps(
                            {
                                f"{name}.{method_name}": {
                                    "kind": "method",
                                    "access_path": cls["access"],
                                    **method,
                                },
                            },
                            indent=2,
                        )
                members = sorted(list(cls.get("properties", {})) + list(cls.get("methods", {})))
                return json.dumps(
                    {
                        "error": f"'{name}' has no member '{member_part.strip()}'",
                        "members": members,
                    },
                    indent=2,
                )
        # Class part didn't match — fall through to error below

    available = ", ".join(_CLASSES.keys())
    return json.dumps(
        {
            "error": f"Unknown class '{class_name}'",
            "available": available,
        },
        indent=2,
    )


@mcp.tool()
def search_api(query: str) -> str:
    """Search the Live API reference by keyword.

    Searches across class names, property/method names, descriptions, and types.
    Supports multi-word queries ("loop start"), fuzzy stems (quantize ≈ quantization),
    and underscore-aware matching. Returns matching entries grouped by class.

    Examples: search_api("tempo"), search_api("quantize"), search_api("loop start").
    """
    raw = query.strip()
    stems = [_stem(w) for w in _tokenize(raw)]
    if not stems:
        return json.dumps(
            {"message": "Empty query. Try a keyword like 'tempo' or 'warp'."}, indent=2
        )

    # Collect scored results: (score, cls_name, member_type, member_name, member_data)
    hits = []

    for cls_name, cls in _CLASSES.items():
        for prop_name, prop in cls.get("properties", {}).items():
            searchable = " ".join([prop_name, prop.get("type", ""), prop.get("description", "")])
            if _match(stems, searchable):
                score = 3 if _match(stems, prop_name) else 1
                hits.append((score, cls_name, "property", prop_name, prop))

        for method_name, method in cls.get("methods", {}).items():
            searchable = " ".join(
                [
                    method_name,
                    method.get("signature", ""),
                    method.get("description", ""),
                ]
            )
            if _match(stems, searchable):
                score = 3 if _match(stems, method_name) else 1
                hits.append((score, cls_name, "method", method_name, method))

    # Also search enums
    enum_hits = {}
    for enum_name, enum in _ENUMS.items():
        if enum_name == "description":
            continue
        searchable = (
            enum_name
            + " "
            + enum.get("used_by", "")
            + " "
            + " ".join(enum.get("values", {}).values())
        )
        if _match(stems, searchable):
            enum_hits[enum_name] = enum

    if not hits and not enum_hits:
        return json.dumps(
            {
                "message": f"No results for '{raw}'. Try a different keyword, "
                "or use api() to browse all classes.",
            },
            indent=2,
        )

    # Group by class, sorted by best score per class, members sorted by score
    hits.sort(key=lambda h: (-h[0], h[1], h[3]))

    results = {}
    for score, cls_name, kind, member_name, member_data in hits:
        if cls_name not in results:
            cls = _CLASSES[cls_name]
            results[cls_name] = {
                "description": cls["description"],
                "access": cls["access"],
            }
        bucket = "properties" if kind == "property" else "methods"
        results[cls_name].setdefault(bucket, {})[member_name] = member_data

    # Summary header
    member_count = len(hits)
    class_count = len(results)
    mc_s = "" if member_count == 1 else "es"
    cc_s = "" if class_count == 1 else "es"
    summary = f"Found {member_count} match{mc_s} across {class_count} class{cc_s}"
    if enum_hits:
        eh_s = "" if len(enum_hits) == 1 else "s"
        summary += f" + {len(enum_hits)} enum{eh_s}"

    output = {"_summary": summary}
    output.update(results)
    if enum_hits:
        output["_enums"] = enum_hits

    return json.dumps(output, indent=2)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
