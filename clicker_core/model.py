"""数据模型、坐标换算与配置序列化。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

PointMode = Literal["abs", "ratio"]


@dataclass(frozen=True, slots=True)
class ScreenSize:
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class ClickPoint:
    mode: PointMode
    x: float
    y: float
    screen: Optional[ScreenSize] = None

    def to_pixels(self, screen: ScreenSize) -> tuple[int, int]:
        if self.mode == "abs":
            return int(round(self.x)), int(round(self.y))
        max_x = max(0, int(screen.width) - 1)
        max_y = max(0, int(screen.height) - 1)
        px = int(round(float(self.x) * max_x))
        py = int(round(float(self.y) * max_y))
        return px, py

    @staticmethod
    def from_abs(x: int, y: int, screen: Optional[ScreenSize] = None) -> "ClickPoint":
        return ClickPoint(mode="abs", x=float(int(x)), y=float(int(y)), screen=screen)

    @staticmethod
    def from_ratio(x: float, y: float, screen: Optional[ScreenSize] = None) -> "ClickPoint":
        return ClickPoint(mode="ratio", x=float(x), y=float(y), screen=screen)


@dataclass(slots=True)
class LoopSettings:
    enabled: bool = False
    infinite: bool = False
    count: int = 1
    interval_ms: int = 0


@dataclass(slots=True)
class HotkeySettings:
    enabled: bool = False
    start: str = "ctrl+shift+s"
    pause: str = "ctrl+shift+p"
    stop: str = "ctrl+shift+x"


@dataclass(slots=True)
class AppConfig:
    points: list[ClickPoint]
    interval_ms: int = 500
    loop: LoopSettings = field(default_factory=LoopSettings)
    hotkeys: HotkeySettings = field(default_factory=HotkeySettings)


def validate_point(point: ClickPoint, screen: ScreenSize) -> tuple[bool, str]:
    if point.mode == "ratio":
        if not (0.0 <= point.x <= 1.0 and 0.0 <= point.y <= 1.0):
            return False, "比例坐标必须在 0.0–1.0 范围内"
        return True, ""

    x = int(round(point.x))
    y = int(round(point.y))
    max_x = max(0, int(screen.width) - 1)
    max_y = max(0, int(screen.height) - 1)
    if x < 0 or y < 0:
        return False, "坐标不能为负数"
    if x > max_x or y > max_y:
        return False, "坐标超出屏幕范围"
    return True, ""


def _screen_from_any(data: Any) -> Optional[ScreenSize]:
    if not isinstance(data, dict):
        return None
    try:
        w = int(data.get("w"))
        h = int(data.get("h"))
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    return ScreenSize(width=w, height=h)


def config_to_json_dict_v2(config: AppConfig, screen: Optional[ScreenSize] = None) -> dict[str, Any]:
    points: list[dict[str, Any]] = []
    for p in config.points:
        item: dict[str, Any] = {"mode": p.mode, "x": p.x, "y": p.y}
        if p.screen is not None:
            item["screen"] = {"w": p.screen.width, "h": p.screen.height}
        points.append(item)

    data: dict[str, Any] = {
        "version": 2,
        "points": points,
        "settings": {
            "interval_ms": int(config.interval_ms),
            "loop": {
                "enabled": bool(config.loop.enabled),
                "infinite": bool(config.loop.infinite),
                "count": int(config.loop.count),
                "interval_ms": int(config.loop.interval_ms),
            },
            "hotkeys": {
                "enabled": bool(config.hotkeys.enabled),
                "start": str(config.hotkeys.start),
                "pause": str(config.hotkeys.pause),
                "stop": str(config.hotkeys.stop),
            },
        },
    }

    if screen is not None:
        data["meta"] = {"screen": {"w": int(screen.width), "h": int(screen.height)}}
    return data


def config_from_json_dict(data: dict[str, Any]) -> AppConfig:
    version = int(data.get("version", 1))
    settings = data.get("settings") or {}

    interval_ms = int(settings.get("interval_ms", 500))

    loop_raw = settings.get("loop") or {}
    loop = LoopSettings(
        enabled=bool(loop_raw.get("enabled", False)),
        infinite=bool(loop_raw.get("infinite", False)),
        count=int(loop_raw.get("count", 1)),
        interval_ms=int(loop_raw.get("interval_ms", 0)),
    )

    hotkeys_raw = settings.get("hotkeys") or {}
    hotkeys = HotkeySettings(
        enabled=bool(hotkeys_raw.get("enabled", False)),
        start=str(hotkeys_raw.get("start", "ctrl+shift+s")),
        pause=str(hotkeys_raw.get("pause", "ctrl+shift+p")),
        stop=str(hotkeys_raw.get("stop", "ctrl+shift+x")),
    )

    points: list[ClickPoint] = []
    points_raw = data.get("points") or []

    if version <= 1:
        for item in points_raw:
            if not isinstance(item, dict):
                continue
            try:
                x = int(item.get("x"))
                y = int(item.get("y"))
            except (TypeError, ValueError):
                continue
            points.append(ClickPoint.from_abs(x, y))
        return AppConfig(points=points, interval_ms=interval_ms, loop=loop, hotkeys=hotkeys)

    for item in points_raw:
        if not isinstance(item, dict):
            continue
        mode = item.get("mode", "abs")
        if mode not in ("abs", "ratio"):
            mode = "abs"
        try:
            x = float(item.get("x"))
            y = float(item.get("y"))
        except (TypeError, ValueError):
            continue
        screen_item = _screen_from_any(item.get("screen"))
        points.append(ClickPoint(mode=mode, x=x, y=y, screen=screen_item))

    return AppConfig(points=points, interval_ms=interval_ms, loop=loop, hotkeys=hotkeys)

