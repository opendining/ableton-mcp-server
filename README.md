# Ableton Live MCP

[![PyPI](https://img.shields.io/pypi/v/ableton-live-mcp)](https://pypi.org/project/ableton-live-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/ableton-live-mcp)](https://pypi.org/project/ableton-live-mcp/)
[![Tests](https://github.com/opendining/ableton-mcp-server/actions/workflows/tests.yml/badge.svg)](https://github.com/opendining/ableton-mcp-server/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

MCP Server for Ableton Live, to let AI agents control or inspect Ableton.

## Quick Start

### 1. Install the Remote Script

Download [`ableton/__init__.py`](ableton/__init__.py) and place it in a new folder called **`AbletonLiveMCP`** inside Ableton's MIDI Remote Scripts directory:

- **Windows:** `C:\ProgramData\Ableton\Live XX\Resources\MIDI Remote Scripts\AbletonLiveMCP\`
- **macOS:** Right-click Ableton Live → Show Package Contents → `Contents/App-Resources/MIDI Remote Scripts/AbletonLiveMCP/`

Then enable it in Ableton: **Settings → Link, Tempo & MIDI → Control Surface → AbletonLiveMCP** (Input/Output: None).

### 2. Connect Claude

First, install **[uv](https://astral.sh/uv)** (which includes `uvx`) if you don't already have it:

| Platform | Command |
|---|---|
| **macOS** | `brew install uv` |
| **Windows** | `winget install astral-sh.uv` |

<details><summary>Alternative install methods</summary>

```bash
# macOS/Linux — standalone installer
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows — PowerShell standalone installer
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

</details>

Then connect Claude:

**Claude Code:**

```bash
claude mcp add --scope user AbletonLiveMCP -- uvx ableton-live-mcp
```

**Claude Desktop** — edit your config file (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
    "mcpServers": {
        "AbletonLiveMCP": {
            "command": "uvx",
            "args": ["ableton-live-mcp"]
        }
    }
}
```

### 3. Go

Make sure Ableton is running with the AbletonLiveMCP control surface active, then start (or restart) Claude and ask it to do something in Ableton.

## How It Works

```
Claude  →  MCP Server  →  TCP :16619  →  Remote Script (inside Ableton)
                                              ↓
                                        exec(python_code)
                                              ↓
                                     Live Object Model
                                   (song, tracks, clips, devices, browser...)
```

The MCP server and Remote Script communicate over TCP port 16619. The Remote Script runs inside Ableton's embedded Python interpreter — Claude sends Python code as a string, the Remote Script `exec()`s it with the full Live API in scope, and returns the serialized result. There are no predefined commands — anything the Live API supports is available immediately.

## What Claude Can Do

```python
# Read session state
song.tempo                                        # → 120.0
[(i, t.name) for i, t in enumerate(song.tracks)]  # → [(0, "Bass"), (1, "Drums"), ...]

# Modify session
song.tempo = 140
song.tracks[0].name = "Lead Synth"

# Create tracks and clips
song.create_midi_track(-1)
song.tracks[-1].clip_slots[0].create_clip(4.0)

# Write MIDI notes (MidiNoteSpecification is in scope, no import needed)
clip = song.tracks[0].clip_slots[0].clip
clip.add_new_notes(tuple([
    MidiNoteSpecification(pitch=60, start_time=0.0, duration=0.5, velocity=100),
    MidiNoteSpecification(pitch=64, start_time=1.0, duration=0.5, velocity=90),
]))

# Find and load instruments (find_item, find_items, find_track, load_to are in scope)
load_to(song.tracks[0], browser.instruments, "Grand Piano")
load_to(find_track("Drums"), browser.drums, "808")

# Control transport
song.start_playing()
song.stop_playing()
song.tracks[0].clip_slots[0].fire()

# Mix
find_track("Bass").mixer_device.volume.value = 0.7
song.tracks[0].mixer_device.panning.value = -0.3
```

## MCP Tools

The server exposes three tools:

| Tool | Purpose |
|---|---|
| `execute(code)` | Send Python code to run inside Ableton. The main tool. |
| `api(class_name?)` | Browse the Live API reference by class (Song, Track, Clip, Device, etc.). |
| `search_api(query)` | Search the API reference by keyword across all classes. |

`api` and `search_api` read from a structured API reference. Claude can execute anything the Live API supports, not just what's in the reference.

### Execution Scope

Every `execute` call gets a fresh namespace with:

| Variable | What It Is |
|---|---|
| `song` | The Live Set — tempo, tracks, scenes, transport |
| `app` | The Live Application — browser, version info |
| `tracks` | Shortcut for `song.tracks` (stale after create/delete — use `song.tracks` or `find_track`) |
| `returns` | `song.return_tracks` |
| `master` | `song.master_track` |
| `browser` | `app.browser` — instruments, effects, drums, sounds |
| `Live` | The `Live` module — `Live.Clip`, `Live.Device`, etc. |
| `MidiNoteSpecification` | `Live.Clip.MidiNoteSpecification` — no import needed |
| `find_item(parent, query)` | Search browser tree for best match. Returns BrowserItem or None |
| `find_items(parent, query)` | Search browser tree, return ranked list of matches |
| `find_track(name)` | Look up a track by name. Returns Track or None |
| `load_to(track, parent, query)` | Find a browser item and load it onto a track |
| `log` | Write to Ableton's Log.txt |
| `json` | The `json` module |
| `time` | The `time` module |

## Development

Requires [uv](https://astral.sh/uv) (see [install instructions](#2-connect-claude) above).

**Clone and symlink** the Remote Script for live development (changes take effect on Ableton restart):

```bash
git clone https://github.com/opendining/ableton-mcp-server.git
```

```powershell
# Windows (PowerShell, run once)
New-Item -ItemType Junction `
  -Path "C:\ProgramData\Ableton\Live 12 Intro\Resources\MIDI Remote Scripts\AbletonLiveMCP" `
  -Target "C:\path\to\ableton-mcp-server\ableton"
```

**Run from source** instead of PyPI:

```bash
# Claude Code
claude mcp add --scope user AbletonLiveMCP -- uv run --directory /path/to/ableton-mcp-server ableton-live-mcp
```

```json
// Claude Desktop
{
    "mcpServers": {
        "AbletonLiveMCP": {
            "command": "uv",
            "args": ["run", "--directory", "/path/to/ableton-mcp-server", "ableton-live-mcp"]
        }
    }
}
```

**Claude Code plugin** — auto-starts the MCP server and loads the agent guide skill:

```bash
claude --plugin-dir /path/to/ableton-mcp-server
```

See [DEVELOPMENT.md](DEVELOPMENT.md) for the full architecture guide.

## Troubleshooting

If the MCP server can't reach Ableton, check:

1. Ableton is running with AbletonLiveMCP control surface enabled
2. No other MCP server instance is already connected (only one client at a time)

Check Ableton's Log.txt for Remote Script errors:
- **Windows:** `%APPDATA%\Ableton\Live x.x.x\Preferences\Log.txt`
- **macOS:** `~/Library/Preferences/Ableton/Live x.x.x/Log.txt`

## Acknowledgments

This project was inspired by [ahujasid/ableton-mcp](https://github.com/ahujasid/ableton-mcp), which pioneered the idea of connecting Ableton Live to AI agents via MCP. That project uses a fixed set of tool-per-action commands (create track, add notes, set tempo, etc.).

This fork takes a different approach inspired by Cloudflare's [Code Mode](https://blog.cloudflare.com/code-mode/): instead of predefined commands, the agent writes and executes Python directly against Ableton's runtime. A streamlined execution scope with built-in helpers (`find_item`, `find_track`, `load_to`, etc.) and a searchable API reference give the model everything it needs to use the full Live API without being limited to a curated command set.

## Disclaimer

This project is unofficial and not affiliated with or supported by Ableton. For issues, please use the [issue tracker](https://github.com/opendining/ableton-mcp-server/issues) — not Ableton's support channels.

## License

MIT
