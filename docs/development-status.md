# Unreleased development status

This work is not an engine-verified release. No Codename Engine runtime, GLSL
compiler, or playback/listening test was available in this environment.

## Checks run on this checkout

- `python3 tools/validate_mod.py`: 2368 checks, 0 errors, 0 warnings.
- `python3 tools/audit_songs.py --strict`: all metrics inside target windows.
- `python3 tools/mix_report.py --strict`: all five melody/bass energy ratios
  above 1.0, crest factors in range.
- `python3 tools/melody_report.py --strict`: all 30 gates clear.
- `python3 tools/dread_report.py --strict`: dread ladder within its tolerance.
- `python3 tools/test_shader_validation.py`: unsupported and wrong-camera
  sampling mutations rejected; current CRT accepted.
- `python3 tools/check_freeplay_zip.py`: built archive passes old/new path and
  literal/rewrite models. A simulated path-like library name falls back to a
  scan, whose engine ordering is not guaranteed.

These are measurements and static models, not proof that the songs sound good,
the shaders compile on a user's GPU, or Freeplay opens on an engine build.

## Measured change

Using `mix_report.py` on the actual pre-change and current The Incident
instrumentals, energy below 250 Hz fell from 80.9% to 38.8%; energy from
250–2000 Hz rose from 9.6% to 50.3%. This band's energy is not the same thing
as perceived melody intelligibility. Crest factor moved from 13.6 to 13.8 dB.
The FFT measurement here uses channel-wise one-second windows; other reports
use different windows and therefore yield different percentages.

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
- Version/tag 3.8.0 and release assets have **not** been published. Do not call
  this finished until the engine and owner checks above are complete.
