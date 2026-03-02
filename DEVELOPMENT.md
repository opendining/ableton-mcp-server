# AbletonMCP — Development Guide

## Architecture

Two Python processes connected by TCP on `localhost:16619`:

```
Claude ←→ MCP (stdio) ←→ server/server.py ←→ TCP :16619 ←→ ableton/__init__.py (inside Ableton)
```

**MCP Server** (`server/server.py`)
- Standalone Python process, started by `uv run`
- Exposes 3 MCP tools: `execute`, `api`, `search_api`
- Connects to Ableton over TCP, sends/receives newline-delimited JSON (NDJSON)
- Pure pass-through — sends Python code, returns serialized results

**Remote Script** (`ableton/__init__.py`)
- Runs inside Ableton Live's embedded Python interpreter
- TCP server that accepts NDJSON requests and `eval()`/`exec()`s the code
- Full access to the Live Object Model via `_Framework.ControlSurface`
- Auto-serializes Live API objects to JSON

**API Reference** (`server/api_reference.json` + `server/api_reference.md`)
- Structured reference of Live API classes (Song, Track, Clip, Device, etc.)
- JSON file: comprehensive data (properties, methods, types, descriptions) — browsed via `api()`, searched via `search_api()`
- Markdown file: compact cheat sheet — exposed as MCP resource
- Not required for execution — Claude can run any valid Python

## File Layout

```
abletonmcp/
├── .claude-plugin/
│   └── plugin.json         # Claude Code plugin manifest
├── .mcp.json               # MCP server auto-start config (plugin mode)
├── skills/
│   └── ableton-guide/
│       └── SKILL.md        # Agent guide — scope vars, helpers, gotchas, recipes
├── ableton/
│   └── __init__.py         # Remote Script — Python REPL inside Ableton
├── server/
│   ├── server.py           # MCP server — thin bridge (standalone, no plugin deps)
│   ├── api_reference.json  # Structured API reference
│   ├── api_reference.md    # Quick-reference cheat sheet (MCP resource)
│   └── __init__.py
├── CLAUDE.md               # Minimal dev-orientation for working on this project
├── DEVELOPMENT.md          # This file
├── README.md               # User-facing docs
├── pyproject.toml
└── uv.lock
```

## Wire Protocol

Messages are **newline-delimited JSON** (NDJSON). Each message is a single JSON object followed by `\n`.

Request (MCP Server → Remote Script):
```
{"code": "song.tempo"}\n
```

Response (Remote Script → MCP Server):
```
{"status": "ok", "result": 120.0}\n
```

Both sides use `socket.makefile()` for buffered line-based I/O, which eliminates manual buffer management.

## How Execution Works

1. Claude calls `execute(code="song.tempo")` via MCP
2. MCP Server sends `{"code": "song.tempo"}\n` over TCP to port 16619
3. Remote Script receives it in `_dispatch()` → `_execute()`:
   - Builds a scope via `_build_scope()`: `song`, `app`, `tracks`, `returns`, `master`, `browser`, `Live`, `MidiNoteSpecification`, `find_item`, `find_items`, `find_track`, `load_to`, `log`, `json`, `time`
   - Tries `eval(code, scope)` first — if it's an expression, returns the value
   - If `SyntaxError`, falls back to `exec(code, scope)` — for statements, reads `result` variable if set
   - Everything runs on Ableton's main thread via `schedule_message(0, callback)` with a 12-second timeout
4. The return value is passed through `serialize()` (module-level function) which converts Live API objects to JSON-safe types
5. Response NDJSON is sent back over TCP, MCP Server returns it to Claude

### The Namespace

Code executed via `execute()` has these variables in scope:

| Name | What It Is |
|---|---|
| `song` | The Live Set. Tempo, tracks, scenes, transport, etc. |
| `app` | The Live Application. Browser access, version info. |
| `tracks` | `song.tracks` — shortcut to the track list |
| `returns` | `song.return_tracks` — return/send tracks |
| `master` | `song.master_track` — the master track |
| `browser` | `app.browser` — for browsing and loading instruments/effects/sounds |
| `Live` | The `Live` module — full access to `Live.Clip`, `Live.Device`, etc. |
| `MidiNoteSpecification` | `Live.Clip.MidiNoteSpecification` — no import needed |
| `find_item` | `find_item(parent, query)` — breadth-first browser search, returns best BrowserItem or None |
| `find_items` | `find_items(parent, query, limit=20)` — breadth-first browser search, returns ranked list |
| `find_track` | `find_track(name)` — track lookup by name (case-insensitive), returns Track or None |
| `load_to` | `load_to(track, parent, query)` — find browser item + select track + load. Raises ValueError if not found |
| `log` | `self.log_message` — writes to Ableton's Log.txt |
| `json` | The `json` module |
| `time` | The `time` module |

### Serialization

The module-level `serialize()` function converts Live API objects to JSON:

| Input Type | Output |
|---|---|
| `None`, `bool`, `int`, `float`, `str` | As-is |
| `bytes` | Decoded to `str` (UTF-8, replace errors) |
| `list`, `tuple` | Recursively serialized |
| `dict` | Recursively serialized |
| `set`, `frozenset` | Sorted list, recursively serialized |
| MidiNote-like (has `.pitch`, `.start_time`) | `{"pitch": N, "start_time": T, "duration": D, "velocity": V, "mute": B}` |
| Named objects (has `.name`) | `{"name": "...", ...}` with `value`, `min`, `max`, `is_enabled`, `is_active`, `is_quantized` if present |
| Iterable collections | Converted to list, recursively serialized |
| Everything else | `str(obj)` |

Max depth is 4 to prevent infinite recursion on circular references.

### Main Thread Scheduling

Ableton requires state-modifying operations to run on the main thread. The Remote Script schedules all code execution via `schedule_message(0, callback)` and uses a `threading.Event` to wait for completion with a 12-second timeout. This means:

- Read-only operations are safe but have a small scheduling overhead
- Write operations execute correctly on the main thread
- Long-running code (>12s) will timeout

## Plugin Layer

The project doubles as a Claude Code plugin. The plugin layer is purely additive — it wraps the standalone MCP server with easy installation and an agent guide skill.

| File | Purpose |
|---|---|
| `.claude-plugin/plugin.json` | Plugin manifest (name, version, description) |
| `.mcp.json` | Auto-starts the MCP server when the plugin is enabled |
| `skills/ableton-guide/SKILL.md` | Agent guide (scope vars, helpers, gotchas, recipes) — Claude auto-loads when working with Ableton tools |

The MCP server (`server/server.py`) has **no plugin dependencies**. It works identically whether started by the plugin, by `claude mcp add`, or by Claude Desktop's JSON config.

## Dev Workflow

### One-Time Setup

1. **Symlink the Remote Script** into Ableton's Remote Scripts directory:
   ```powershell
   # Windows (PowerShell)
   New-Item -ItemType Junction `
     -Path "C:\ProgramData\Ableton\Live 12 Intro\Resources\MIDI Remote Scripts\AbletonMCP" `
     -Target "C:\Users\you\Documents\abletonmcp\ableton"
   ```

2. **Point MCP config at local source:**
   ```bash
   claude mcp add --scope user AbletonMCP -- uv run --directory /path/to/abletonmcp ableton-live-mcp
   ```

### Edit-Test Loop

| What Changed | What to Restart |
|---|---|
| `ableton/__init__.py` (Remote Script) | Toggle control surface off/on in Ableton Settings, or restart Ableton |
| `server/server.py` (MCP Server) | Reconnect MCP (`/mcp` in Claude Code, or restart Claude Desktop) |
| `server/api_reference.json` or `api_reference.md` | Reconnect MCP (server reloads on startup) |

### Logging

**Ableton Log.txt** — the Remote Script writes here via `self.log_message()`:
- Windows: `%APPDATA%\Ableton\Live x.x.x\Preferences\Log.txt`
- macOS: `~/Library/Preferences/Ableton/Live x.x.x/Log.txt`

Every execution is logged: `AbletonLiveMCP: exec: <code>` on receive, `AbletonLiveMCP: error: <error>` on failure.

**MCP Server stderr** — logs every command sent/received:
```
>>> song.tempo
<<< OK
```

## Adding New Capabilities

**You don't need to change any code.** The whole point of the REPL architecture is that Claude can use any Live API feature immediately by writing Python. No new command handlers, no protocol changes.

To make a pattern **discoverable**, add it to `server/api_reference.json` under the appropriate class. Each class has `properties` (with type, access, description) and `methods` (with signature, description):
```json
{
  "Track": {
    "properties": {
      "new_prop": { "type": "bool", "access": "rw", "description": "What it does" }
    },
    "methods": {
      "new_method": { "signature": "(arg)", "description": "What it does" }
    }
  }
}
```

Claude can then find it via `search_api("new_prop")`.

## Live API Quick Reference

See `server/api_reference.md` for the compact cheat sheet (also exposed as an MCP resource), or `server/api_reference.json` for the full structured reference browsable via `api()` and `search_api()`.

## Constraints

- **Single client**: Only one MCP server should connect at a time
- **Main thread**: All code runs on Ableton's main thread — long operations block the UI
- **12-second timeout**: Execution that takes longer will return a timeout error
- **Serialization depth**: Auto-serializer goes 4 levels deep; deeper objects become `str(obj)`
- **No async**: The Remote Script runs synchronous Python; no `await`
- **Browser search is slow**: Recursive searches across the full browser tree can take seconds
