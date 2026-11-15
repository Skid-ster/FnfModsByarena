# Contributing to Super Scary Trollge

Thanks for wanting to help! This repo is a *generated* mod: charts, audio and art are all produced by the
scripts in `tools/`, so most contributions are a code change plus a regeneration.

## Ground rules

1. **Never hand-edit generated files.** These are outputs:
   * `mods/TrollgeMod/songs/*/charts/*.json`
   * `mods/TrollgeMod/songs/*/meta.json`, `events.json`
   * `mods/TrollgeMod/images/**` (including `images/characters/*.png/.xml`,
     `data/characters/*.xml` and the `images/icons/*` -- those come from `tools/make_characters.py`)
   * `mods/TrollgeMod/images/game/**` -- arrow skins, splashes, health bar, countdown
     (`tools/make_noteskin.py`, `tools/make_hud.py`)
   * `mods/TrollgeMod/data/splashes/default.xml` (`tools/make_noteskin.py`)
   * `mods/TrollgeMod/songs/*/song/Inst.ogg`, `mods/TrollgeMod/sounds/*.ogg`
   * `docs/*.png` previews

   Edit the generator instead (`tools/song_layout.py`, `tools/trollge_art.py`, `tools/make_audio.py`,
   `tools/make_art.py`, `tools/make_noteskin.py`, `tools/make_hud.py`) and re-run it. CI fails if charts drift.
2. **Keep it Codename Engine compatible.** We target the Codename chart format (`chartVersion 1.6.0`,
   `codenameChart: true`) and HScript (`data/scripts/*.hx`). Psych Engine formats are not supported.
3. **Keep the scare tiers honest.** The ladder is 2/10 → 4/10 → 6/10 → 8/10 → 10/10, one band per song, and it
   has to stay strictly rising (`tools/audit_songs.py` fails otherwise). If you add a jumpscare to song 1, you have
   changed the design — say so in the PR.
4. **Never hand-place the stage.** Character positions, the gap between them and `camyoffset` are validated by
   `tools/make_stage_preview.py` against the engine's real framing maths; edit `data/stages/trollge.xml` and re-run
   it instead of nudging numbers until it looks right in one resolution.

## Workflow

```bash
pip install pillow numpy soundfile

# make your change, then rebuild whatever you touched
python3 tools/make_art.py      # only if you touched trollge_art.py / make_art.py
python3 tools/make_audio.py    # only if you touched song_layout.py / make_audio.py
python3 tools/make_noteskin.py # only if you touched make_noteskin.py (arrow skins + splashes)
python3 tools/make_hud.py      # only if you touched make_hud.py (health bar + countdown)
python3 tools/make_chart.py    # if you touched song_layout.py (charts)
python3 tools/make_stage_preview.py  # if you touched the stage xml

python3 tools/validate_mod.py  # must print VALIDATION PASSED
python3 tools/audit_songs.py   # mix + chart style report; --strict fails on a metric outside its window
```

Commit the regenerated files together with the generator change, in one commit, e.g.:

```
feat(song3): denser final section

- song_layout: +2 dense phrase blocks in the last act
- regenerated charts + instrumental
```

## Changing the music

* **Arrangement** is by section role, not by hand: `section_roles()` in `tools/song_layout.py` labels every phrase
  block (`intro`, `verse`, `build`, `drop`, `break`, `finale`) from its position and rhythm cell, and `ROLE_GAIN`
  sets how hard each role pushes. The chart writer reads the same list, so a `break` block drops its drums *and*
  becomes a sparse `HALF` cell. Add a role, or change where one lands, and all five songs follow.
* **Chart shape** is `section_measures` (bars per phrase block, 2-4 like the base game) plus `cells` (one rhythm cell
  per block, cycled). Blocks alternate `opponent → player`, so every bar is owned by exactly one character; keep it
  that way, or `tools/validate_mod.py` fails with "a bar mixes player and opponent notes".
* **Difficulties** come from `notes(song, difficulty)`: hard keeps every note, normal two in three, easy every second.
  Do not hand-write an easy chart — it is a strided subset, so the three charts can never disagree about timing.
* **Song identity** is `"style"` in `song_layout.py` (`bounce`, `trap`, `glitch`, `industrial`, `finale`). Each style
  picks its own kit,
  bass and lead voice from `kick_for` / `snare_for` / `hat_for` / `bass_for` / `lead_for` and its own groove in
  `render_song()`. Add a style, not a special case.
* **Mix balance** lives in the pan table near the end of `render_song()` (stem -> left/right gains), the master EQ
  breakpoints and the loudness target `TARGET_RMS`. Change them and `tools/audit_songs.py` tells you what it did to
  the spectrum, width and dynamics — it is the same script CI runs with `--strict`.
* **Scare tier = production tier.** `tier_for()` maps the 0-10 scare rating onto a 1-5 production tier, and the tier
  decides how many horror layers sit under the mix (dread drone → tape hiss → whisper swells → breathing tritone →
  heartbeat + whispers + choir) and how hard the camera works.
* **Do not chase loudness by squashing.** The audit enforces a crest factor window (7-20 dB) and 5+ dB of section
  dynamics on purpose: a wall of sound fails the build.

## Changing the screen grade

`shaders/trollge_vhs.frag` is the full-screen filter; `data/stages/trollge.hx` loads it, sets its uniforms every
frame and disables it silently when the platform cannot run shaders. Keep to the engine's shader rules (they are in
`assets/shaders/engine/CompatabilityGuide.md` upstream, and `tools/validate_mod.py` enforces the important ones):
no `switch`, no reversed `smoothstep`, `#pragma header` at the top, and float literals written as `0.0`.

## Changing the arrows or the HUD

* **Arrow colours** live in `LANES` / `SHADOW_LANES` in `tools/make_noteskin.py`; each skin is drawn from that
  palette, so changing one RGB triple re-skins a whole lane. Re-run the script, then
  `python3 tools/make_chart.py` if you renamed a skin.
* **Which song uses which skin** is `song_layout.py` -> `"noteskin"` (`None`, `"shadow"`, `"corrupt"`). The
  chart's `noteTypes` carries it to the notes; `data/stages/trollge.hx` mirrors it onto the strums through
  `onStrumCreation`, because the engine always builds strums from `game/notes/default`.
* **Frame names are fixed by the engine** -- `arrowLEFT`, `left press`, `left confirm`, `purple`, `purple hold
  piece`, `purple hold end`. Every skin must have the same frame set and no frame larger than the sizes in
  `SKIN_SIZES` (`tools/validate_mod.py` enforces both).
* **HUD** is pure filename theming: `images/game/healthBar.png`, `ready.png`, `set.png`, `go.png` and
  `sounds/intro{1,2,3,Go}.ogg`. Keep the health bar's centre dark and opaque -- the `FlxBar` is drawn 4 px
  inside it.

## Adding a character (skin or phase)

1. Drop the Sparrow atlas (`<name>.png` + `<name>.xml`) into `art_src/bf/` (Boyfriend) or
   `art_src/trollge/` (Trollge).
2. Add an entry to `SKINS` in `tools/make_characters.py` (set `"role": "player"` for Boyfriend-style
   characters and `"role": "opponent"` for the Trollge phases):

```python
{
    "song": "getting_dark",
    "role": "player",
    "source": SRC_BF,
    "files": ("Boyfriend_<name>.png", "Boyfriend_<name>.xml"),
    "short": "BFnew",                     # frame-name prefix inside the built atlas
    "sprite": "Boyfriend_<name>",         # images/characters/<sprite>.png
    "character": "bf_<name>",             # data/characters/<character>.xml
    "dead_character": "bf_<name>_dead",
    "icon": "bf_<name>",
    "color": "#31B0D1",
    "icon_frames": (("idle", 0), ("singUPmiss", 0)),
    "derive_miss": True,                  # grade miss poses if the atlas has none
    "anims": [("idle", "BF idle dance", 24, True), ...],   # engine name, atlas prefix, fps, loop
    "dead": ("Gameover", 24),
    "mirror": {"singRIGHT": "singLEFT"},  # optional: rebuild a corrupt animation
},
```

   Add `"tint": {"hue": -74.0, "sat": 0.72, "contrast": 1.22}` to re-colour an existing upload
   instead of shipping a new one (`bf_glitched` and `bf_damned` are built this way).

3. `python3 tools/make_characters.py bf_smiler` -- it normalises the atlas (feet on the shared ground line,
   centred, every frame on the skin's canvas), writes the character XMLs, builds the health icon and a preview,
   and warns you about any animation the atlas is missing.
4. Point the song at it in `tools/song_layout.py` (`"bf"` or `"trollge"`), then
   `python3 tools/make_chart.py`.
5. `python3 tools/validate_mod.py` -- it now checks that every character a chart references exists,
   that all of its animations resolve to real frames, and that the atlas is uniformly framed.

## Ideas that fit well

* New story event functions in `data/scripts/trollge_song_behavior.hx` (add them to the event list in
  `tools/song_layout.py` so the charts and audio stingers pick them up).
* More poses in `tools/trollge_art.py` — the pose library is a list, adding a pose automatically adds atlas frames.
* Better backdrops/horror grading in `tools/make_art.py`.
* A fourth difficulty (e.g. `erect`) — add it to `L.DIFFICULTIES` and `DIFFICULTY_STRIDE` in `tools/song_layout.py`;
  `tools/make_chart.py` writes a chart per entry and `meta.json` follows.
* More rhythm cells — add one to `CELLS` in `tools/song_layout.py` and reference it from a song's `cells` list.

## Reporting bugs

Use the issue templates. For crashes, attach the engine log and say **which song, which difficulty and roughly
which timestamp** — the story events are time-based, so "right after the 32 s jumpscare" is genuinely useful.
