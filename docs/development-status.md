# Development status

The v4.0.0 testing release includes menu, battle and earlier soundtrack changes beyond v3.9.0; it is not engine-verified. The v4.1.0-rc1 testing release includes the later soundtrack and visual changes. No Codename Engine runtime, GPU rendering test, or playback/listening test was available in this environment. A standalone GLSL compiler was used with a minimal preamble.

## Checks run on this checkout

- `python3 tools/validate_mod.py`: 2387 checks, 0 errors, 0 warnings.
- `python3 tools/audit_songs.py --strict`: all metrics inside target windows.
- `python3 tools/mix_report.py --strict`: all five melody/bass energy ratios
  above 1.0, crest factors in range.
- `python3 tools/melody_report.py --strict`: all 30 gates clear.
- `python3 tools/test_music.py`: music generation regression tests.
- `python3 tools/check_stem_mix.py`: decoded equal-gain stem-sum peak estimates.
- `python3 tools/dread_report.py --strict`: dread ladder within its tolerance.
- `python3 tools/test_battle_visuals.py`: lane colours, note contrast, frame-edge clipping, hold seams and HUD effect routing.
- `python3 tools/test_polish.py`: character wiring, chart timing, note contrast, countdown bounds and seeded texture checks pass.
- `python3 tools/test_stage_bounds.py`: 800 projected battle frames pass; minimum modelled margin 48.8 px at static zooms 0.95 and 1.05.
- `python3 tools/test_glsl_compile.py`: both shaders compile for desktop GLSL 330/410 and ES 300 with a minimal Flixel-compatible preamble.
- `python3 tools/test_shader_validation.py`: unsupported and wrong-camera
  sampling mutations rejected; current CRT accepted.
- `python3 tools/check_freeplay_zip.py`: built archive passes old/new path and
  literal/rewrite models. A simulated path-like library name falls back to a
  scan, whose engine ordering is not guaranteed.

These are measurements and static models, not proof that the songs sound good,
the shaders compile on a user's GPU, or Freeplay opens on an engine build.

## Music changes

The 4.1.0-rc1 arrangement adds recorded upright piano and new harmonised
figures. The latest revision gives each song a distinct three-note answering
gesture in vocal rests, ties dynamic landmarks to chart sections, shapes the kit
and bass across phrases, and varies vocal articulation and expression without
moving chart onsets or shortening written holds. The existing chart melodies
and song lengths remain unchanged. Five equal-gain breakdown excerpts are in
`previews/music/`. None has been auditioned here or tested in-engine.

The current work-in-progress rebuild replaces song-stem formant synthesis with
pitched, looped CC0 recorded singing, while keeping existing authored chart
onsets and the lower opponent register. It reduces competing instrumental lead,
stereo widening, hiss and vocal boost. Both characters use the same source,
not official character recordings. A listening test and in-engine test are still
needed before judging character, mix and playability.

The rendered lead and vocals now preserve the written semitone instead of
snapping near chord tones. Harmony is scored against the notes remaining after
hard-chart thinning, in their correct bars; simultaneous doubled hands are
counted once. Suspensions retain the fifth, pad extensions are actual diatonic
ninths, and the glitch bass gates a stable root instead of jumping randomly to
tritones. The opening song's recurring phrases were re-timed so their hooks
survive thinning. `test_music.py` covers these properties and the report's
onset accounting. Section roles now align to chart bars, unison hands produce
one sung onset, drones use the song tonic, and a linked gain curve protects
the decoded equal-gain sum of the instrumental and voices. `melody_report.py` now assesses the chart rather than the
unthinned notation, so its results are not comparable to older tables.

These corrections are not a listening test. Scary/catchy sound and balance
still need to be assessed with the actual instrumental and voices together.

## Source findings and remaining work

- The current Codename `cne-openfl` dependency (commit
  `74f5f97242fa31150d525559e514743398abd8f1`) defaults to GLSL 300 es on
  web/mobile, 410 core on macOS and 330 core elsewhere. Its default source
  compatibility pass translates `gl_FragColor` and `texture2D`. This is not a
  driver compilation test, and other engine builds may use other dependencies.
- CRT warping uses camera coordinates and both passes preserve premultiplied transparency. Stage teardown preserves unrelated filters. The standalone compiler does not reproduce the full OpenFL pipeline;
  shader initialization, filter survival and the actual rendered frame must be
  checked in-engine, including a machine without shader support.
- The five backgrounds and menu were visually reviewed. The last backdrop was
  regenerated with a clearer, seeded grade; battle HUD, all scare payloads and
  character animation still need real in-game artistic and accessibility review.
- Listen to all songs with the owner; play each song in Story and Freeplay on
  target Codename versions (zip and extracted installs). Confirm exact Freeplay
  ordering, shader behavior, chart sync, cutscenes and ending.
- Please report listening and engine results before treating this testing build as finished.

## Battle polish

All five Trollge character XMLs now load their shared behavior extension. Shader
event pulses follow `Conductor.songPosition` rather than wall time, and ambient
random chances use the percentage units documented in the engine's FlxRandom.
The finale note skin retains distinct lane colours; READY fits its canvas; the
inversion is shorter, less opaque, and shows a negative of the room. Background
and noteskin textures are seeded. These changes have not been tested in-engine.

## Menu and battle pass in v4.1.0-rc1

The menu was rebuilt again to follow the user-supplied cinematic reference:
a generated Trollge hallway scene, distressed title and compact left-side
navigation. The `LIB_TrollgeMod` state script repositions native menu items;
the fallback is the stock centred layout. Countdown badges and the health-bar
casing retain the earlier console language. The menu and HUD previews are
approximations. Research and limitations are in [ui-research.md](ui-research.md).
The battle stage has fixed contact shadows and bounded camera impulses;
downbeat shake replaces constant beat shake. Scripted event shakes leave the
HUD still. Shipped songs use their existing vocal stem instead of doubled hit
samples. Real engine testing is
still needed for menu states, animated character feet, camera movement, shader
effects, HUD readability and the audio mix. Scripted flashes and scares remain.

## Visual readability pass in v4.1.0-rc1

Arrow scratch masks now affect the scratches only; note/receptor contrast and
lane colours remain distinct through the four skins. Sustain bodies tile at
matching edges, with compatible caps. HUD CRT motion and edge darkening are
disabled; scare overlays and flashes use the game camera instead. The two
game-camera vignettes and VHS contrast are restrained to retain shadow detail.
`battle_preview.png` is a static atlas composite on cropped backdrops, not a
render of the game, shaders, splash animation, camera or timing. The grade
preview approximates VHS alone, not the subsequent CRT. Actual effects coverage,
GPU compatibility, holds and reading under motion remain to be play-tested.
The packaged mod now includes CC0 third-party audio source notices.
