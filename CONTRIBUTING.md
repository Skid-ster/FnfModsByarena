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
4. **Validate stage placement.** Character positions, the gap between them and camera offsets are modelled by
   `tools/make_stage_preview.py` against the engine's real framing maths; edit `data/stages/trollge.xml` and re-run
   it instead of nudging numbers until it looks right in one resolution.

## Workflow

```bash
pip install pillow numpy soundfile

# make your change, then rebuild whatever you touched
python3 tools/make_art.py      # only if you touched trollge_art.py / make_art.py
                                # (every random pass must be seeded -- an unseeded
                                #  one makes the shipped art differ on every run)
python3 tools/make_audio.py    # only if you touched song_layout.py / make_audio.py
python3 tools/make_noteskin.py # only if you touched make_noteskin.py (arrow skins + splashes)
python3 tools/make_hud.py      # only if you touched make_hud.py (health bar + countdown)
python3 tools/make_chart.py    # if you touched song_layout.py (charts)
python3 tools/make_cutscenes.py # if you touched the cutscene lines or their art
python3 tools/make_promo.py     # docs/banner.jpg (only after a version bump)
python3 tools/make_menu.py      # main menu buttons, backdrop, docs/menu_preview.png
                                # (committed, not diffed in CI: the atlas sizes come
                                #  from font metrics, which drift between Pillow builds)
python3 tools/make_stage_preview.py  # if you touched the stage xml

python3 tools/validate_mod.py  # must print VALIDATION PASSED
python3 tools/test_polish.py    # character wiring, effect timing, HUD and notes
python3 tools/audit_songs.py   # mix + chart style report; --strict fails on a metric outside its window
```

### Packaging and Freeplay

Use `TrollgeMod.zip` for installation, matching the literal `LIB_TrollgeMod`
compatibility copies. `tools/check_freeplay_zip.py` exercises the actual archive
against old and new lookup paths and both rewrite modes. The archive model is not
an engine test; a path-like library name can trigger an unordered folder scan.

Commit the regenerated files together with the generator change, in one commit, e.g.:

```
feat(song3): denser final section

- song_layout: +2 dense phrase blocks in the last act
- regenerated charts + instrumental
```

Both `data/config/freeplaySonglist{.txt,/LIB_TrollgeMod.txt}` and the older
`data/freeplaySonglist{.txt,/LIB_TrollgeMod.txt}` must contain the same ordered
song IDs. Static resolution checks do not replace testing in the engine.

## Changing the music

Research references and their limitations are recorded in [music-research.md](docs/music-research.md).
`measure_roles()` maps role changes directly to chart-bar indices; `melodic_onsets()`
collapses unison hands. After rendering, `check_stem_mix.py` estimates the decoded
sum at equal stem gain, not actual engine playback or standards-compliant true peak.

* **The melody lives in `tools/phrases.py`, not in the renderer.** Each phrase is a block of text where one line is a
  bar of sixteen 16th steps: a number is a semitone above the song's tonic (`12` is the octave, `15` the minor third
  above it), `.` is a rest and `-` ties the previous note. `song_layout.py` parses it (rejecting a phrase that is not a
  whole number of bars), maps each note onto an arrow lane and lays the phrases out over `song["form"]`. Write the
  music there; never hand-edit a chart or an `Inst.ogg`.
* **`form` decides the arrangement.** One entry per chart block names the phrase it sings (and optionally a starting
  bar inside it, e.g. `("verse_b", 2)`). The opponent sings the antecedents (`verse_a`, `chorus_a`), the player the
  consequents (`verse_b`, `chorus_b`), and every fourth exchange inverts the player's phrase. A block that names a
  phrase longer than itself plays a window of it; a block that names a shorter one repeats it.
* **Lanes vs pitches.** A phrase note carries both: `lane` is the arrow the player hits (the note's degree class --
  tonic, flat third, fifth, flat seventh) and `semi` is the pitch the singer sings. That is why the chart can stay
  playable while the tune steps and leaps: `note_pitch()` preserves `semi` without chord snapping, and the chart only needs the lane.
  Harmony and `melody_report.py` use the thinned hard chart, counting doubled hands once; run `python3 tools/test_music.py`
  after touching pitch, chord voicings or the bass. Listening still decides whether it works.
* **Arrangement** is by section role, not by hand: `section_roles()` in `tools/song_layout.py` labels every phrase
  block (`intro`, `verse`, `build`, `drop`, `break`, `finale`) from its position and rhythm cell, and `ROLE_GAIN`
  sets how hard each role pushes. The chart writer reads the same list, so a `break` block drops its drums *and*
  becomes a sparse `HALF` cell. Add a role, or change where one lands, and all five songs follow.
* **Chart shape** is `section_measures` (bars per phrase block, 2-4 like the base game) plus `cells` (one rhythm cell
  per block, cycled). Blocks alternate `opponent → player`, so every bar is owned by exactly one character; keep it
  that way, or `tools/validate_mod.py` fails with "a bar mixes player and opponent notes".
* **In-song captions** are `"captions": [(seconds, "text")]` in `song_layout.py`; `story_events()` turns them into
  chart events, and `trollgeCaption()` in `trollge_song_behavior.hx` types them on the HUD camera. Keep them under 60
  characters — the validator fails anything longer, because it cannot be read in three seconds of scrolling arrows.
* **Cutscene copy** lives in `song_layout.py` too (`"cutscene": {"tag", "lines", "outro"}`). Edit the words there and
  run `tools/make_cutscenes.py`: it rewrites `songs/<song>/cutscene.hx`, `songs/<song>/cutscene-end.hx` and the frames
  in `images/ui/`. Never hand-edit the `.hx` files, CI diffs them.
* **Difficulties** come from `notes(song, difficulty)`: hard applies tier spacing, normal drops one in four of those notes, and easy keeps every second.
  Do not hand-write an easy chart — it is a strided subset, so the three charts can never disagree about timing.
* **Song identity** is `"style"` in `song_layout.py` (`bounce`, `trap`, `glitch`, `industrial`, `finale`). Each style
  picks its own kit,
  bass and lead voice from `kick_for` / `snare_for` / `hat_for` / `bass_for` / `lead_for` and its own groove in
  `render_song()`. Add a style, not a special case.
* **Mix balance** lives in the pan table near the end of `render_song()` (stem -> left/right gains), the master EQ
  breakpoints and the loudness target `TARGET_RMS`. Change them and `tools/audit_songs.py` tells you what it did to
  the spectrum, width and dynamics — it is the same script CI runs with `--strict`. The master EQ thins 1–4 kHz on
  purpose: that is the vocal formant band, and the instrumental leaves it to `Voices.ogg`.
* **Voices are formant voices, not buzzers.** `voice_note()` in `tools/make_audio.py` builds a glottal source with a
  spectral tilt, a pitch scoop, vibrato that grows through the note, and a parallel bank of resonances from `VOWELS`
  (`ah`/`oh`/`ee`/`oo`, first two formants decide the vowel). Boyfriend shifts the formants up and sings bright vowels;
  the Trollge shifts them down, adds sub-harmonic weight and a controlled saturation. If you change a formant, measure
  the vowel again: filter white noise through `lib_dsp.formant_bank()` and check the energy sits in the right band
  (e.g. `ee` should peak at 2.2–3 kHz, `oo` below 1 kHz).
* **Drums are tuned and warm.** Kicks are a 90 → 55 Hz pitch envelope with a smooth amplitude attack (no click, no
  drive by default); snares carry a tuned 180–220 Hz body under band-limited noise and get their tail from the plate in
  the mix; hats are soft-filtered noise with a shelf instead of a hard 6.5 kHz highpass. Harsh 3–8 kHz content is what
  makes a synth mix tiring — check `bandpass()` energy there before shipping a new voice.
* **Scare tier = production tier.** `tier_for()` maps the 0-10 scare rating onto a 1-5 production tier, and the tier
  decides how many horror layers sit under the mix (dread drone → tape hiss → whisper swells → breathing tritone →
  heartbeat + whispers + choir) and how hard the camera works.
* **Do not chase loudness by squashing.** The audit enforces a crest factor window (7-20 dB) and 5+ dB of section
  dynamics on purpose: a wall of sound fails the build.

The current Codename dependency list uses `CodenameCrew/cne-openfl` branch `cne`.
At commit `74f5f97242fa31150d525559e514743398abd8f1`,
`GLSLSourceAssembler.getDefaultVersion()` returns `300 es` on web/mobile,
`410 core` on macOS and `330 core` elsewhere. Its default compatibility pass
rewrites `gl_FragColor` and `texture2D` for modern GLSL. This is source evidence,
not proof of compilation on a particular driver or engine version.

## Changing the screen grade

Two shaders ship, and they stack:

* `shaders/trollge_vhs.frag` -- the VHS grade on `camGame` (wobble, halation, grain, vignette).
* `shaders/crt.frag` -- the CRT pass (`camGame` + a weaker copy on `camHUD`): barrel curvature, RGB split, tear
  bands, scanlines, static, vignette. Uniforms are `uTime`/`iTime`, `uAberration`, `uScanline`, `uStatic`,
  `uCurvature`, `uVignette`, `uGlitch`.

Both are loaded by `data/stages/trollge.hx` with `FunkinShader.fromFile('<name>')` (Psych calls this
`CustomShader`), wrapped in filters with `openfl.filters.ShaderFilter`, and driven from `update(elapsed)`. Rules for
touching them:

* run `python3 tools/test_glsl_compile.py` with `glslangValidator` installed: its minimal preamble catches GLSL syntax/type errors but does not simulate OpenFL or a GPU;
* preserve existing camera filters and remove only this stage's filters during teardown; keep HUD output premultiplied and transparent outside the CRT tube;
* every load, filter creation and `setFloat` stays inside its own `try/catch`, and every shader variable is null-checked
  -- a driver that cannot compile a shader should cost you the effect, never the song;
* a new uniform has to be declared in the `.frag` **and** set by the stage script; `validate_mod.py` cross-checks both
  directions and fails on a mismatch, because `setFloat` on a uniform that does not exist fails silently;
* use the OpenFL names (`openfl_TextureCoordv`, `openfl_TextureSize`, `openfl_Alphav`, `textureCam(bitmap, getCamPos(uv))` for camera filters),
  and never `switch` -- it breaks on macOS GL drivers.

The current Codename dependency list uses `CodenameCrew/cne-openfl` branch `cne`.
At commit `74f5f97242fa31150d525559e514743398abd8f1`,
`GLSLSourceAssembler.getDefaultVersion()` returns `300 es` on web/mobile,
`410 core` on macOS and `330 core` elsewhere. Its default compatibility pass
rewrites `gl_FragColor` and `texture2D` for modern GLSL. This is source evidence,
not proof of compilation on a particular driver or engine version.

## Changing the screen grade

`shaders/trollge_vhs.frag` is the full-screen filter; `data/stages/trollge.hx` loads it, sets its uniforms every
frame and disables it silently when the platform cannot run shaders. Keep to the engine's shader rules (they are in
`assets/shaders/engine/CompatabilityGuide.md` upstream, and `tools/validate_mod.py` enforces the important ones):
no `switch`, no reversed `smoothstep`, `#pragma header` at the top, and float literals written as `0.0`.

## Changing the arrows or the HUD

The rule the noteskin lives by: **a note must be brighter than the receptor it lands on.** The interiors are lifted
towards white around a blurred core (`hot_core` in `tools/make_noteskin.py`) and the receptors stay dark with a hot rim,
a static edge and a keyline. `tools/test_polish.py` checks the finale's four note/receptor pairs and the separation
between lane colours; a change that inverts that relationship can make arrows hard to read at speed. Holds get the same fringe,
scanline and ink pass as the notes so a sustain is legible too.

* **Arrow colours** live in `LANES` / `SHADOW_LANES` in `tools/make_noteskin.py`; each skin is drawn from that
  palette, so changing one RGB triple re-skins a whole lane. Texture passes use seeded noise; preserve this so the
  atlases can be regenerated. Re-run the script, then
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

## Writing HScript for this mod

Codename scripts are interpreted, and the engine registers a fixed set of classes as
script globals (`Script.hx`: `FlxSprite`, `FlxText`, `FlxTypeText`, `FlxCamera`,
`FlxTween`, `FlxTimer`, `Paths`, `PlayState`, …). Two rules that cost an afternoon each:

* **Do not `import` Haxe classes.** In HScript an `import` is a *file* import: it tries to
  load `assets/…/Class.hx` and fails. Use the globals.
* **Anything you hide or create must be put back in `destroy()`.** `tools/validate_mod.py`
  checks the cutscene scripts for `camHUD.visible = true` and `FlxG.cameras.remove(cam)`;
  a missing line means the player finishes the cutscene with no HUD or a leaked camera.

Two more traps that shipped a crash in 3.3.0 — both are now enforced by the validator, because
they are invisible until the text is actually drawn:

* **Never assign `borderStyle` a number.** `FlxTextBorderStyle` is a *real* enum in flixel (it
  has a parameterised `SHADOW_XY` case) and `FlxText.regenGraphic()` switches on it. Writing
  `t.borderStyle = 2` from HScript leaves the field holding a non-enum value, and that switch
  throws **Null Object Reference** the first time the text draws. Put a dark band behind the
  text instead — that is what the captions and the cutscene panels do now.
* **`FlxTypeText.start()` takes only a delay.** The string to type comes from the constructor or
  `resetText()`; whatever `_finalText` already holds is what gets typed. `start("hello", 0.02)`
  types nothing, forever, and looks like "the dialogue is broken" rather than a bug.

## Ideas that fit well

* New story event functions in `data/scripts/trollge_song_behavior.hx` (add them to the event list in
  `tools/song_layout.py` so the charts and audio stingers pick them up).
* More poses in `tools/trollge_art.py` — the pose library is a list, adding a pose automatically adds atlas frames.
* Better backdrops/horror grading in `tools/make_art.py`.
* A fourth difficulty (e.g. `erect`) — add it to `L.DIFFICULTIES` and `DIFFICULTY_STRIDE` in `tools/song_layout.py`;
  `tools/make_chart.py` writes a chart per entry and `meta.json` follows.
* A second death variant per song — `GameOverSubstate.script` accepts a cutscene script; the four
  `music/gameOver*` / `sounds/gameOver*` files are already themed.
* A mid-song cutscene — `PlayState.startCutscene("midsong-", ...)` picks up
  `songs/<song>/midsong-cutscene.hx` if you want to interrupt a song.
* More rhythm cells — add one to `CELLS` in `tools/song_layout.py` and reference it from a song's `cells` list.

## Reporting bugs

Use the issue templates. For crashes, attach the engine log and say **which song, which difficulty and roughly
which timestamp** — the story events are time-based, so "right after the 32 s jumpscare" is genuinely useful.
