"""业务逻辑控制器。"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QFileDialog, QMessageBox

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
from .settings import AppSettings
from .view import MainWindow
from .worker import ClickWorker, RunPlan


def _app_data_dir() -> Path:
    from PyQt6.QtCore import QStandardPaths

    base = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
    base.mkdir(parents=True, exist_ok=True)
    return base


def _setup_logger() -> logging.Logger:
    from logging.handlers import RotatingFileHandler

    logger = logging.getLogger("sequential_clicker")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    log_path = _app_data_dir() / "history.log"
    handler = RotatingFileHandler(log_path, maxBytes=512_000, backupCount=3, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


class Controller:
    """连接 View 与 Model 的控制器。"""

    def __init__(self, window: MainWindow) -> None:
        self.window = window
        self.settings = AppSettings()
        self.logger = _setup_logger()

        self._current_file: Optional[str] = None
        self._points: list[ClickPoint] = []

        self._thread: Optional[QThread] = None
        self._worker: Optional[ClickWorker] = None
        self._paused: bool = False
        self._stop_requested: bool = False
        self._error_occurred: bool = False

        self._sound: Optional[QSoundEffect] = None
        self._init_sound()

        self._hotkeys_enabled = False
        self._keyboard = None

        self._connect_signals()
        max_x, max_y = self._screen_max_xy()
        self.window.set_point_bounds(max_x, max_y)
        self._connect_screen_signals()
        self._refresh_recent_menu()
        self.window.update_points(self._points)

    def _init_sound(self) -> None:
        try:
            from PyQt6.QtMultimedia import QSoundEffect

            effect = QSoundEffect(self.window)
            self._sound = effect
        except Exception:  # noqa: BLE001
            self._sound = None

    def _connect_signals(self) -> None:
        w = self.window
        w.addPointRequested.connect(self.add_point)
        w.deletePointsRequested.connect(self.delete_points_by_rows)
        w.table.orderChanged.connect(self.on_table_order_changed)
        w.table.itemChanged.connect(self.on_table_item_changed)

        w.loadRequested.connect(self.open_config_dialog)
        w.saveRequested.connect(self.save_config)
        w.saveAsRequested.connect(self.save_config_as)
        w.recentFileRequested.connect(self.open_recent_file)

        w.startRequested.connect(self.start)
        w.pauseRequested.connect(self.pause)
        w.resumeRequested.connect(self.resume)
        w.stopRequested.connect(self.stop)

        w.loopUiChanged.connect(self._on_loop_ui_changed)
        w.hotkeyUiChanged.connect(self._on_hotkey_ui_changed)

    def _connect_screen_signals(self) -> None:
        app = QGuiApplication.instance()
        if app is None:
            return
        try:
            app.screenAdded.connect(lambda *_: self._on_screens_changed())
            app.screenRemoved.connect(lambda *_: self._on_screens_changed())
            app.primaryScreenChanged.connect(lambda *_: self._on_screens_changed())
        except Exception:  # noqa: BLE001
            return

    def _on_screens_changed(self) -> None:
        max_x, max_y = self._screen_max_xy()
        self.window.set_point_bounds(max_x, max_y)
        self.logger.info("screens_changed max_x=%s max_y=%s", max_x, max_y)

    def _refresh_recent_menu(self) -> None:
        self.window.update_recent_files(self.settings.recent_files())

    def _screen_max_xy(self) -> tuple[int, int]:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return 99999, 99999
        geo = screen.availableGeometry()
        return max(0, geo.width() - 1), max(0, geo.height() - 1)

    def _screen_size(self) -> ScreenSize:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return ScreenSize(width=100000, height=100000)
        geo = screen.availableGeometry()
        return ScreenSize(width=max(1, geo.width()), height=max(1, geo.height()))

    def add_point(self, x: int, y: int) -> None:
        screen = self._screen_size()
        point = ClickPoint.from_abs(x, y, screen=screen)
        ok, msg = validate_point(point, screen)
        if not ok:
            self.window.show_error(msg)
            return
        self._points.append(point)
        self.window.update_points(self._points)
        self.logger.info("add_point x=%s y=%s", x, y)

    def delete_points_by_rows(self, rows: list[int]) -> None:
        for row in sorted(set(rows), reverse=True):
            if 0 <= row < len(self._points):
                self._points.pop(row)
        self.window.update_points(self._points)
        self.logger.info("delete_points count=%s", len(rows))

    def on_table_order_changed(self) -> None:
        self._points = self.window.points_from_table()
        self.window.refresh_indices()
        self.logger.info("reorder_points")

    def on_table_item_changed(self) -> None:
        points = self.window.points_from_table()
        screen = self._screen_size()
        for p in points:
            ok, _ = validate_point(p, screen)
            if not ok:
                self.window.show_error("坐标值无效，已回退到上一次有效值")
                self.window.update_points(self._points)
                return
        self._points = points
        self.window.refresh_indices()

    def open_config_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.window,
            "打开配置",
            "",
            "JSON Files (*.json);;All Files (*.*)",
        )
        if not path:
            return
        self.open_file(path)

    def open_recent_file(self, path: str) -> None:
        if path:
            self.open_file(path)

    def open_file(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            config = config_from_json_dict(data)
        except Exception as exc:  # noqa: BLE001
            self.window.show_error(f"打开失败：{exc}")
            return

        screen = self._screen_size()
        points: list[ClickPoint] = []
        for p in list(config.points):
            if p.mode == "ratio":
                px, py = p.to_pixels(screen)
                points.append(ClickPoint.from_abs(px, py, screen=screen))
            else:
                points.append(ClickPoint.from_abs(int(round(p.x)), int(round(p.y)), screen=p.screen or screen))
        self._points = points
        self.window.update_points(self._points)
        self.window.spin_interval.setValue(int(config.interval_ms))
        self.window.chk_loop.setChecked(bool(config.loop.enabled))
        self.window.chk_infinite.setChecked(bool(config.loop.infinite))
        self.window.spin_loop_count.setValue(int(max(1, config.loop.count)))
        self.window.spin_loop_interval.setValue(int(max(0, config.loop.interval_ms)))
        self.window.chk_hotkeys.setChecked(bool(config.hotkeys.enabled))
        self.window.edit_hotkey_start.setText(config.hotkeys.start)
        self.window.edit_hotkey_pause.setText(config.hotkeys.pause)
        self.window.edit_hotkey_stop.setText(config.hotkeys.stop)

        self._current_file = path
        self.settings.push_recent_file(path)
        self._refresh_recent_menu()
        self.logger.info("open_file path=%s", path)

        self._on_hotkey_ui_changed()

    def save_config(self) -> None:
        if not self._current_file:
            self.save_config_as()
            return
        self._save_to_path(self._current_file)

    def save_config_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self.window,
            "另存为",
            self._current_file or "",
            "JSON Files (*.json);;All Files (*.*)",
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path = f"{path}.json"
        self._current_file = path
        self._save_to_path(path)
        self.settings.push_recent_file(path)
        self._refresh_recent_menu()

    def _collect_config(self) -> AppConfig:
        loop_ui = self.window.loop_ui_state()
        hotkeys_ui = self.window.hotkey_ui_state()
        loop = LoopSettings(
            enabled=loop_ui.enabled,
            infinite=loop_ui.infinite,
            count=loop_ui.count,
            interval_ms=loop_ui.interval_ms,
        )
        hotkeys = HotkeySettings(
            enabled=hotkeys_ui.enabled,
            start=hotkeys_ui.start,
            pause=hotkeys_ui.pause,
            stop=hotkeys_ui.stop,
        )
        return AppConfig(points=list(self._points), interval_ms=int(self.window.spin_interval.value()), loop=loop, hotkeys=hotkeys)

    def _save_to_path(self, path: str) -> None:
        config = self._collect_config()
        data = config_to_json_dict_v2(config, screen=self._screen_size())
        try:
            Path(os.path.dirname(path) or ".").mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as exc:  # noqa: BLE001
            self.window.show_error(f"保存失败：{exc}")
            return
        self.window.notify_info("配置已保存")
        self.logger.info("save_file path=%s", path)

    def _validate_points_before_run(self) -> bool:
        screen = self._screen_size()
        for i, p in enumerate(self._points, start=1):
            ok, msg = validate_point(p, screen)
            if not ok:
                QMessageBox.critical(self.window, "坐标无效", f"第 {i} 个点无效：{msg}")
                return False
        return True

    def start(self) -> None:
        if self._thread is not None:
            return
        if not self._points:
            self.window.show_error("请先添加至少一个坐标点")
            self.window.set_state("准备")
            return
        if not self._validate_points_before_run():
            self.window.set_state("准备")
            return

        self.window.set_running_controls(True, paused=False)
        self.window.set_state("运行")
        self.window.set_progress(0, len(self._points))
        self._paused = False
        self._stop_requested = False
        self._error_occurred = False

        thread = QThread(self.window)
        worker = ClickWorker()
        plan = RunPlan(points=list(self._points), loop=self._collect_config().loop)
        worker.configure(
            plan=plan,
            interval_provider=lambda: int(self.window.spin_interval.value()),
            loop_interval_provider=lambda: int(self.window.spin_loop_interval.value()),
        )
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progressChanged.connect(self._on_progress)
        worker.cycleChanged.connect(self.window.set_cycle)
        worker.statusChanged.connect(self.window.set_state)
        worker.errorOccurred.connect(self._on_worker_error)
        worker.finished.connect(self._on_worker_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        thread.start()
        self.logger.info("start_run points=%s", len(self._points))

    def pause(self) -> None:
        if self._worker is None or self._paused:
            return
        self._paused = True
        self._worker.request_pause()
        self.window.set_running_controls(True, paused=True)
        self.logger.info("pause")

    def resume(self) -> None:
        if self._worker is None or not self._paused:
            return
        self._paused = False
        self._worker.request_resume()
        self.window.set_running_controls(True, paused=False)
        self.logger.info("resume")

    def stop(self) -> None:
        if self._worker is None:
            self.window.set_state("停止")
            self.window.set_running_controls(False)
            self.window.set_progress(0, 0)
            return
        self._stop_requested = True
        self._worker.request_stop()
        self.logger.info("stop")

    def _on_progress(self, current: int, total: int) -> None:
        self.window.set_progress(current, total)

    def _on_worker_error(self, message: str) -> None:
        self.logger.error("worker_error %s", message)
        self._error_occurred = True
        self.window.show_error(message)

    def _play_done_sound(self) -> None:
        if self._sound is None:
            QApplication.beep()
            return
        try:
            from PyQt6.QtCore import QUrl

            wav = (_app_data_dir() / "done.wav").as_posix()
            if os.path.exists(wav):
                self._sound.setSource(QUrl.fromLocalFile(wav))
                self._sound.setVolume(0.8)
                self._sound.play()
            else:
                QApplication.beep()
        except Exception:  # noqa: BLE001
            QApplication.beep()

    def _on_worker_finished(self) -> None:
        self._thread = None
        self._worker = None
        self._paused = False
        self.window.set_running_controls(False)
        if self._stop_requested:
            self.window.set_state("停止")
        else:
            self.window.set_state("准备")
        self.window.clear_cycle()
        self.window.set_progress(0, 0)
        if not self._stop_requested and not self._error_occurred:
            self.window.notify_info("执行完成")
            self._play_done_sound()
            self.logger.info("finished")
        else:
            self.logger.info("finished stop=%s error=%s", self._stop_requested, self._error_occurred)
        self._stop_requested = False
        self._error_occurred = False

    def _on_loop_ui_changed(self) -> None:
        ui = self.window.loop_ui_state()
        enabled = ui.enabled
        self.window.chk_infinite.setEnabled(enabled)
        self.window.spin_loop_count.setEnabled(enabled and not ui.infinite)
        self.window.spin_loop_interval.setEnabled(enabled)

    def _on_hotkey_ui_changed(self) -> None:
        ui = self.window.hotkey_ui_state()
        self.window.edit_hotkey_start.setEnabled(ui.enabled)
        self.window.edit_hotkey_pause.setEnabled(ui.enabled)
        self.window.edit_hotkey_stop.setEnabled(ui.enabled)
        self._apply_hotkeys(ui)

    def _apply_hotkeys(self, ui) -> None:
        enabled = bool(ui.enabled)
        if not enabled and self._hotkeys_enabled:
            try:
                if self._keyboard is not None:
                    self._keyboard.unhook_all_hotkeys()
            except Exception:  # noqa: BLE001
                pass
            self._hotkeys_enabled = False
            self.logger.info("hotkeys_disabled")
            return

        if not enabled:
            return

        hotkeys = [ui.start, ui.pause, ui.stop]
        if any(not x for x in hotkeys) or len(set(hotkeys)) != 3:
            self.window.chk_hotkeys.setChecked(False)
            self.window.show_error("热键不能为空，且开始/暂停/停止必须互不相同")
            return

        if enabled and not self._hotkeys_enabled:
            try:
                import keyboard

                self._keyboard = keyboard
                keyboard.add_hotkey(ui.start, lambda: self.window.startRequested.emit())
                keyboard.add_hotkey(
                    ui.pause,
                    lambda: self.window.resumeRequested.emit()
                    if self._paused
                    else self.window.pauseRequested.emit(),
                )
                keyboard.add_hotkey(ui.stop, lambda: self.window.stopRequested.emit())
                self._hotkeys_enabled = True
                self.logger.info("hotkeys_enabled")
            except Exception as exc:  # noqa: BLE001
                self._hotkeys_enabled = False
                self.window.chk_hotkeys.setChecked(False)
                self.window.show_error(f"热键启用失败：{exc}")
        elif enabled and self._hotkeys_enabled:
            try:
                if self._keyboard is None:
                    self._hotkeys_enabled = False
                    self.window.chk_hotkeys.setChecked(False)
                    return
                self._keyboard.unhook_all_hotkeys()
                self._keyboard.add_hotkey(ui.start, lambda: self.window.startRequested.emit())
                self._keyboard.add_hotkey(
                    ui.pause,
                    lambda: self.window.resumeRequested.emit()
                    if self._paused
                    else self.window.pauseRequested.emit(),
                )
                self._keyboard.add_hotkey(ui.stop, lambda: self.window.stopRequested.emit())
                self.logger.info("hotkeys_updated")
            except Exception as exc:  # noqa: BLE001
                self._hotkeys_enabled = False
                self.window.chk_hotkeys.setChecked(False)
                self.window.show_error(f"热键更新失败：{exc}")
