from __future__ import annotations

from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import time
from typing import Callable, Optional

from .timing import TimingProfile, TypingRhythm


INPUT_KEYBOARD = 1

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_RETURN = 0x0D
VK_TAB = 0x09
VK_ESCAPE = 0x1B
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_DELETE = 0x2E
VK_HOME = 0x24
VK_END = 0x23
VK_PRIOR = 0x21
VK_NEXT = 0x22
VK_INSERT = 0x2D
VK_RMENU = 0xA5
VK_RCONTROL = 0xA3

MAPVK_VK_TO_VSC = 0

ULONG_PTR = wintypes.WPARAM

user32 = ctypes.WinDLL("user32", use_last_error=True)


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("data", _INPUTUNION),
    ]


SendInput = user32.SendInput
SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
SendInput.restype = wintypes.UINT

MapVirtualKeyW = user32.MapVirtualKeyW
MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
MapVirtualKeyW.restype = wintypes.UINT

VkKeyScanExW = user32.VkKeyScanExW
VkKeyScanExW.argtypes = (wintypes.WCHAR, wintypes.HKL)
VkKeyScanExW.restype = ctypes.c_short

GetKeyboardLayout = user32.GetKeyboardLayout
GetKeyboardLayout.argtypes = (wintypes.DWORD,)
GetKeyboardLayout.restype = wintypes.HKL

GetAsyncKeyState = user32.GetAsyncKeyState
GetAsyncKeyState.argtypes = (ctypes.c_int,)
GetAsyncKeyState.restype = ctypes.c_short


@dataclass(slots=True)
class ResolvedKey:
    char: str
    vk: Optional[int]
    use_unicode: bool
    shift: bool = False


@dataclass(slots=True)
class TypingResult:
    completed: bool
    characters_typed: int
    total_characters: int
    message: str


ProgressCallback = Callable[[int, int], None]


class KeyboardTyper:
    def __init__(self) -> None:
        self._layout = GetKeyboardLayout(0)

    def type_text(
        self,
        text: str,
        profile: TimingProfile,
        *,
        stop_requested: Callable[[], bool],
        progress_callback: Optional[ProgressCallback] = None,
    ) -> TypingResult:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        rhythm = TypingRhythm(profile)
        total = len(normalized)
        previous_vk: Optional[int] = None

        for index, char in enumerate(normalized, start=1):
            if stop_requested() or self.escape_pressed():
                return TypingResult(
                    completed=False,
                    characters_typed=index - 1,
                    total_characters=total,
                    message="Typing cancelled.",
                )

            resolved = self.resolve_key(char)
            self.send(resolved)

            if progress_callback is not None:
                progress_callback(index, total)

            delay = rhythm.delay_after(
                current_char=char,
                current_vk=resolved.vk,
                previous_vk=previous_vk,
            )
            if not self._sleep_interruptibly(delay, stop_requested):
                return TypingResult(
                    completed=False,
                    characters_typed=index,
                    total_characters=total,
                    message="Typing cancelled.",
                )

            previous_vk = resolved.vk

        return TypingResult(
            completed=True,
            characters_typed=total,
            total_characters=total,
            message="Typing complete.",
        )

    def resolve_key(self, char: str) -> ResolvedKey:
        if char == "\n":
            return ResolvedKey(char=char, vk=VK_RETURN, use_unicode=False)
        if char == "\t":
            return ResolvedKey(char=char, vk=VK_TAB, use_unicode=False)

        vk_combo = VkKeyScanExW(char, self._layout)
        if vk_combo == -1:
            return ResolvedKey(char=char, vk=None, use_unicode=True)

        shift_state = (vk_combo >> 8) & 0xFF
        virtual_key = vk_combo & 0xFF

        # AltGr and dead-key compositions vary across layouts. Falling back to
        # Unicode packets is less human-like, but it is much more reliable for
        # reproducing the exact visible character in the target field.
        if shift_state & 0x06:
            return ResolvedKey(char=char, vk=None, use_unicode=True)

        return ResolvedKey(
            char=char,
            vk=virtual_key,
            use_unicode=False,
            shift=bool(shift_state & 0x01),
        )

    def send(self, resolved: ResolvedKey) -> None:
        if resolved.use_unicode or resolved.vk is None:
            self._send_unicode(resolved.char)
            return

        if resolved.shift:
            self._send_vk(VK_SHIFT, key_up=False)

        self._send_vk(resolved.vk, key_up=False)
        self._send_vk(resolved.vk, key_up=True)

        if resolved.shift:
            self._send_vk(VK_SHIFT, key_up=True)

    def escape_pressed(self) -> bool:
        return bool(GetAsyncKeyState(VK_ESCAPE) & 0x8000)

    def _sleep_interruptibly(self, seconds: float, stop_requested: Callable[[], bool]) -> bool:
        target = time.perf_counter() + max(seconds, 0.0)
        while time.perf_counter() < target:
            if stop_requested() or self.escape_pressed():
                return False
            time.sleep(0.01)
        return True

    def _send_vk(self, virtual_key: int, *, key_up: bool) -> None:
        scan_code = MapVirtualKeyW(virtual_key, MAPVK_VK_TO_VSC)
        flags = KEYEVENTF_KEYUP if key_up else 0
        if virtual_key in {
            VK_LEFT,
            VK_UP,
            VK_RIGHT,
            VK_DOWN,
            VK_DELETE,
            VK_HOME,
            VK_END,
            VK_PRIOR,
            VK_NEXT,
            VK_INSERT,
            VK_RMENU,
            VK_RCONTROL,
        }:
            flags |= KEYEVENTF_EXTENDEDKEY

        keyboard_input = KEYBDINPUT(
            wVk=virtual_key,
            wScan=scan_code,
            dwFlags=flags,
            time=0,
            dwExtraInfo=0,
        )
        input_record = INPUT(type=INPUT_KEYBOARD, data=_INPUTUNION(ki=keyboard_input))
        sent = SendInput(1, ctypes.byref(input_record), ctypes.sizeof(INPUT))
        if sent != 1:
            raise ctypes.WinError(ctypes.get_last_error())

    def _send_unicode(self, char: str) -> None:
        encoded = char.encode("utf-16-le")
        for index in range(0, len(encoded), 2):
            unit = int.from_bytes(encoded[index : index + 2], "little")
            self._send_unicode_unit(unit, key_up=False)
            self._send_unicode_unit(unit, key_up=True)

    def _send_unicode_unit(self, unit: int, *, key_up: bool) -> None:
        flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if key_up else 0)
        keyboard_input = KEYBDINPUT(
            wVk=0,
            wScan=unit,
            dwFlags=flags,
            time=0,
            dwExtraInfo=0,
        )
        input_record = INPUT(type=INPUT_KEYBOARD, data=_INPUTUNION(ki=keyboard_input))
        sent = SendInput(1, ctypes.byref(input_record), ctypes.sizeof(INPUT))
        if sent != 1:
            raise ctypes.WinError(ctypes.get_last_error())
