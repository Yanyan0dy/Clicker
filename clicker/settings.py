"""应用设置（最近文件等）。"""

from __future__ import annotations

from PyQt6.QtCore import QSettings


class AppSettings:
    """基于 QSettings 的持久化设置。"""

    def __init__(self) -> None:
        self._settings = QSettings("SequentialClicker", "SequentialClicker")

    def recent_files(self) -> list[str]:
        value = self._settings.value("recent_files", [])
        if isinstance(value, list):
            return [str(x) for x in value][:3]
        if isinstance(value, str) and value:
            return [value][:3]
        return []

    def push_recent_file(self, path: str) -> None:
        if not path:
            return
        files = [p for p in self.recent_files() if p != path]
        files.insert(0, path)
        self._settings.setValue("recent_files", files[:3])

