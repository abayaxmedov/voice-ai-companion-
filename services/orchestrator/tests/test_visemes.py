import unittest

from companion_core.pipeline.visemes import (
    generate_viseme_timeline,
    visemes_from_alignment,
    visemes_from_text,
)


class VisemesFromTextTest(unittest.TestCase):
    def test_vowels_and_consonants_map_to_expected_classes(self) -> None:
        frames = visemes_from_text("bola", duration_ms=None)
        names = [f.name for f in frames]
        self.assertEqual(names[0], "PP")  # b
        self.assertIn("O", names)  # o
        self.assertIn("nn", names)  # l
        self.assertIn("aa", names)  # a
        self.assertEqual(names[-1], "sil")

    def test_uzbek_digraphs_win_over_single_letters(self) -> None:
        sh = [f.name for f in visemes_from_text("shahar", None)]
        self.assertEqual(sh[0], "CH")  # sh -> ʃ
        ou = [f.name for f in visemes_from_text("o'zbek", None)]
        self.assertEqual(ou[0], "O")  # oʻ single unit

    def test_ng_is_single_unit(self) -> None:
        # "singil": s-i-ng-i-l -> SS I kk I nn
        names = [f.name for f in visemes_from_text("singil", None)]
        self.assertEqual(names[:5], ["SS", "I", "kk", "I", "nn"])

    def test_timeline_scales_to_duration(self) -> None:
        short = visemes_from_text("salom dunyo", duration_ms=600)
        long = visemes_from_text("salom dunyo", duration_ms=2000)
        self.assertLess(short[-1].time_ms, long[-1].time_ms)
        self.assertTrue(all(f.time_ms >= 0 for f in long))
        times = [f.time_ms for f in long]
        self.assertEqual(times, sorted(times))

    def test_empty_and_symbol_only_text(self) -> None:
        self.assertEqual(visemes_from_text("", 1000), ())
        self.assertEqual(visemes_from_text("### |", 1000), ())


class VisemesFromAlignmentTest(unittest.TestCase):
    def test_alignment_produces_real_timestamps(self) -> None:
        alignment = {
            "characters": ["s", "a", "l", "o", "m"],
            "character_start_times_seconds": [0.00, 0.08, 0.20, 0.27, 0.40],
            "character_end_times_seconds": [0.08, 0.20, 0.27, 0.40, 0.55],
        }
        frames = visemes_from_alignment(alignment)
        names = [f.name for f in frames]
        self.assertEqual(names[:5], ["SS", "aa", "nn", "O", "PP"])
        self.assertEqual(frames[0].time_ms, 0)
        self.assertEqual(frames[1].time_ms, 80)
        self.assertEqual(frames[-1].name, "sil")
        self.assertEqual(frames[-1].time_ms, 550)

    def test_alignment_digraph_spans_two_characters(self) -> None:
        alignment = {
            "characters": ["s", "h", "u"],
            "character_start_times_seconds": [0.0, 0.05, 0.12],
            "character_end_times_seconds": [0.05, 0.12, 0.30],
        }
        frames = visemes_from_alignment(alignment)
        self.assertEqual(frames[0].name, "CH")
        self.assertEqual(frames[1].name, "U")
        self.assertEqual(frames[1].time_ms, 120)

    def test_broken_alignment_falls_back_to_text(self) -> None:
        frames = generate_viseme_timeline(
            "salom", 900, alignment={"characters": ["s"], "character_start_times_seconds": []}
        )
        self.assertGreaterEqual(len(frames), 3)


if __name__ == "__main__":
    unittest.main()
