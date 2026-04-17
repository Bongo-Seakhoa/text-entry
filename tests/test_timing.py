import unittest
import ctypes

from typing_simulator.keyboard_engine import INPUT
from typing_simulator.timing import TimingProfile, TypingRhythm, format_duration


class TimingRhythmTests(unittest.TestCase):
    def test_windows_input_structure_matches_expected_size(self) -> None:
        expected_size = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
        self.assertEqual(ctypes.sizeof(INPUT), expected_size)

    def test_sentence_punctuation_adds_extra_pause(self) -> None:
        profile = TimingProfile(words_per_minute=60, humanize=True)
        rhythm = TypingRhythm(profile, seed=11)

        letter_delay = rhythm.delay_after(current_char="a", current_vk=ord("A"), previous_vk=ord("S"))
        period_delay = rhythm.delay_after(current_char=".", current_vk=0xBE, previous_vk=ord("A"))

        self.assertGreater(period_delay, letter_delay)

    def test_estimate_duration_grows_with_text_length(self) -> None:
        profile = TimingProfile(words_per_minute=70, humanize=False)
        rhythm = TypingRhythm(profile, seed=4)

        short = rhythm.estimate_duration("short")
        long = rhythm.estimate_duration("this is definitely longer")

        self.assertGreater(long, short)

    def test_format_duration_is_readable(self) -> None:
        self.assertEqual(format_duration(4.2), "4s")
        self.assertEqual(format_duration(64.0), "1m 4s")


if __name__ == "__main__":
    unittest.main()
