# Music research and implementation notes

These are selected sources, not a complete survey. They informed independent
changes to the existing generators. The current vocals use the separately
credited recorded vowel described below; no external melodies were copied.

- [Zoe Sones, Music and Horror: What Makes Music Sound Scary](https://www.premiumbeat.com/blog/what-makes-music-sound-scary/): contrast, dissonance, low drones and pulsating rhythms. The arrangements already use quiet/loud section roles, horror layers and chart-timed events; v3.8 corrects which chart bars receive those roles and tunes the continuous drone to the song's tonic. It preserves intentionally chromatic written pitches rather than silently snapping them.
- [Northern Film Orchestra, 5 Tips for Writing Horror Music](https://www.northernfilmorchestra.com/post/film-composers-5-tips-for-writing-horror-music): dissonant intervals, unfamiliar treatments of familiar sounds and space. The five pieces retain different instrumental palettes and scale colours; the glitch bass no longer makes uncontrolled random tritone jumps that can fight the melody.
- [Winifred Phillips, The Hook in Game Music](https://winifredphillips.wpcomstaging.com/2020/06/16/game-composers-and-the-importance-of-themes-the-hook-in-game-music-pt-1/): recurring hooks, contrast and variation. The tracks use authored phrases and call/response forms, and Trolling's hook was re-timed to survive the chart-spacing filter. Repetition counts are a structural diagnostic, not a catchiness score.
- [Jazzerator procedural music generator](https://github.com/apzeedyk/procedural-game-music): an example of using separate forms, harmony, melody and arrangement rules. This project keeps its own existing phrase notation and generator; it does not import that implementation. Chords here are selected against the actual thinned hard-chart melody and its correct bar, and sung unison hands are rendered once.
- [Välimäki and Huovilainen, New Approaches to Digital Subtractive Synthesis](https://quod.lib.umich.edu/i/icmc/bbp2372.2005.042/1/--new-approaches-to-digital-subtractive-synthesis?page=root%3Bsize%3D200%3Bview%3Dtext): sampled sharp-edged oscillators alias; band-limited oscillators can reduce it. The existing saw and square generators are not band-limited, so aliasing remains a known limitation. A blanket oscillator replacement was not made without listening and comparison.
- [iZotope, mastering questions: intersample peaks](https://www.izotope.com/en/learn/we-are-listening-your-mastering-questions-answered.html): decoded/converted audio can peak between samples and needs headroom. The new linked gain controls the *sum* of both song stems; the packaged Vorbis files are decoded and checked with a 4× Catmull-Rom estimate. This is not an ITU true-peak meter, and engine gain and additional sound effects are not modelled.

Every track still needs a human listening test, including vocals and instrumental
together, and gameplay needs testing in the actual Codename Engine build.

## Recorded voice and redistribution

[Bart Massey's voice-note.wav](https://github.com/pdx-cs-sound/wavs) is a
single sung note, identified in that repository as CC0. Both characters use
retuned versions of this one recording, with crossfaded looping and short
note envelopes; it is not an official BF or Trollge recording. The vocal stem
is less aggressively boosted, with less artificial top end and reverb; the
instrumental's chart-following lead and excessive stereo width were reduced.
These are production decisions, not proof of quality or character accuracy.

The [NyxTheShield BF soundfont](https://github.com/NyxTheShield/FNFSoundfonts)
claims Apache-2.0, but says the samples are ripped from the original game.
The [Funkin assets license](https://github.com/FunkinCrew/funkin.assets/blob/main/LICENSE.md)
reserves the game's audio content, distinct from the code license. Those samples
were therefore not incorporated.

The instrumental audit's minimum air and width thresholds were adjusted for the
intentional darker, narrower mix; it still checks air, width and side/mid energy.
The melody-band mix report now measures the decoded equal-gain **sum** of both
stems instead of treating the quietened instrumental lead as the whole melody.
It does not model the engine muting vocals on misses or its actual gain settings.

## The Trollge Files reference and 4.1.0-rc1 arrangement

The user requested *The Trollge Files / The Blueballs Incident* as a reference.
The [track listing](https://fridaynightfunking.fandom.com/wiki/The_Trollge_Files)
credits EZHALT for **Sadness**, **Rage**, **Incident** and **Redemption** and
lists different tempos and minor keys; the story's emotional framing moves
between sadness, rage, conflict and redemption, not simply escalating noise.
The [character notes](https://fridaynightfunking.fandom.com/wiki/The_Trollge_Files/Characters)
also describe how the credits move between ideas from those songs. These sources
support a narrative-contrast direction, not an assertion that every track uses
a particular instrument.

For analysis only, instrumentals in the publicly accessible
[Dxgamer7405/Trollge-Files repository](https://github.com/Dxgamer7405/Trollge-Files)
were inspected using non-overlapping four-second RMS windows, without a
listening test. Approximate 10th-to-90th percentile ranges were **11.5 dB**
for Sadness, **11.6 dB** for Rage, **5.4 dB** for Incident and **11.2 dB**
for Redemption; these are dynamic measurements, not measures of emotion or
proof of an exact sonic match. No reference audio or melody is shipped or
reproduced.

Our independent arrangement uses new chord-based piano figures and answers,
section-aware register/velocity, different long-form rises and retreats per
song, and softer first-song endings. The existing authored charts and vocal
melodies remain unchanged. Seven [Meta Piano](https://github.com/facebookincubator/Meta-open-sound/tree/main/systems/instruments/meta-piano)
upright samples (CC0) are included in `audio_src/piano/`, retuned and
enveloped by the renderer. Listening and real gameplay are still necessary to
judge emotion, similarity, voice character and mix.

## Phrase-focused revision in 4.1.0-rc1

The next arrangement keeps the charted melodies and adds five distinct,
original three-note piano gestures. They are fitted to the local bar's chord
and placed only in sufficiently long vocal rests, with space for the piano's
release. Each song's dynamics now follow authored section boundaries instead
of equal time fractions; drums and bass have four-bar movement and a small
breath before major returns. Vocal tap lengths respond to the next note,
while authored holds and every chart-aligned onset are preserved. Phrase
contour, beat accent, note direction and story landmarks shape vocal intensity.
The two characters still use different pitches of the same CC0 vowel sample,
so this is not a substitute for separately recorded character performances.

These are compositional intentions, not a verified claim about emotional
impact. `previews/music/` contains equal-gain mixes around each breakdown;
they omit in-engine vocal muting, volume settings and event sound effects.
Listen to the complete songs and play them in Codename before judging the mix
or whether the new phrases feel right.
