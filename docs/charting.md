# How a Friday Night Funkin' song is actually built

…and what these five songs do to match it. Everything below was checked against
the engine source (`CodenameCrew/CodenameEngine`, `main`) and the base-game song
documentation, not against memory. Where a claim is engine behaviour it names the
file that proves it.

## 1. What a song *is* in the engine

### Folder, internal name, freeplay key

A song is a folder whose name **is** the song's internal name:

```
songs/<internal-name>/
    song/Inst.ogg          instrumental
    song/Voices.ogg        the characters' vocals
    charts/easy.json       one chart per difficulty
    charts/normal.json
    charts/hard.json
    meta.json              display name, BPM, icon, difficulties, …
    events.json            (Codename) global events file
```

`Chart.hx` forces `data.name = songName` when the meta is loaded, so the folder
name, the meta name and the key freeplay/story use are the same string. The base
game's folders are lowercase, hyphenated and short — `bopeebo`, `spookeez`,
`south`, `satin-panties`, `high`, `milf`, `cocoa`, `winter-horrorland`,
`lit-up`, `monster` — never `Title_Case_With_Underscores`.

### Audio paths (Codename)

`Paths.inst` and `Paths.voices` (`source/funkin/backend/assets/Paths.hx`):

```haxe
voices(song, difficulty, suffix) =
    exists('songs/$song/song/Voices$suffix-$difficulty') ? that
  : 'songs/$song/song/Voices$suffix'
```

so `Voices.ogg` on its own covers **every** difficulty, and a per-difficulty or
per-character variant only needs the suffix appended. `StrumLine` loads its own
vocals only when the strum line has a `vocalsSuffix` *and* that file exists;
otherwise it recycles a silent `FlxSound`.

`PlayState` gates the main vocal track on the meta flag
(`PlayState.hx:1219-1224`): `if (SONG.meta.needsVoices && Assets.exists(vocalsPath))`.
With `needsVoices: false` — or with no `Voices.ogg` — the song plays with **no
singing at all**: the characters mouth the lyrics silently. That is the single
most obvious "this is not a FNF song" tell.

### `meta.json`

The fields the engine actually reads (`ChartMetaData` in
`source/funkin/backend/chart/ChartData.hx`):

| Field | Meaning |
| --- | --- |
| `displayName` | the name freeplay shows |
| `bpm`, `beatsPerMeasure`, `stepsPerBeat` | timing grid (4 / 4 in every base song) |
| `difficulties` | which `charts/<name>.json` files exist, in menu order |
| `icon`, `color` | health-bar icon and bar colour |
| `coopAllowed`, `opponentModeAllowed` | mode support |
| `needsVoices` | load `Voices.ogg` |
| `instSuffix`, `vocalsSuffix` | alternate audio takes |
| `customValues` | anything the mod wants (`scareTier`, `songKey`, …) |

If `difficulties` is empty the engine fills it from the JSON files in `charts/`,
and when there are exactly three it sorts them into **easy / normal / hard**.

### Charts

Codename charts are strum-line native:

```json
{ "stage": "trollge", "scrollSpeed": 2.25, "chartVersion": "1.6.0",
  "codenameChart": true, "noteTypes": ["corrupt"], "bookmarks": [],
  "strumLines": [
    { "position": "dad", "type": 0, "characters": ["trollge_final"],
      "keyCount": 4, "notes": [{ "time": 1142.857, "id": 0, "type": 0, "sLen": 0 }] }
  ] }
```

There is **no `sections` array** in `ChartData` — the editor derives 16-step
sections from the notes, and a section's `who sings this` comes from which strum
line the note sits in. The legacy FNF format expresses the same thing with
`sectionNotes` + `mustHitSection` (four lanes per character, sides swapped when
`mustHitSection` is true).

The convention both formats encode:

* **one bar (16 steps) belongs to exactly one character**, and phrase blocks of
  2–4 bars alternate: opponent → player → opponent → player;
* the opponent opens the song and the **player sings the last phrase**;
* rhythms are 16th-note cells, not a constant stream: week 1 is halves and
  quarters, week 7 adds eighths and short 16th runs;
* sustains mark the end of a phrase;
* hard-mode extras (doubled lanes) arrive only in the hardest charts.

### Numbers the base game keeps to

| Song | Length | BPM | Key | Notes (EZ / NM / HARD) | Scroll |
| --- | --- | --- | --- | --- | --- |
| Bopeebo | 1:21 | 100 | E♭ major | 44 / 51 / 62 | 1.2 |
| Roses | 1:32 | 120 | C minor | 127 / 191 / 234 | 1.6–1.8 |
| South | 1:28 | 165 | B minor | 103 / 156 / 175 | – |
| Blammed | 1:46 | 165 | F# minor | 115 / 147 / 196 | – |
| Guns | 2:20 | 185 | E minor | 247 / 388 / 456 | 2.0–2.5 |
| Lit Up | 1:54 | 176 | E minor | 301 / 394 / 468 | – |

So: **1:20–2:20 long, ≤ 190 BPM, ≈0.5–4 notes/second on hard, scroll 1.2–2.6,
three difficulties whose note counts sit near 1 : 1.5 : 2.**

## 2. Where this pack used to deviate (measured, not guessed)

| Problem | Before | Now |
| --- | --- | --- |
| Folder / internal names | `getting_dark`, `dont_look_back`, `super_scary`, `the_incident` | `getting-dark`, `dont-look-back`, `super-scary`, `the-incident` |
| Difficulties | `easy`, `normal` (two) | `easy`, `normal`, `hard` |
| Note density (hard) | 2.5 → 8.5 notes/s — the last two songs were above anything in the base game | 1.5 → 3.8 notes/s |
| Structure | every section note-filled, no intro, no breakdown | intro, verse/build/drop blocks, two breakdowns, finale |
| Section sides | notes of both characters inside one section (they interleaved within a bar) | one character per bar, phrase blocks alternate |
| Length | 1:32 → 1:44, finale the *shortest* | 1:43 → 1:52, finale the longest |
| Vocals | none shipped (`needsVoices: false`) | `song/Voices.ogg` per song, `needsVoices: true` |
| Stated key | none | D minor, C minor, C# minor, B minor, A minor |
| Scroll speed | 1.0 for every difficulty | 1.25 → 2.45, rising per song and per difficulty |

## 3. What ships now

| # | Song | Folder | Key | BPM | Length | Phrase blocks | EZ / NM / HARD notes | Scroll EZ / NM / HARD |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Trolling | `trolling` | D minor | 140 | 1:44.0 | 16 (60 bars) | 92 / 110 / 152 | 1.25 / 1.45 / 1.60 |
| 2 | It's Getting Dark | `getting-dark` | C minor | 150 | 1:43.6 | 20 (64 bars) | 108 / 128 / 176 | 1.50 / 1.70 / 1.85 |
| 3 | Don't Look Back | `dont-look-back` | C# minor | 152 | 1:51.9 | 20 (70 bars) | 153 / 185 / 266 | 1.70 / 1.90 / 2.05 |
| 4 | Super Scary Trollge | `super-scary` | B minor | 160 | 1:43.5 | 20 (68 bars) | 162 / 201 / 308 | 1.90 / 2.10 / 2.25 |
| 5 | The Incident | `the-incident` | A minor | 170 | 1:48.9 | 28 (76 bars) | 206 / 257 / 378 | 2.10 / 2.30 / 2.45 |

Density on hard runs **1.46 → 1.70 → 2.38 → 2.98 → 3.47 notes/second**, inside the
base game's window and still a real ladder (the finale is 2.4× song 1).

### Rhythm cells

`tools/song_layout.py` writes every bar as one of seven 16th-note cells; each song
picks a cycle of them, so a riff repeats as a phrase rather than as a loop:

| Cell | Offsets (16ths) | Used by |
| --- | --- | --- |
| `HALF` | 0, 8 | song 1, every breakdown |
| `QUARTERS` | 0, 4, 8, 12 | songs 1–5 |
| `QUARTERS_SYNC` | 0, 3, 8, 11 | song 3 |
| `CLAP` | 0, 6, 8, 14 | song 2 |
| `TRAP` | 0, 4, 8, 10, 12 | songs 4–5 |
| `DRIVE` | 0, 2, 4, 8, 10, 12 | songs 4–5 |
| `SKITTER` | 0, 3, 6, 8, 11, 14 | song 5 |

### Phrase blocks and sides

A song defines `section_measures` — the bars of each phrase block — and the blocks
alternate `opponent, player, opponent, …` starting with the opponent and ending
with the player. Vexing consequence, and the point of the whole exercise: in the
editor every bar becomes a 16-step section owned by exactly one character, which
is what the base game looks like.

Breakdown blocks are sparse (`HALF`) in the chart **and** drop their drums in the
audio, because both read the same `section_roles()` list.

### Difficulties

`notes(song, difficulty)` filters each phrase: hard keeps everything, normal keeps
two notes in three, easy every second note (and always the phrase's last note, so
phrases still land). Sustains and the finale's doubled lanes exist on hard only —
an easy chart with two-lane chords is not easy.

### Vocals

`render_vocals()` renders the same note list through a formant synth: the opponent
sings his blocks an octave down with a growl and a dark vowel, the player sings his
an octave above with a bright vowel, and the two are panned apart. The result is
`song/Voices.ogg`, exactly the length of `Inst.ogg` and mastered ~6 dB under it.


### The hook: why the chart is the melody

The base game's charts follow the vocals, and the vocals are a hook — four notes you
can hum. `tools/song_layout.py` models that directly: every song defines `hooks`,
two four-lane figures. The opponent sings the call, the player answers with the
other figure, and every fourth exchange the answer comes back inverted. Because
`note_pitch()` turns the lane into a scale degree and the chord changes every bar,
the same four lanes never sound twice the same way. The chart and both audio files
are generated from those lanes, so the hook the player hears is the hook the player
hits, and every phrase cadences on the root.

That is also why the difficulty filters can be mechanical: easy/normal/hard are
subsets of the same melody, not three different songs.

### Cutscenes

Codename finds them without being asked (`PlayState.createPost` →
`startCutscene("", cutscene)`; `PlayState` → `startCutscene("end-", endCutscene,
nextSong)`), so a song cutscene is just `songs/<song>/cutscene.hx` and
`songs/<song>/cutscene-end.hx`. Both are scripted cutscenes: the substate sets
`persistentUpdate` on the game, so the stage keeps running underneath while the
script draws on its own camera.

This pack generates those scripts (`tools/make_cutscenes.py`) rather than
hand-writing them, because the text lives next to the song data in
`tools/song_layout.py`. The scripts only touch APIs the engine itself uses —
`FlxCamera` + camera lists (DialogueCutscene), `FlxSprite.loadGraphic` (every stage
script), `FlxTypeText` with `font = Paths.font("vcr.ttf")` (DialogueBox.hx) and
`FlxTimer` (guns' cutscene) — and every class comes from the engine's script
globals (`Script.hx` default imports), not from `import` statements, which in
HScript try to load a `.hx` *file* instead.

### In-song captions

Cutscenes only run before and after a song, so anything that has to land *during*
play has to be a chart event. `song_layout.py` carries `"captions": [(seconds, text)]`
per song; `story_events()` emits them as `HScript Call` events whose first argument is
the function name, and `trollgeCaption()` in `trollge_song_behavior.hx` types them onto
`camHUD` with `FlxTypeText` — fade in 0.3 s, hold 3.4 s, fade out 0.9 s, destroyed in
`destroy()` so a mid-song quit cannot leak the text.

Two constraints come from the engine, both found the hard way. `PlayState.executeEvent`
splits the `HScript Call` parameter string on commas, so caption text has to be rejoined
from its arguments (and must not contain a comma it wants to keep literal). And a
`FlxTypeText` on the HUD camera keeps typing through a pause unless it is added to the
same camera list the subtitles use — this one is, like DialogueBox.

### Cutscenes

`tools/validate_mod.py` (structural, runs on every push):

* every song folder is lowercase-hyphenated;
* `meta.json` ships exactly the base game's three difficulties, `needsVoices: true`,
  a `songKey`, and a `scrollSpeed` inside 1.1–2.6 that matches the layout;
* `song/Voices.ogg` and `song/Inst.ogg` exist, share a sample rate and a length
  (within 150 ms);
* every chart has the note count the layout says, no bar mixes the two characters,
  and every bar of the song has notes;
* every `HScript Call` in every chart resolves to a function that exists in the
  song/pack scripts, and every caption in the layout appears in the matching
  `events.json` with the same time. The death theme is checked too: `music/gameOver.ogg`
  + `gameOver.ini` + both game-over sounds must exist at sane lengths, because a
  missing file silently falls back to the base game's;
* **and the shipped zip is checked, not assumed** — `package_mod.py`'s include list
  has to cover every top-level folder in `mods/TrollgeMod`. That check exists because
  the include list was missing `shaders/` and `music/`: the release zip shipped
  without the VHS grade and would have shipped without the death theme, and nothing
  in the game says a word when a shader file is absent.

`tools/audit_songs.py --strict` (measured, runs on every push):

* hard-chart density 1–6 notes/s, off-beat share ≤ 90 %, same-lane run ≤ 3;
* one character per bar (0 mixed bars), phrase runs printed per song;
* the vocal track covers ≥ 90 % of the chart's notes and peaks below −0.5 dBFS;
* tempo, hard note count, notes/second and scroll speed all rise song by song.
