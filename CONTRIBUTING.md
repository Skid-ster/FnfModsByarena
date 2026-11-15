# Contributing to Super Scary Trollge

Thanks for wanting to help! This repo is a *generated* mod: charts, audio and art are all produced by the
scripts in `tools/`, so most contributions are a code change plus a regeneration.

## Ground rules

1. **Never hand-edit generated files.** These are outputs:
   * `mods/TrollgeMod/songs/*/charts/*.json`
   * `mods/TrollgeMod/songs/*/meta.json`, `events.json`
   * `mods/TrollgeMod/images/**`
   * `mods/TrollgeMod/songs/*/song/Inst.ogg`, `mods/TrollgeMod/sounds/*.ogg`
   * `docs/preview.png`, `docs/stages.png`, `docs/jumpscare.png`

   Edit the generator instead (`tools/song_layout.py`, `tools/trollge_art.py`, `tools/make_audio.py`,
   `tools/make_art.py`) and re-run it. CI fails if charts drift.
2. **Keep it Codename Engine compatible.** We target the Codename chart format (`chartVersion 1.6.0`,
   `codenameChart: true`) and HScript (`data/scripts/*.hx`). Psych Engine formats are not supported.
3. **Keep the scare tiers honest.** Song 1 ≈ 2/10, song 2 ≈ 4/10, song 3 ≈ 7/10. If you add a jumpscare to
   song 1, you have changed the design — say so in the PR.

## Workflow

```bash
pip install pillow numpy soundfile

# make your change, then rebuild whatever you touched
python3 tools/make_art.py      # only if you touched trollge_art.py / make_art.py
python3 tools/make_audio.py    # only if you touched song_layout.py / make_audio.py
python3 tools/make_chart.py    # if you touched song_layout.py (charts)

python3 tools/validate_mod.py  # must print VALIDATION PASSED
```

Commit the regenerated files together with the generator change, in one commit, e.g.:

```
feat(song3): denser final section

- song_layout: +2 spacing-1 sections in the last act
- regenerated charts + instrumental
```

## Ideas that fit well

* New story event functions in `data/scripts/trollge_song_behavior.hx` (add them to the event list in
  `tools/song_layout.py` so the charts and audio stingers pick them up).
* More poses in `tools/trollge_art.py` — the pose library is a list, adding a pose automatically adds atlas frames.
* Better backdrops/horror grading in `tools/make_art.py`.
* Extra difficulty (`hard`) — extend `tools/make_chart.py` and the `difficulties` list in `meta.json`.

## Reporting bugs

Use the issue templates. For crashes, attach the engine log and say **which song, which difficulty and roughly
which timestamp** — the story events are time-based, so "right after the 32 s jumpscare" is genuinely useful.
