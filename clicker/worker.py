"""连点工作线程。"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

from PyQt6.QtCore import QObject, pyqtSignal

from clicker_core.model import ClickPoint, LoopSettings, ScreenSize


@dataclass(frozen=True, slots=True)
class RunPlan:
    """一次运行计划。"""

    points: list[ClickPoint]
    loop: LoopSettings


class ClickWorker(QObject):
    """在工作线程中执行顺序连点。"""

    statusChanged = pyqtSignal(str)
    progressChanged = pyqtSignal(int, int)
    cycleChanged = pyqtSignal(int, int)
    finished = pyqtSignal()
    errorOccurred = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._pause_event = threading.Event()
        self._stop_event = threading.Event()
        self._pause_event.set()
        self._interval_provider: Callable[[], int] | None = None
        self._loop_interval_provider: Callable[[], int] | None = None
        self._plan: RunPlan | None = None

    def configure(
        self,
        plan: RunPlan,
        interval_provider: Callable[[], int],
        loop_interval_provider: Callable[[], int],
    ) -> None:
        self._plan = plan
        self._interval_provider = interval_provider
        self._loop_interval_provider = loop_interval_provider

    def request_pause(self) -> None:
        self._pause_event.clear()
        self.statusChanged.emit("暂停")

    def request_resume(self) -> None:
        self._pause_event.set()
        self.statusChanged.emit("运行")

    def request_stop(self) -> None:
        self._stop_event.set()
        self._pause_event.set()
        self.statusChanged.emit("停止")

    def run(self) -> None:
        plan = self._plan
        interval_provider = self._interval_provider
        loop_interval_provider = self._loop_interval_provider
        if plan is None or interval_provider is None or loop_interval_provider is None:
            self.errorOccurred.emit("任务未配置")
            self.finished.emit()
            return

        try:
            import pyautogui
        except Exception as exc:  # noqa: BLE001
            self.errorOccurred.emit(f"pyautogui 导入失败：{exc}")
            self.finished.emit()
            return

        try:
            FailSafeException = pyautogui.FailSafeException
        except Exception:  # noqa: BLE001
            FailSafeException = Exception

        points = list(plan.points)
        if not points:
            self.finished.emit()
            return

        def sleep_ms(ms: int) -> None:
            end = time.time() + (max(0, ms) / 1000.0)
            while time.time() < end:
                if self._stop_event.is_set():
                    return
                if not self._pause_event.is_set():
                    self._pause_event.wait(0.1)
                time.sleep(0.01)

        self.statusChanged.emit("运行")

        cycles_total = 1
        if plan.loop.enabled and plan.loop.infinite:
            cycles_total = 0
        elif plan.loop.enabled:
            cycles_total = max(1, int(plan.loop.count))

        cycle_index = 0
        try:
            while True:
                if self._stop_event.is_set():
                    break

                cycle_index += 1
                if cycles_total > 0:
                    self.cycleChanged.emit(cycle_index, cycles_total)
                else:
                    self.cycleChanged.emit(cycle_index, 0)

                total = len(points)
                for i, p in enumerate(points, start=1):
                    if self._stop_event.is_set():
                        break
                    if not self._pause_event.is_set():
                        self._pause_event.wait()

                    self.progressChanged.emit(i, total)

                    try:
                        size = pyautogui.size()
                        screen = ScreenSize(width=int(size.width), height=int(size.height))
                        px, py = p.to_pixels(screen)
                        max_x = int(screen.width) - 1
                        max_y = int(screen.height) - 1
                        if px < 0 or py < 0 or px > max_x or py > max_y:
                            self.errorOccurred.emit(
                                f"屏幕分辨率变更导致坐标越界：({px},{py})，当前最大({max_x},{max_y})"
                            )
                            self._stop_event.set()
                            break
                        pyautogui.moveTo(px, py)
                        pyautogui.click(px, py)
                    except FailSafeException:
                        self.errorOccurred.emit("触发 FailSafe：鼠标移动到屏幕角落，已停止")
                        self._stop_event.set()
                        break
                    except Exception as exc:  # noqa: BLE001
                        self.errorOccurred.emit(f"点击失败：{exc}")
                        self._stop_event.set()
                        break

                    sleep_ms(int(interval_provider()))

                if self._stop_event.is_set():
                    break

                if not plan.loop.enabled:
                    break
                if plan.loop.enabled and not plan.loop.infinite and cycle_index >= cycles_total:
                    break

                sleep_ms(int(loop_interval_provider()))
        finally:
            self.finished.emit()
