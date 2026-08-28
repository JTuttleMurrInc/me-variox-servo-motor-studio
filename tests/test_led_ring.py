"""
Unit tests for core/led_ring.py.
"""

import unittest
from core.led_ring import (
    LedRingConfig, BlinkPattern, eval_pattern_state, SideColorState,
    RING_PRESETS, PATTERN_NAMES
)

class TestLedRing(unittest.TestCase):

    def test_dword_roundtrip(self):
        # User mode enabled, Red Right=0x1, Red Left=0x2, Yellow Right=0x3, Yellow Left=0x4, Green Right=0x5, Green Left=0x6
        cfg = LedRingConfig(
            user_mode=True,
            red_right=0x1,
            red_left=0x2,
            yellow_right=0x3,
            yellow_left=0x4,
            green_right=0x5,
            green_left=0x6
        )
        dword = cfg.to_dword()
        # Check Bit 31 set:
        self.assertTrue(bool(dword & (1 << 31)))
        
        # Decode back
        decoded = LedRingConfig.from_dword(dword)
        self.assertEqual(decoded.user_mode, True)
        self.assertEqual(decoded.red_right, 0x1)
        self.assertEqual(decoded.red_left, 0x2)
        self.assertEqual(decoded.yellow_right, 0x3)
        self.assertEqual(decoded.yellow_left, 0x4)
        self.assertEqual(decoded.green_right, 0x5)
        self.assertEqual(decoded.green_left, 0x6)

    def test_auto_mode_dword(self):
        cfg = LedRingConfig(user_mode=False)
        self.assertEqual(cfg.to_dword(), 0x00000000)
        decoded = LedRingConfig.from_dword(0x00000000)
        self.assertEqual(decoded.user_mode, False)

    def test_priority_order(self):
        # Red > Yellow > Green
        side = SideColorState(red=0x1, yellow=0x1, green=0x1)
        # Red is solid on (0x1), so at any time it must return 'red'
        color, intensity = side.active_color(0.0)
        self.assertEqual(color, "red")

        # When red is off (0x0), yellow should dominate green
        side_no_red = SideColorState(red=0x0, yellow=0x1, green=0x1)
        color, _ = side_no_red.active_color(0.0)
        self.assertEqual(color, "yellow")

        # When red & yellow off, green is active
        side_green_only = SideColorState(red=0x0, yellow=0x0, green=0x1)
        color, _ = side_green_only.active_color(0.0)
        self.assertEqual(color, "green")

    def test_pattern_evaluations(self):
        # Off
        self.assertFalse(eval_pattern_state(BlinkPattern.OFF, 0.5))
        # Solid On
        self.assertTrue(eval_pattern_state(BlinkPattern.SOLID_ON, 0.5))
        # 1s On / 1s Off: at 0.5s is True, at 1.5s is False
        self.assertTrue(eval_pattern_state(BlinkPattern.ON_1S_OFF_1S, 0.5))
        self.assertFalse(eval_pattern_state(BlinkPattern.ON_1S_OFF_1S, 1.5))
        # 500ms On / 500ms Off: at 0.2s is True, at 0.7s is False
        self.assertTrue(eval_pattern_state(BlinkPattern.ON_500MS_OFF_500MS, 0.2))
        self.assertFalse(eval_pattern_state(BlinkPattern.ON_500MS_OFF_500MS, 0.7))

    def test_presets_exist(self):
        self.assertGreaterEqual(len(RING_PRESETS), 10)
        solid_green = RING_PRESETS["Solid Green (Normal Operation)"]
        self.assertTrue(solid_green.user_mode)
        self.assertEqual(solid_green.green_left, 0x1)
        self.assertEqual(solid_green.green_right, 0x1)

if __name__ == "__main__":
    unittest.main()
