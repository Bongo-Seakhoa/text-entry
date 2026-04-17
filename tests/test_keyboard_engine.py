import unittest
from unittest.mock import patch

from typing_simulator import keyboard_engine as ke


class ResolveKeyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.typer = ke.KeyboardTyper()

    def test_resolve_key_maps_newline_and_tab_without_unicode_fallback(self) -> None:
        newline = self.typer.resolve_key("\n")
        tab = self.typer.resolve_key("\t")

        self.assertEqual(newline.vk, ke.VK_RETURN)
        self.assertEqual(tab.vk, ke.VK_TAB)
        self.assertFalse(newline.use_unicode)
        self.assertFalse(tab.use_unicode)
        self.assertFalse(newline.shift)
        self.assertFalse(tab.shift)

    @patch("typing_simulator.keyboard_engine.VkKeyScanExW", return_value=(0x01 << 8) | 0x41)
    def test_resolve_key_detects_shifted_virtual_key(self, _mock_vk_lookup: object) -> None:
        resolved = self.typer.resolve_key("A")

        self.assertEqual(resolved.vk, 0x41)
        self.assertFalse(resolved.use_unicode)
        self.assertTrue(resolved.shift)

    @patch("typing_simulator.keyboard_engine.VkKeyScanExW", return_value=-1)
    def test_resolve_key_falls_back_to_unicode_when_lookup_fails(self, _mock_vk_lookup: object) -> None:
        resolved = self.typer.resolve_key("é")

        self.assertIsNone(resolved.vk)
        self.assertTrue(resolved.use_unicode)
        self.assertFalse(resolved.shift)

    @patch("typing_simulator.keyboard_engine.VkKeyScanExW", return_value=(0x06 << 8) | 0x45)
    def test_resolve_key_uses_unicode_for_altgr_or_dead_key_combo(self, _mock_vk_lookup: object) -> None:
        resolved = self.typer.resolve_key("€")

        self.assertIsNone(resolved.vk)
        self.assertTrue(resolved.use_unicode)
        self.assertFalse(resolved.shift)


if __name__ == "__main__":
    unittest.main()
