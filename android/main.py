from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.behaviors import DragBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.utils import platform
from kivymd.app import MDApp
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import MDList, OneLineAvatarIconListItem
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.snackbar import Snackbar

from clicker_core.model import AppConfig, ClickPoint, LoopSettings, ScreenSize, config_from_json_dict, config_to_json_dict_v2
from android_bridge import (
    is_accessibility_enabled,
    open_accessibility_settings,
    send_click,
    start_foreground_service,
    stop_foreground_service,
)


KV = r"""
<PointListItem>:
    text: root.text
    _no_ripple_effect: True
    on_release: app.on_item_tapped(root)
    IconLeftWidget:
        icon: "drag"

<MainScreen>:
    name: "main"
    MDBoxLayout:
        id: root_layout
        orientation: "horizontal"
        padding: "12dp"
        spacing: "12dp"

        MDCard:
            id: list_card
            radius: [12, 12, 12, 12]
            md_bg_color: app.theme_cls.bg_normal
            size_hint_x: 0.6
            padding: "8dp"

            MDBoxLayout:
                orientation: "vertical"
                spacing: "8dp"

                MDBoxLayout:
                    size_hint_y: None
                    height: self.minimum_height
                    spacing: "8dp"
                    MDRaisedButton:
                        text: "录点"
                        on_release: app.open_record()
                    MDRaisedButton:
                        text: "导入"
                        on_release: app.open_file_dialog()
                    MDRaisedButton:
                        text: "保存"
                        on_release: app.save_default()
                    MDRaisedButton:
                        text: "另存为"
                        on_release: app.save_as_dialog()
                    MDRaisedButton:
                        text: "删除"
                        on_release: app.delete_selected()

                ScrollView:
                    MDList:
                        id: points_list

        MDCard:
            radius: [12, 12, 12, 12]
            md_bg_color: app.theme_cls.bg_normal
            padding: "12dp"

            MDBoxLayout:
                orientation: "vertical"
                spacing: "12dp"

                MDBoxLayout:
                    size_hint_y: None
                    height: self.minimum_height
                    spacing: "12dp"
                    MDRaisedButton:
                        id: btn_start
                        text: "开始"
                        on_release: app.start()
                    MDRaisedButton:
                        id: btn_pause
                        text: "暂停"
                        disabled: True
                        on_release: app.pause_or_resume()
                    MDRaisedButton:
                        id: btn_stop
                        text: "停止"
                        disabled: True
                        on_release: app.stop()

                MDLabel:
                    id: status_label
                    text: "准备"
                    theme_text_color: "Secondary"

                MDTextField:
                    id: interval_input
                    text: "500"
                    mode: "rectangle"
                    input_filter: "int"
                    helper_text: "间隔时间（ms，100-5000）"
                    helper_text_mode: "on_focus"

                MDBoxLayout:
                    orientation: "horizontal"
                    size_hint_y: None
                    height: self.minimum_height
                    spacing: "8dp"
                    MDCheckbox:
                        id: loop_enabled
                        active: False
                    MDLabel:
                        text: "启用循环"
                        valign: "middle"

                MDTextField:
                    id: loop_count
                    text: "1"
                    mode: "rectangle"
                    input_filter: "int"
                    helper_text: "循环次数（1-999）"
                    helper_text_mode: "on_focus"
                    disabled: not loop_enabled.active

                MDBoxLayout:
                    orientation: "horizontal"
                    size_hint_y: None
                    height: self.minimum_height
                    spacing: "8dp"
                    MDCheckbox:
                        id: loop_infinite
                        active: False
                        disabled: not loop_enabled.active
                    MDLabel:
                        text: "无限循环"
                        valign: "middle"

                MDTextField:
                    id: loop_interval
                    text: "0"
                    mode: "rectangle"
                    input_filter: "int"
                    helper_text: "循环间隔（ms）"
                    helper_text_mode: "on_focus"
                    disabled: not loop_enabled.active

<RecordScreen>:
    name: "record"
    MDBoxLayout:
        orientation: "vertical"
        padding: "12dp"
        spacing: "12dp"
        MDLabel:
            text: "录点模式：在屏幕上点击任意位置以添加坐标（按返回退出）"
            theme_text_color: "Secondary"
            size_hint_y: None
            height: self.texture_size[1] + dp(12)
        MDCard:
            id: canvas_card
            radius: [12, 12, 12, 12]
            md_bg_color: (0, 0, 0, 0.05)

<FileScreen>:
    name: "file"
    MDBoxLayout:
        orientation: "vertical"
        padding: "12dp"
        spacing: "12dp"
        MDLabel:
            id: file_title
            text: "文件"
            theme_text_color: "Secondary"
            size_hint_y: None
            height: self.texture_size[1] + dp(12)
        FileChooserListView:
            id: chooser
            path: app.user_data_dir
            filters: ["*.json"]
        MDTextField:
            id: filename
            text: "config.json"
            mode: "rectangle"
            helper_text: "保存时填写文件名（.json）"
            helper_text_mode: "on_focus"
        MDBoxLayout:
            size_hint_y: None
            height: self.minimum_height
            spacing: "12dp"
            MDRaisedButton:
                text: "确定"
                on_release: app.confirm_file()
            MDFlatButton:
                text: "取消"
                on_release: app.cancel_file()

"""


class PointListItem(OneLineAvatarIconListItem):
    index = NumericProperty(0)
    selected = BooleanProperty(False)


class DraggablePointListItem(DragBehavior, PointListItem):
    drag_timeout = 200
    drag_distance = 10

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._dragging = False

    def on_touch_move(self, touch):  # type: ignore[override]
        if self.collide_point(*touch.pos):
            self._dragging = True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):  # type: ignore[override]
        res = super().on_touch_up(touch)
        if self._dragging:
            self._dragging = False
            app = MDApp.get_running_app()
            app.reorder_by_drop(self)
            return True
        return res


class MainScreen(Screen):
    pass


class RecordScreen(Screen):
    def on_touch_down(self, touch):  # type: ignore[override]
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        app = MDApp.get_running_app()
        app.add_point_from_touch(touch.x, touch.y)
        return True


class FileScreen(Screen):
    pass


@dataclass(slots=True)
class RecentFiles:
    items: list[str]


class AndroidClickerApp(MDApp):
    points = ListProperty([])
    status_text = StringProperty("准备")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._dialog: Optional[MDDialog] = None
        self._recent: RecentFiles = RecentFiles(items=[])
        self._default_path = Path(self.user_data_dir) / "config.json"
        self._running = False
        self._paused = False
        self._cursor = 0
        self._clock_ev = None
        self._cycle_done = 0
        self._file_mode: str = "open"

    def build(self):
        self.theme_cls.primary_palette = "Blue"
        Builder.load_string(KV)
        sm = ScreenManager()
        self.main_screen = MainScreen()
        self.record_screen = RecordScreen()
        self.file_screen = FileScreen()
        sm.add_widget(self.main_screen)
        sm.add_widget(self.record_screen)
        sm.add_widget(self.file_screen)
        self.sm = sm
        self._load_default_if_exists()
        self._refresh_points_list()
        self._update_layout()
        Window.bind(size=lambda *_: self._update_layout())
        return sm

    def _update_layout(self):
        root = self.main_screen.ids.get("root_layout")
        if root is None:
            return
        root.orientation = "horizontal" if Window.width >= Window.height else "vertical"

    def open_record(self):
        self.sm.current = "record"

    def add_point_from_touch(self, x: float, y: float):
        screen = ScreenSize(width=max(1, int(Window.width)), height=max(1, int(Window.height)))
        rx = float(x) / float(max(1, screen.width - 1))
        ry = float(y) / float(max(1, screen.height - 1))
        self.points.append(ClickPoint.from_ratio(rx, ry, screen=screen))
        self._refresh_points_list()
        Snackbar(text="已添加坐标点").open()

    def on_item_tapped(self, item: PointListItem):
        item.selected = not item.selected
        checkbox = getattr(item, "checkbox", None)
        if checkbox is not None:
            checkbox.active = item.selected

    def _refresh_points_list(self):
        lst: MDList = self.main_screen.ids.points_list
        lst.clear_widgets()
        for i, p in enumerate(list(self.points), start=1):
            item = DraggablePointListItem(text=f"{i}. ratio=({p.x:.4f}, {p.y:.4f})", index=i - 1)
            cb = MDCheckbox(active=False)
            item.add_widget(cb)
            item.checkbox = cb
            lst.add_widget(item)

    def reorder_by_drop(self, dragged: DraggablePointListItem):
        lst: MDList = self.main_screen.ids.points_list
        items = [w for w in reversed(lst.children) if isinstance(w, DraggablePointListItem)]
        if not items:
            return
        try:
            from_idx = items.index(dragged)
        except ValueError:
            return

        target = min(items, key=lambda w: abs(w.center_y - dragged.center_y))
        to_idx = items.index(target)
        if from_idx == to_idx:
            return
        pts = list(self.points)
        moving = pts.pop(from_idx)
        pts.insert(to_idx, moving)
        self.points = pts
        self._refresh_points_list()
        Snackbar(text=f"已调整顺序：{from_idx + 1} → {to_idx + 1}").open()

    def delete_selected(self):
        lst: MDList = self.main_screen.ids.points_list
        selected = []
        for w in list(lst.children):
            if isinstance(w, PointListItem) and getattr(w, "checkbox", None) is not None:
                if w.checkbox.active:
                    selected.append(int(w.index))
        if not selected:
            Snackbar(text="未选择任何坐标点").open()
            return

        def do_delete(_):
            for idx in sorted(set(selected), reverse=True):
                if 0 <= idx < len(self.points):
                    self.points.pop(idx)
            self._refresh_points_list()

        self._confirm("确认删除", f"确定删除选中的 {len(selected)} 个点吗？", do_delete)

    def _confirm(self, title: str, text: str, on_yes):
        if self._dialog is not None:
            self._dialog.dismiss()
        self._dialog = MDDialog(
            title=title,
            text=text,
            buttons=[
                MDFlatButton(text="取消", on_release=lambda *_: self._dialog.dismiss()),
                MDRaisedButton(text="确定", on_release=lambda *_: (self._dialog.dismiss(), on_yes(None))),
            ],
        )
        self._dialog.open()

    def _collect_config(self) -> AppConfig:
        interval = self._clamp_int(self.main_screen.ids.interval_input.text, 100, 5000, 500)
        loop_enabled = bool(self.main_screen.ids.loop_enabled.active)
        loop_infinite = bool(self.main_screen.ids.loop_infinite.active) if loop_enabled else False
        loop_count = self._clamp_int(self.main_screen.ids.loop_count.text, 1, 999, 1)
        loop_interval = self._clamp_int(self.main_screen.ids.loop_interval.text, 0, 10000, 0)
        loop = LoopSettings(enabled=loop_enabled, infinite=loop_infinite, count=loop_count, interval_ms=loop_interval)
        return AppConfig(points=list(self.points), interval_ms=interval, loop=loop)

    def save_default(self):
        self._save_to_path(self._default_path)

    def open_file_dialog(self):
        self._file_mode = "open"
        self.file_screen.ids.file_title.text = "导入配置"
        self.file_screen.ids.filename.disabled = True
        self.sm.current = "file"

    def save_as_dialog(self):
        self._file_mode = "save"
        self.file_screen.ids.file_title.text = "另存为配置"
        self.file_screen.ids.filename.disabled = False
        self.sm.current = "file"

    def cancel_file(self):
        self.sm.current = "main"

    def confirm_file(self):
        chooser = self.file_screen.ids.chooser
        if self._file_mode == "open":
            if not chooser.selection:
                Snackbar(text="请选择要导入的JSON文件").open()
                return
            self._load_from_path(Path(chooser.selection[0]))
            self.sm.current = "main"
            self._refresh_points_list()
            return

        filename = self.file_screen.ids.filename.text.strip()
        if not filename:
            Snackbar(text="请输入文件名").open()
            return
        if not filename.lower().endswith(".json"):
            filename = f"{filename}.json"
        path = Path(chooser.path) / filename
        self._save_to_path(path)
        self.sm.current = "main"

    def _load_default_if_exists(self):
        if not self._default_path.exists():
            return
        self._load_from_path(self._default_path)

    def _load_from_path(self, path: Path):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            cfg = config_from_json_dict(data)
        except Exception as exc:  # noqa: BLE001
            Snackbar(text=f"导入失败：{exc}").open()
            return
        self.points = list(cfg.points)
        self.main_screen.ids.interval_input.text = str(int(cfg.interval_ms))
        self.main_screen.ids.loop_enabled.active = bool(cfg.loop.enabled)
        self.main_screen.ids.loop_infinite.active = bool(cfg.loop.infinite)
        self.main_screen.ids.loop_count.text = str(int(cfg.loop.count))
        self.main_screen.ids.loop_interval.text = str(int(cfg.loop.interval_ms))
        Snackbar(text=f"已导入：{path.name}").open()

    def _save_to_path(self, path: Path):
        cfg = self._collect_config()
        screen = ScreenSize(width=max(1, int(Window.width)), height=max(1, int(Window.height)))
        data = config_to_json_dict_v2(cfg, screen=screen)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        Snackbar(text=f"已保存：{path.name}").open()

    def _clamp_int(self, value: str, min_v: int, max_v: int, default: int) -> int:
        try:
            v = int(value)
        except Exception:  # noqa: BLE001
            return default
        return max(min_v, min(max_v, v))

    def start(self):
        if platform != "android":
            Snackbar(text="仅安卓可执行点击注入").open()
            return
        if self._running:
            return
        if not self.points:
            Snackbar(text="请先录入至少一个坐标点").open()
            return
        if not is_accessibility_enabled():
            self._confirm(
                "需要无障碍权限",
                "请在系统设置中开启本应用的无障碍服务后再开始。",
                lambda *_: open_accessibility_settings(),
            )
            return

        start_foreground_service()
        self._running = True
        self._paused = False
        self._cursor = 0
        self.main_screen.ids.btn_start.disabled = True
        self.main_screen.ids.btn_pause.disabled = False
        self.main_screen.ids.btn_stop.disabled = False
        self.main_screen.ids.btn_pause.text = "暂停"
        self.main_screen.ids.status_label.text = "运行"
        self._schedule_next(0)

    def pause_or_resume(self):
        if not self._running:
            return
        self._paused = not self._paused
        self.main_screen.ids.btn_pause.text = "继续" if self._paused else "暂停"
        self.main_screen.ids.status_label.text = "暂停" if self._paused else "运行"
        if not self._paused:
            self._schedule_next(0)

    def stop(self):
        if not self._running:
            return
        self._running = False
        self._paused = False
        self._cursor = 0
        if self._clock_ev is not None:
            try:
                self._clock_ev.cancel()
            except Exception:  # noqa: BLE001
                pass
            self._clock_ev = None
        stop_foreground_service()
        self.main_screen.ids.btn_start.disabled = False
        self.main_screen.ids.btn_pause.disabled = True
        self.main_screen.ids.btn_stop.disabled = True
        self.main_screen.ids.btn_pause.text = "暂停"
        self.main_screen.ids.status_label.text = "停止"
        Snackbar(text="已停止").open()

    def _schedule_next(self, delay_ms: int):
        if not self._running or self._paused:
            return
        delay_s = max(0.0, float(delay_ms) / 1000.0)
        self._clock_ev = Clock.schedule_once(lambda *_: self._do_step(), delay_s)

    def _do_step(self):
        if not self._running or self._paused:
            return
        interval = self._clamp_int(self.main_screen.ids.interval_input.text, 100, 5000, 500)
        screen = ScreenSize(width=max(1, int(Window.width)), height=max(1, int(Window.height)))

        point = self.points[self._cursor]
        x, y = point.to_pixels(screen)
        ok = send_click(int(x), int(y))
        if not ok:
            self.stop()
            Snackbar(text="点击发送失败：请确认无障碍服务已开启").open()
            return

        self._cursor += 1
        if self._cursor >= len(self.points):
            cfg = self._collect_config()
            if not cfg.loop.enabled:
                self.stop()
                self.main_screen.ids.status_label.text = "完成"
                Snackbar(text="执行完成").open()
                return
            self._cursor = 0
            if cfg.loop.infinite:
                self._schedule_next(cfg.loop.interval_ms)
                return
            self._cycle_done += 1
            if self._cycle_done >= max(1, int(cfg.loop.count)):
                self.stop()
                self.main_screen.ids.status_label.text = "完成"
                Snackbar(text="循环完成").open()
                self._cycle_done = 0
                return
            self._schedule_next(cfg.loop.interval_ms)
            return

        self._schedule_next(interval)


if __name__ == "__main__":
    AndroidClickerApp().run()
