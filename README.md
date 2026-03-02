# Ableton Live MCP

[![PyPI](https://img.shields.io/pypi/v/ableton-live-mcp)](https://pypi.org/project/ableton-live-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/ableton-live-mcp)](https://pypi.org/project/ableton-live-mcp/)
[![Tests](https://github.com/opendining/ableton-mcp-server/actions/workflows/tests.yml/badge.svg)](https://github.com/opendining/ableton-mcp-server/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

MCP Server for Ableton Live, to let AI agents control or inspect Ableton.

## Quick Start

1. **Install [uv](https://astral.sh/uv)** if you don't have it
2. **Install Remote Script:** Copy the `ableton/` folder into Ableton's MIDI Remote Scripts directory as `AbletonLiveMCP/` (see [detailed instructions](#1-install-the-remote-script) below)
3. **Enable in Ableton:** Settings > Link, Tempo & MIDI > Control Surface > **AbletonLiveMCP**
4. **Connect Claude:** pick one method from [Setup](#2-connect-claude) below
5. **Go:** Ask Claude to do something in Ableton

## How It Works

```
Claude  →  MCP Server  →  TCP :16619  →  Remote Script (inside Ableton)
                                              ↓
                                        exec(python_code)
                                              ↓
                                     Live Object Model
                                   (song, tracks, clips, devices, browser...)
```

The Remote Script runs inside Ableton's embedded Python interpreter. Claude sends Python code as a string, the Remote Script `exec()`s it with the full Live API in scope, and returns the serialized result. There are no predefined commands — anything the Live API supports is available immediately.

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

## Prerequisites

- **Ableton Live 11+** (uses the extended MIDI note API)
- **[uv](https://astral.sh/uv)** — handles Python and dependencies automatically

### Install uv

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

You do **not** need to install Python separately — `uv` manages that for you.

## Setup

### 1. Install the Remote Script

The Remote Script runs inside Ableton. It needs to be in Ableton's MIDI Remote Scripts directory.

**Option A — Download just the Remote Script** (if you're using `uvx` and don't need the full repo):

Download [`ableton/__init__.py`](ableton/__init__.py) from this repo and place it in a folder called `AbletonLiveMCP` inside:

- **Windows:** `C:\ProgramData\Ableton\Live XX\Resources\MIDI Remote Scripts\`
- **macOS:** Right-click Ableton Live > Show Package Contents > `Contents/App-Resources/MIDI Remote Scripts/`

**Option B — Clone the repo** and symlink (recommended for development):

```bash
git clone https://github.com/opendining/ableton-mcp-server.git
```

```powershell
# Windows (PowerShell, run once)
New-Item -ItemType Junction `
  -Path "C:\ProgramData\Ableton\Live 12 Intro\Resources\MIDI Remote Scripts\AbletonLiveMCP" `
  -Target "C:\path\to\abletonmcp\ableton"
```

Then enable in Ableton: Settings > Link, Tempo & MIDI > Control Surface > **AbletonLiveMCP** (Input/Output: None).

### 2. Connect Claude

Pick **one** method. Using multiple at once will start duplicate servers.

#### Claude Desktop (no clone needed)

Edit your config file:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

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

#### Claude Code (no clone needed)

```bash
claude mcp add --scope user AbletonLiveMCP -- uvx ableton-live-mcp
```

#### Claude Code plugin (clone required)

Auto-starts the MCP server and loads the agent guide skill:
```bash
claude --plugin-dir /path/to/abletonmcp
```

#### From a cloned repo

If you cloned the repo and want to run from source instead of PyPI:
```bash
# Claude Code
claude mcp add --scope user AbletonLiveMCP -- uv run --directory /path/to/abletonmcp ableton-live-mcp
```
```json
// Claude Desktop
{
    "mcpServers": {
        "AbletonLiveMCP": {
            "command": "uv",
            "args": ["run", "--directory", "/path/to/abletonmcp", "ableton-live-mcp"]
        }
    }
}
```

### 3. Verify

1. Make sure Ableton is running with AbletonLiveMCP control surface active
2. Start/restart your Claude client
3. The MCP server connects to Ableton automatically on first use

**Troubleshooting:** Check Ableton's Log.txt for Remote Script errors:
- **Windows:** `%APPDATA%\Ableton\Live x.x.x\Preferences\Log.txt`
- **macOS:** `~/Library/Preferences/Ableton/Live x.x.x/Log.txt`

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

## Architecture

See [DEVELOPMENT.md](DEVELOPMENT.md) for the full technical guide.

## Acknowledgments

This project was inspired by [ahujasid/ableton-mcp](https://github.com/ahujasid/ableton-mcp), which pioneered the idea of connecting Ableton Live to AI agents via MCP. That project uses a fixed set of tool-per-action commands (create track, add notes, set tempo, etc.).

This fork takes a different approach inspired by Cloudflare's [Code Mode](https://blog.cloudflare.com/code-mode/): instead of predefined commands, the agent writes and executes Python directly against Ableton's runtime. A streamlined execution scope with built-in helpers (`find_item`, `find_track`, `load_to`, etc.) and a searchable API reference give the model everything it needs to use the full Live API without being limited to a curated command set.

## License

MIT
