#!/usr/bin/env python3
"""Regression tests for the actual chart melody and its accompaniment."""
import unittest
from collections import Counter

import numpy as np
import make_audio as A
import melody_report as M
import song_layout as L


class MusicTests(unittest.TestCase):
    def test_written_pitches_are_preserved_for_all_chart_notes(self):
        for song in L.SONGS:
            for n in L.notes(song):
                if n.get("semi") is not None:
                    self.assertEqual(L.note_pitch(song, n["measure"], n["id"], semi=n["semi"]),
                                     song["tonic"] + 12 + n["semi"])
                    self.assertEqual(L.note_pitch(song, n["measure"], n["id"], octave_shift=-1, semi=n["semi"]),
                                     song["tonic"] + n["semi"])

    def test_harmoniser_uses_bar_containing_played_note(self):
        for song in L.SONGS:
            expected = {}
            layout = L.sections(song)
            starts = [round((sec["time"] - L.measure_time(song, 0)) /
                            (L.measure(song) * 1000)) for sec in layout]
            seen = set()
            for note in L.notes(song):
                key = (round(note["time"], 3), note["side"], note["semi"])
                if key in seen:
                    continue
                seen.add(key)
                block = max(i for i, start in enumerate(starts) if start <= note["measure"])
                offset = round((note["time"] - L.measure_time(song, note["measure"])) /
                               (L.step(song) * 1000)) % 16
                expected.setdefault((block, note["measure"] - starts[block]), []).append((note["semi"], offset))
            self.assertEqual(L._melody_bars(song), expected)
            # Include late-bar notes, which the former rounding misassigned.
            self.assertTrue(any(step >= 8 for values in expected.values() for _, step in values))

    def test_suspensions_keep_fifth_not_third(self):
        scale = L.SCALES["trolling"]
        chords = L.diatonic_triads(L.SONGS[0])
        self.assertEqual(chords[len(scale) * 2][1], [0, 2, 7])
        self.assertEqual(chords[len(scale) * 2 + 1][1], [0, 5, 7])

    def test_pad_add_nine_is_relative_to_chord_root(self):
        self.assertEqual(A.pad_voicing(60, [0, 3, 7], 4, 60, L.SCALES["getting-dark"]), [60, 63, 67, 74])
        self.assertEqual(A.pad_voicing(60, [0, 2, 7], 4, 60, L.SCALES["getting-dark"]), [60, 62, 67])
        self.assertEqual(A.pad_voicing(60, [0, 3, 7], 4, 60, L.SCALES["super-scary"]), [60, 63, 67, 73])

    def test_report_counts_heard_onsets_not_unthinned_or_doubled_hands(self):
        for song in L.SONGS:
            heard = {(round(n["time"], 3), n["side"], n["semi"]) for n in L.notes(song)
                     if n.get("semi") is not None}
            measured = Counter((round(n["time"], 3), n["side"], n["semi"])
                               for line in M.melody_lines(song) for n in line)
            self.assertEqual(set(measured), heard)
            self.assertTrue(all(count == 1 for count in measured.values()))

    def test_section_roles_are_not_shifted_by_the_song_lead_in(self):
        for song in L.SONGS:
            mapping = L.measure_roles(song)
            pos = 0
            for count, role in zip(song["section_measures"], L.section_roles(song)):
                self.assertTrue(all(mapping[bar] == role for bar in range(pos, pos + count)))
                pos += count
            self.assertEqual(len(mapping), L.measures(song))

    def test_unison_hands_are_one_sung_onset(self):
        for song in L.SONGS:
            notes = list(L.melodic_onsets(song))
            self.assertEqual(len(notes), M.analyse(song)["notes"])

    def test_linked_stem_gain_prevents_sum_overload(self):
        n = A.SR // 5
        inst = np.zeros(n)
        voice = np.zeros(n)
        inst[n // 2:n // 2 + 100] = .8
        voice[n // 2:n // 2 + 100] = .7
        gain = A.linked_mix_gain(inst, inst, voice, voice)
        self.assertLessEqual(np.max(np.abs((inst + voice) * gain)), .85 + 1e-9)
        self.assertLess(gain[n // 2], 1.0)
        self.assertEqual(gain[0], 1.0)

    def test_recorded_voice_notes_have_pitch_and_click_free_edges(self):
        # Check both registers and a long sustain, without claiming that any
        # spectral measurement can substitute for listening.
        for midi in (53, 57, 65, 69, 76, 84, 88):
            x = A.sampled_voice_note(midi, .8, dark=midi < 65)
            self.assertTrue(np.isfinite(x).all())
            self.assertAlmostEqual(x[0], 0.0)
            self.assertAlmostEqual(x[-1], 0.0)
            y = x[int(.12 * A.SR):int(.4 * A.SR)]
            size = 2 ** int(np.ceil(np.log2(len(y) * 2)))
            corr = np.fft.irfft(abs(np.fft.rfft(y, size)) ** 2)
            expected = A.midi_to_hz(midi)
            lo = int(A.SR / (expected * 1.15))
            hi = int(A.SR / (expected * .85))
            measured = A.SR / (lo + np.argmax(corr[lo:hi]))
            self.assertLess(abs(measured / expected - 1), .035)

    def test_glitch_bass_does_not_jump_to_tritone(self):
        audio = A.bass_for("glitch", 45, .7, 6)
        self.assertTrue(np.isfinite(audio).all())
        # Harmonics of the 110 Hz root should dominate a former tritone jump.
        spectrum = np.abs(np.fft.rfft(audio * np.hanning(len(audio))))
        freq = np.fft.rfftfreq(len(audio), 1 / A.SR)
        def band(f):
            return np.max(spectrum[np.abs(freq - f) < 4])
        self.assertGreater(band(110), 10 * band(110 * 2 ** .5))


if __name__ == "__main__":
    unittest.main()
