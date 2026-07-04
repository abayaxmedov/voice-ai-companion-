import math
import unittest

from companion_core.pipeline.audio_mouth import CURVE_FPS, curves_from_pcm


def _tone(freq: float, seconds: float, rate: int, amp: float = 0.6) -> list[float]:
    return [amp * math.sin(2 * math.pi * freq * i / rate) for i in range(int(seconds * rate))]


def _silence(seconds: float, rate: int) -> list[float]:
    return [0.0] * int(seconds * rate)


def _noise(seconds: float, rate: int, amp: float = 0.4) -> list[float]:
    # Deterministik "shovqin" (yuqori chastotali): tez almashinuvchi belgi.
    return [amp * (1 if i % 2 == 0 else -1) for i in range(int(seconds * rate))]


class MouthCurvesTest(unittest.TestCase):
    RATE = 24000

    def test_speech_like_signal_produces_all_curves(self) -> None:
        samples = (
            _tone(220, 0.3, self.RATE)      # unli (past chastota)
            + _silence(0.2, self.RATE)      # pauza
            + _noise(0.25, self.RATE)       # frikativ (yuqori chastota)
        )
        curves = curves_from_pcm(samples, self.RATE)
        self.assertIsNotNone(curves)
        self.assertEqual(curves["fps"], CURVE_FPS)
        n = len(curves["energy"])
        for key in ("jaw", "close", "spread", "round"):
            self.assertEqual(len(curves[key]), n)
        self.assertTrue(all(0.0 <= v <= 1.0 for v in curves["jaw"]))

    def test_vowel_opens_jaw_and_silence_closes(self) -> None:
        samples = _tone(220, 0.4, self.RATE) + _silence(0.4, self.RATE)
        curves = curves_from_pcm(samples, self.RATE)
        frames = len(curves["jaw"])
        mid_vowel = curves["jaw"][frames // 4]
        late_silence = curves["close"][-2]
        self.assertGreater(mid_vowel, 0.3)
        self.assertGreater(late_silence, 0.5)

    def test_fricative_spreads_vowel_rounds(self) -> None:
        rate = self.RATE
        vowel = curves_from_pcm(_tone(220, 0.5, rate), rate)
        fric = curves_from_pcm(_noise(0.5, rate), rate)
        v_mid = len(vowel["round"]) // 2
        f_mid = len(fric["spread"]) // 2
        self.assertGreater(vowel["round"][v_mid], fric["round"][f_mid])
        self.assertGreater(fric["spread"][f_mid], vowel["spread"][v_mid])

    def test_too_short_audio_returns_none(self) -> None:
        self.assertIsNone(curves_from_pcm([0.1] * 10, self.RATE))


if __name__ == "__main__":
    unittest.main()
