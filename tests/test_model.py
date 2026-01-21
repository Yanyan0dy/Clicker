from __future__ import annotations

import unittest

from clicker_core.model import (
    AppConfig,
    ClickPoint,
    HotkeySettings,
    LoopSettings,
    ScreenSize,
    config_from_json_dict,
    config_to_json_dict_v2,
    validate_point,
)


class ModelTests(unittest.TestCase):
    def test_validate_point_abs(self) -> None:
        screen = ScreenSize(width=1920, height=1080)
        ok, _ = validate_point(ClickPoint.from_abs(10, 20), screen)
        self.assertTrue(ok)
        ok, _ = validate_point(ClickPoint.from_abs(-1, 0), screen)
        self.assertFalse(ok)

    def test_validate_point_ratio(self) -> None:
        screen = ScreenSize(width=100, height=100)
        ok, _ = validate_point(ClickPoint.from_ratio(0.5, 0.25), screen)
        self.assertTrue(ok)
        ok, _ = validate_point(ClickPoint.from_ratio(1.1, 0.0), screen)
        self.assertFalse(ok)

    def test_config_v2_roundtrip(self) -> None:
        cfg = AppConfig(
            points=[ClickPoint.from_abs(1, 2), ClickPoint.from_ratio(0.3, 0.4)],
            interval_ms=500,
            loop=LoopSettings(enabled=True, infinite=False, count=2, interval_ms=200),
            hotkeys=HotkeySettings(
                enabled=True,
                start="ctrl+shift+s",
                pause="ctrl+shift+p",
                stop="ctrl+shift+x",
            ),
        )
        data = config_to_json_dict_v2(cfg, screen=ScreenSize(width=1920, height=1080))
        cfg2 = config_from_json_dict(data)
        self.assertEqual(cfg2.points[0].mode, "abs")
        self.assertEqual(int(cfg2.points[0].x), 1)
        self.assertEqual(int(cfg2.points[0].y), 2)
        self.assertEqual(cfg2.points[1].mode, "ratio")
        self.assertEqual(cfg2.interval_ms, 500)
        self.assertTrue(cfg2.loop.enabled)
        self.assertEqual(cfg2.loop.count, 2)
        self.assertTrue(cfg2.hotkeys.enabled)

    def test_read_v1_compat(self) -> None:
        v1 = {
            "version": 1,
            "points": [{"x": 10, "y": 20}, {"x": 30, "y": 40}],
            "settings": {"interval_ms": 500},
        }
        cfg = config_from_json_dict(v1)
        self.assertEqual(len(cfg.points), 2)
        self.assertEqual(cfg.points[0].mode, "abs")
        self.assertEqual(int(cfg.points[0].x), 10)
        self.assertEqual(int(cfg.points[0].y), 20)


if __name__ == "__main__":
    unittest.main()
