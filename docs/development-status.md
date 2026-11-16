# v3.8.0 testing release status

This is a testing release, not an engine-verified release. No Codename Engine runtime, GLSL
compiler, or playback/listening test was available in this environment.

## Checks run on this checkout

- `python3 tools/validate_mod.py`: 2378 checks, 0 errors, 0 warnings.
- `python3 tools/audit_songs.py --strict`: all metrics inside target windows.
- `python3 tools/mix_report.py --strict`: all five melody/bass energy ratios
  above 1.0, crest factors in range.
- `python3 tools/melody_report.py --strict`: all 30 gates clear.
- `python3 tools/test_music.py`: music generation regression tests.
- `python3 tools/check_stem_mix.py`: decoded equal-gain stem-sum peak estimates.
- `python3 tools/dread_report.py --strict`: dread ladder within its tolerance.
- `python3 tools/test_polish.py`: character wiring, chart timing, note contrast, countdown bounds and seeded texture checks pass.
- `python3 tools/test_shader_validation.py`: unsupported and wrong-camera
  sampling mutations rejected; current CRT accepted.
- `python3 tools/check_freeplay_zip.py`: built archive passes old/new path and
  literal/rewrite models. A simulated path-like library name falls back to a
  scan, whose engine ordering is not guaranteed.

These are measurements and static models, not proof that the songs sound good,
the shaders compile on a user's GPU, or Freeplay opens on an engine build.

## Music changes

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
- CRT camera sampling now follows the engine's camera helper convention, but
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
