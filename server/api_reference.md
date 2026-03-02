# Ableton Live API — Quick Reference

## Song (`song`)
```python
song.tempo                     # rw float — BPM (20–999)
song.is_playing                # r  bool
song.signature_numerator       # rw int — time sig top
song.signature_denominator     # rw int — time sig bottom
song.metronome                 # rw bool — click on/off
song.loop                      # rw bool — arrangement loop
song.record_mode               # rw bool — global record
song.overdub                   # rw bool — MIDI overdub
song.tracks                    # r  list[Track]
song.return_tracks             # r  list[Track]
song.master_track              # r  Track
song.scenes                    # r  list[Scene]
song.start_playing()           # start transport
song.stop_playing()            # stop transport
song.stop_all_clips()          # stop every clip
song.create_midi_track(-1)     # create MIDI track (-1 = append)
song.create_audio_track(-1)    # create audio track
song.delete_track(index)       # delete track (can't delete last)
song.undo()                    # undo last action
song.redo()                    # redo
```

## Track (`song.tracks[i]` / `find_track(name)`)
```python
track.name                     # rw str
track.mute / .solo / .arm      # rw bool
track.has_midi_input            # r  bool — is MIDI track?
track.clip_slots                # r  list[ClipSlot]
track.devices                   # r  list[Device]
track.mixer_device              # r  MixerDevice
track.color_index               # rw int (0–69)
track.duplicate_clip_slot(idx)  # duplicate clip to next empty slot
```

## ClipSlot (`track.clip_slots[j]`)
```python
slot.has_clip                   # r  bool
slot.clip                       # r  Clip or None
slot.create_clip(length)        # create empty MIDI clip (beats)
slot.delete_clip()
slot.fire()                     # launch clip
slot.stop()                     # stop clip
```

## Clip (`slot.clip`)
```python
clip.name                       # rw str
clip.length                     # r  float (beats)
clip.looping                    # rw bool
clip.loop_start / .loop_end     # rw float
clip.is_midi_clip               # r  bool
clip.muted                      # rw bool — deactivated
clip.gain                       # rw float — audio clip gain
clip.pitch_coarse               # rw int — semitone transpose
clip.warping                    # rw bool
clip.warp_mode                  # rw int (0=Beats,1=Tones,2=Texture,3=Re-Pitch,4=Complex,6=Pro)
clip.fire() / .stop()
clip.add_new_notes(tuple([...]))       # add MIDI notes (MidiNoteSpecification)
clip.get_notes_extended(0,128,0,len)   # read MIDI notes
clip.remove_notes_extended(0,128,0,len)# remove MIDI notes
clip.quantize(grid, strength)          # quantize notes (grid: 1=1/4 … ; strength: 0–1)
clip.duplicate_loop()                  # double loop + duplicate content
clip.crop()                            # crop to loop
```

## Device (`track.devices[j]`)
```python
device.name                     # rw str
device.class_name               # r  str (e.g. "Reverb")
device.parameters               # r  list[DeviceParameter] — [0] is always on/off
device.parameters[0].value = 0  # 0=off, 1=on
device.chains                   # r  list[Chain] — Rack devices only
```

## DeviceParameter (`device.parameters[k]`)
```python
param.name                      # r  str
param.value                     # rw float (between .min and .max)
param.min / .max                # r  float
param.is_quantized              # r  bool — discrete steps?
param.value_items               # r  list[str] — labels for quantized values
```

## MixerDevice (`track.mixer_device`)
```python
mixer.volume.value              # rw float (0.0–1.0, 0.85 ≈ 0 dB)
mixer.panning.value             # rw float (-1.0 L … 1.0 R)
mixer.sends[i].value            # rw float — send level to return track i
mixer.crossfade_assign          # rw int (0=None, 1=A, 2=B)
```

## Scene (`song.scenes[i]`)
```python
scene.name                      # rw str
scene.tempo                     # rw float (-1 = not set)
scene.fire()                    # launch all clips in scene
```

## Song.View (`song.view`)
```python
song.view.selected_track        # rw Track — currently selected
song.view.selected_scene        # rw Scene — currently selected
song.view.detail_clip           # r  Clip — clip in detail view
song.view.highlighted_clip_slot # rw ClipSlot — focused slot
song.view.follow_song           # rw bool — follow playback
song.view.select_device(dev)    # show device in detail view
```

## Browser (`browser`)
```python
browser.instruments / .drums / .sounds / .audio_effects / .midi_effects
item.name / .children / .is_loadable
browser.load_item(item)         # load onto selected track
find_item(parent, query)        # best match → BrowserItem or None
find_items(parent, query)       # ranked list of matches
load_to(track, parent, query)   # find + select + load (helper)
```

## Chain (`device.chains[k]`)
```python
chain.name                      # rw str
chain.mute / .solo              # rw bool
chain.devices                   # r  list[Device]
chain.mixer_device              # r  MixerDevice
```

## DrumPad (`device.drum_pads[k]`)
```python
pad.name                        # rw str
pad.note                        # r  int — MIDI note number
pad.mute / .solo                # rw bool
pad.chains                      # r  list[Chain]
```

---
*Use `api(class_name)` for full details on any class, or `search_api(keyword)` to find properties/methods across the whole API.*
