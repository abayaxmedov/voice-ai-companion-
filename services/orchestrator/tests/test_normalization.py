from __future__ import annotations

import unittest

from companion_core.pipeline.normalization import (
    normalize_speech_text,
    number_to_uzbek,
    time_to_uzbek,
)


class NumberToUzbekTests(unittest.TestCase):
    def test_units(self) -> None:
        self.assertEqual(number_to_uzbek(0), "nol")
        self.assertEqual(number_to_uzbek(7), "yetti")

    def test_tens_and_hundreds(self) -> None:
        self.assertEqual(number_to_uzbek(30), "o'ttiz")
        self.assertEqual(number_to_uzbek(35), "o'ttiz besh")
        self.assertEqual(number_to_uzbek(100), "yuz")
        self.assertEqual(number_to_uzbek(245), "ikki yuz qirq besh")

    def test_thousands_and_millions(self) -> None:
        self.assertEqual(number_to_uzbek(12000), "o'n ikki ming")
        self.assertEqual(number_to_uzbek(2026), "ikki ming yigirma olti")
        self.assertEqual(number_to_uzbek(1_500_000), "bir million besh yuz ming")


class TimeToUzbekTests(unittest.TestCase):
    def test_tz_example_nine_thirty(self) -> None:
        self.assertEqual(time_to_uzbek(9, 30), "to'qqiz yarim")

    def test_full_hour(self) -> None:
        self.assertEqual(time_to_uzbek(9, 0), "soat to'qqiz")

    def test_other_minutes(self) -> None:
        self.assertEqual(time_to_uzbek(9, 35), "to'qqizu o'ttiz besh daqiqa")


class NormalizeSpeechTextTests(unittest.TestCase):
    def test_time_and_currency(self) -> None:
        result = normalize_speech_text("Uchrashuv 9:30 da, narxi 12000 so'm.")
        self.assertIn("to'qqiz yarim", result)
        self.assertIn("o'n ikki ming so'm", result)
        self.assertNotRegex(result, r"\d")

    def test_markdown_removed(self) -> None:
        result = normalize_speech_text("**Muhim:** `kod` va # sarlavha")
        self.assertNotIn("*", result)
        self.assertNotIn("`", result)
        self.assertNotIn("#", result)

    def test_percent(self) -> None:
        self.assertIn("ellik foiz", normalize_speech_text("chegirma 50%"))

    def test_url_speakable(self) -> None:
        result = normalize_speech_text("https://fotonlabs.com/ saytini oching")
        self.assertNotIn("https://", result)
        self.assertIn("fotonlabs nuqta com", result)

    def test_year(self) -> None:
        result = normalize_speech_text("2026 yil rejasi")
        self.assertIn("ikki ming yigirma olti yil", result)


if __name__ == "__main__":
    unittest.main()
