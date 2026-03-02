---
name: ableton-guide
description: >
  Agent guide for controlling Ableton Live via MCP. Covers execution scope
  (song, tracks, browser, find_item, find_items, find_track, load_to,
  MidiNoteSpecification), gotchas (fresh scope each call, track index shifting,
  sleep between browser loads), and quick recipes. Load this when using Ableton
  Live MCP tools.
user-invocable: false
---

# Ableton Live MCP — Agent Guide

You control Ableton Live by sending Python code via the `execute` tool. Each call is a fresh scope with these variables:

`song`, `app`, `tracks`, `returns`, `master`, `browser`, `Live`, `MidiNoteSpecification`, `find_item`, `find_items`, `find_track`, `load_to`, `log`, `json`, `time`

Use `api()` and `search_api(query)` to explore the Live API reference.

## Built-in Helpers

These are in scope every call — no imports or definitions needed.

**`MidiNoteSpecification(pitch, start_time, duration, velocity)`** — create MIDI note specs:
```python
clip.add_new_notes(tuple([
    MidiNoteSpecification(pitch=60, start_time=0.0, duration=0.5, velocity=100),
]))
```

**`find_item(parent, query)`** — search a browser tree for the best-matching loadable item (case-insensitive, breadth-first, prefers exact matches). Returns BrowserItem or None:
```python
find_item(browser.instruments, "Grand Piano")
find_item(browser.drums, "808")  # finds "808 Core Kit" not a random 808 sample
find_item(browser.audio_effects, "Reverb")
```

**`find_items(parent, query, limit=20)`** — like `find_item` but returns a ranked list. Use when you want to see candidates:
```python
find_items(browser.drums, "808")  # → [808 Core Kit.adg, 808 variants…, individual 808 hits…]
```

**`find_track(name)`** — look up a track by name (case-insensitive). Returns Track or None:
```python
bass = find_track("Bass")
bass.mixer_device.volume.value = 0.8
```

**`load_to(track, parent, query)`** — find a browser item, select the track, and load it. Returns the BrowserItem. Raises `ValueError` if nothing matched:
```python
load_to(song.tracks[0], browser.instruments, "Grand Piano")
load_to(find_track("Drums"), browser.drums, "808")
```

## Gotchas

- **Fresh scope each call.** Variables/functions from a previous `execute` don't carry over.
- **Track indices shift** after create/delete. Use `find_track(name)` or `song.tracks` (not the `tracks` shortcut, which is a stale snapshot).
- **Can't delete the last track.** Loop from the end: `for i in range(len(song.tracks) - 1, 0, -1): song.delete_track(i)`
- **Multi-line code can partially execute.** If line 5 fails, lines 1–4 already ran. Use `song.undo()` to roll back.
- **`time.sleep(0.3)` between consecutive browser loads** (`load_to` or `browser.load_item`). Without it, loads silently fail.
- **No export API.** Tell the user to export manually (Ctrl+Shift+R / Cmd+Shift+R).
- **Return data with `result`.** Expressions return their value directly. For statements, assign to `result`:
  ```python
  result = [(i, t.name) for i, t in enumerate(song.tracks)]
  ```

## Quick Recipes

**Clean slate:**
```python
for i in range(len(song.tracks) - 1, 0, -1):
    song.delete_track(i)
```

**Create a track with a clip:**
```python
song.create_midi_track(-1)
idx = len(song.tracks) - 1
song.tracks[idx].name = "Bass"
song.tracks[idx].clip_slots[0].create_clip(8.0)  # 8 beats = 2 bars
```

**Play everything:**
```python
for t in song.tracks:
    t.clip_slots[0].fire()
song.start_playing()
```
