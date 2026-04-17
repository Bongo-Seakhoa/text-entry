from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Optional


VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_SPACE = 0x20
VK_OEM_1 = 0xBA
VK_OEM_PLUS = 0xBB
VK_OEM_COMMA = 0xBC
VK_OEM_MINUS = 0xBD
VK_OEM_PERIOD = 0xBE
VK_OEM_2 = 0xBF
VK_OEM_3 = 0xC0
VK_OEM_4 = 0xDB
VK_OEM_5 = 0xDC
VK_OEM_6 = 0xDD
VK_OEM_7 = 0xDE


QWERTY_POSITIONS = {
    VK_OEM_3: (0.0, 0.0),
    ord("1"): (1.0, 0.0),
    ord("2"): (2.0, 0.0),
    ord("3"): (3.0, 0.0),
    ord("4"): (4.0, 0.0),
    ord("5"): (5.0, 0.0),
    ord("6"): (6.0, 0.0),
    ord("7"): (7.0, 0.0),
    ord("8"): (8.0, 0.0),
    ord("9"): (9.0, 0.0),
    ord("0"): (10.0, 0.0),
    VK_OEM_MINUS: (11.0, 0.0),
    VK_OEM_PLUS: (12.0, 0.0),
    VK_BACK: (13.4, 0.0),
    VK_TAB: (0.4, 1.0),
    ord("Q"): (1.4, 1.0),
    ord("W"): (2.4, 1.0),
    ord("E"): (3.4, 1.0),
    ord("R"): (4.4, 1.0),
    ord("T"): (5.4, 1.0),
    ord("Y"): (6.4, 1.0),
    ord("U"): (7.4, 1.0),
    ord("I"): (8.4, 1.0),
    ord("O"): (9.4, 1.0),
    ord("P"): (10.4, 1.0),
    VK_OEM_4: (11.4, 1.0),
    VK_OEM_6: (12.4, 1.0),
    ord("A"): (1.8, 2.0),
    ord("S"): (2.8, 2.0),
    ord("D"): (3.8, 2.0),
    ord("F"): (4.8, 2.0),
    ord("G"): (5.8, 2.0),
    ord("H"): (6.8, 2.0),
    ord("J"): (7.8, 2.0),
    ord("K"): (8.8, 2.0),
    ord("L"): (9.8, 2.0),
    VK_OEM_1: (10.8, 2.0),
    VK_OEM_7: (11.8, 2.0),
    VK_RETURN: (13.1, 2.0),
    ord("Z"): (2.3, 3.0),
    ord("X"): (3.3, 3.0),
    ord("C"): (4.3, 3.0),
    ord("V"): (5.3, 3.0),
    ord("B"): (6.3, 3.0),
    ord("N"): (7.3, 3.0),
    ord("M"): (8.3, 3.0),
    VK_OEM_COMMA: (9.3, 3.0),
    VK_OEM_PERIOD: (10.3, 3.0),
    VK_OEM_2: (11.3, 3.0),
    VK_OEM_5: (12.3, 3.0),
    VK_SPACE: (6.3, 4.2),
}


@dataclass(slots=True)
class TimingProfile:
    words_per_minute: int = 65
    startup_delay_seconds: int = 4
    humanize: bool = True
    jitter_ratio: float = 0.18
    distance_multiplier: float = 0.28
    punctuation_pause_ratio: float = 0.75
    sentence_pause_ratio: float = 1.45
    line_break_pause_ratio: float = 1.9
    minimum_delay_seconds: float = 0.012

    @property
    def base_delay_seconds(self) -> float:
        safe_wpm = max(self.words_per_minute, 1)
        return 60.0 / (safe_wpm * 5.0)


class TypingRhythm:
    def __init__(self, profile: TimingProfile, seed: Optional[int] = None) -> None:
        self.profile = profile
        self._random = random.Random(seed)

    def delay_after(
        self,
        *,
        current_char: str,
        current_vk: Optional[int],
        previous_vk: Optional[int],
    ) -> float:
        base = self.profile.base_delay_seconds
        delay = base

        if not self.profile.humanize:
            return max(self.profile.minimum_delay_seconds, delay)

        delay += self._distance_penalty(previous_vk, current_vk) * base * self.profile.distance_multiplier
        delay += self._character_pause(current_char, base)
        delay += self._random.uniform(-self.profile.jitter_ratio, self.profile.jitter_ratio) * base

        return max(self.profile.minimum_delay_seconds, delay)

    def estimate_duration(self, text: str) -> float:
        previous_vk: Optional[int] = None
        total = 0.0

        for char in text.replace("\r\n", "\n").replace("\r", "\n"):
            vk = self._guess_vk(char)
            total += self.delay_after(current_char=char, current_vk=vk, previous_vk=previous_vk)
            previous_vk = vk

        return total

    def _distance_penalty(self, previous_vk: Optional[int], current_vk: Optional[int]) -> float:
        if previous_vk is None or current_vk is None:
            return 0.14

        previous_pos = QWERTY_POSITIONS.get(previous_vk)
        current_pos = QWERTY_POSITIONS.get(current_vk)
        if previous_pos is None or current_pos is None:
            return 0.26

        dx = current_pos[0] - previous_pos[0]
        dy = current_pos[1] - previous_pos[1]
        return math.sqrt((dx * dx) + (dy * dy)) / 3.2

    def _character_pause(self, char: str, base: float) -> float:
        if char in ".!?":
            return base * self.profile.sentence_pause_ratio
        if char in ",;:":
            return base * self.profile.punctuation_pause_ratio
        if char == "\n":
            return base * self.profile.line_break_pause_ratio
        if char == " ":
            return base * 0.18
        return 0.0

    def _guess_vk(self, char: str) -> Optional[int]:
        if char == "\n":
            return VK_RETURN
        if char == "\t":
            return VK_TAB
        if char == " ":
            return VK_SPACE

        upper = char.upper()
        if len(upper) == 1 and upper.isascii():
            code_point = ord(upper)
            if ord("A") <= code_point <= ord("Z"):
                return code_point
            if ord("0") <= code_point <= ord("9"):
                return code_point

        punctuation_map = {
            "`": VK_OEM_3,
            "~": VK_OEM_3,
            "-": VK_OEM_MINUS,
            "_": VK_OEM_MINUS,
            "=": VK_OEM_PLUS,
            "+": VK_OEM_PLUS,
            "[": VK_OEM_4,
            "{": VK_OEM_4,
            "]": VK_OEM_6,
            "}": VK_OEM_6,
            ";": VK_OEM_1,
            ":": VK_OEM_1,
            "'": VK_OEM_7,
            '"': VK_OEM_7,
            ",": VK_OEM_COMMA,
            "<": VK_OEM_COMMA,
            ".": VK_OEM_PERIOD,
            ">": VK_OEM_PERIOD,
            "/": VK_OEM_2,
            "?": VK_OEM_2,
            "\\": VK_OEM_5,
            "|": VK_OEM_5,
        }
        return punctuation_map.get(char)


def format_duration(seconds: float) -> str:
    rounded = max(int(round(seconds)), 0)
    minutes, remainder = divmod(rounded, 60)
    if minutes and remainder:
        return f"{minutes}m {remainder}s"
    if minutes:
        return f"{minutes}m"
    return f"{remainder}s"
