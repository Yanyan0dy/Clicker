"""桌面端兼容层（转向 clicker_core）。"""

from __future__ import annotations

from clicker_core.model import (  # noqa: F401
    AppConfig,
    ClickPoint,
    HotkeySettings,
    LoopSettings,
    ScreenSize,
    config_from_json_dict,
    config_to_json_dict_v2,
    validate_point,
)
