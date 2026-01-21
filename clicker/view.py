"""主界面实现。"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QCloseEvent, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStyledItemDelegate,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from clicker_core.model import ClickPoint


@dataclass(frozen=True, slots=True)
class LoopUiState:
    enabled: bool
    infinite: bool
    count: int
    interval_ms: int


@dataclass(frozen=True, slots=True)
class HotkeyUiState:
    enabled: bool
    start: str
    pause: str
    stop: str


class PointsTableWidget(QTableWidget):
    """支持拖拽排序的表格。"""

    orderChanged = pyqtSignal()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        super().dropEvent(event)
        self.orderChanged.emit()


class PointSpinDelegate(QStyledItemDelegate):
    """用 QSpinBox 编辑坐标单元格，确保输入实时有效。"""

    def __init__(self, get_bounds, parent=None) -> None:
        super().__init__(parent)
        self._get_bounds = get_bounds

    def createEditor(self, parent, option, index):  # type: ignore[override]
        editor = QSpinBox(parent)
        max_x, max_y = self._get_bounds()
        editor.setMinimum(0)
        if index.column() == 1:
            editor.setMaximum(max_x)
        elif index.column() == 2:
            editor.setMaximum(max_y)
        else:
            editor.setMaximum(99999)
        editor.setFrame(False)
        return editor

    def setEditorData(self, editor, index) -> None:  # type: ignore[override]
        try:
            value = int(index.data() or 0)
        except ValueError:
            value = 0
        editor.setValue(value)

    def setModelData(self, editor, model, index) -> None:  # type: ignore[override]
        model.setData(index, int(editor.value()))


class MainWindow(QMainWindow):
    """主窗口。"""

    addPointRequested = pyqtSignal(int, int)
    deletePointsRequested = pyqtSignal(list)
    loadRequested = pyqtSignal()
    saveRequested = pyqtSignal()
    saveAsRequested = pyqtSignal()
    recentFileRequested = pyqtSignal(str)
    startRequested = pyqtSignal()
    pauseRequested = pyqtSignal()
    resumeRequested = pyqtSignal()
    stopRequested = pyqtSignal()
    intervalChanged = pyqtSignal(int)
    loopUiChanged = pyqtSignal()
    hotkeyUiChanged = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("顺序连点器")
        self.resize(1100, 650)

        self._base_state = "准备"
        self._cycle_text = ""
        self._max_x = 99999
        self._max_y = 99999
        self._force_quit = False

        self._build_actions()
        self._build_ui()
        self._build_tray()

    def _build_actions(self) -> None:
        self.action_open = QAction("打开", self)
        self.action_save = QAction("保存", self)
        self.action_save_as = QAction("另存为", self)
        self.action_exit = QAction("退出", self)

        self.action_open.triggered.connect(self.loadRequested.emit)
        self.action_save.triggered.connect(self.saveRequested.emit)
        self.action_save_as.triggered.connect(self.saveAsRequested.emit)
        self.action_exit.triggered.connect(self.request_quit)

        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件")
        file_menu.addAction(self.action_open)
        file_menu.addAction(self.action_save)
        file_menu.addAction(self.action_save_as)
        file_menu.addSeparator()
        self.recent_menu = QMenu("最近打开", self)
        file_menu.addMenu(self.recent_menu)
        file_menu.addSeparator()
        file_menu.addAction(self.action_exit)

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)

        left = QWidget(self)
        left_layout = QVBoxLayout(left)

        input_row = QHBoxLayout()
        self.spin_x = QSpinBox()
        self.spin_y = QSpinBox()
        self.spin_x.setRange(0, 99999)
        self.spin_y.setRange(0, 99999)
        self.spin_x.setPrefix("X: ")
        self.spin_y.setPrefix("Y: ")

        self.btn_get_pos = QPushButton("获取当前位置")
        self.btn_add = QPushButton("添加")
        self.btn_delete = QPushButton("删除")

        input_row.addWidget(self.spin_x)
        input_row.addWidget(self.spin_y)
        input_row.addWidget(self.btn_get_pos)
        input_row.addWidget(self.btn_add)
        input_row.addWidget(self.btn_delete)
        input_row.addStretch(1)
        left_layout.addLayout(input_row)

        self.table = PointsTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["序号", "X", "Y"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self.table.setDragEnabled(True)
        self.table.setAcceptDrops(True)
        self.table.setDropIndicatorShown(True)
        self.table.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.table.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.table.setColumnWidth(0, 70)
        left_layout.addWidget(self.table, 1)

        self._point_delegate = PointSpinDelegate(self.point_edit_bounds, self.table)
        self.table.setItemDelegateForColumn(1, self._point_delegate)
        self.table.setItemDelegateForColumn(2, self._point_delegate)

        right = QWidget(self)
        right_layout = QVBoxLayout(right)

        group_controls = QGroupBox("控制")
        controls_layout = QHBoxLayout(group_controls)
        self.btn_start = QPushButton("开始")
        self.btn_pause = QPushButton("暂停")
        self.btn_stop = QPushButton("停止")
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        controls_layout.addWidget(self.btn_start)
        controls_layout.addWidget(self.btn_pause)
        controls_layout.addWidget(self.btn_stop)
        right_layout.addWidget(group_controls)

        group_params = QGroupBox("参数")
        params_layout = QFormLayout(group_params)
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(100, 5000)
        self.spin_interval.setSingleStep(100)
        self.spin_interval.setValue(500)
        self.spin_interval.setSuffix(" ms")
        params_layout.addRow("间隔时间", self.spin_interval)

        self.chk_loop = QCheckBox("启用循环")
        self.chk_infinite = QCheckBox("无限循环")
        self.spin_loop_count = QSpinBox()
        self.spin_loop_count.setRange(1, 999)
        self.spin_loop_count.setValue(1)
        self.spin_loop_interval = QSpinBox()
        self.spin_loop_interval.setRange(0, 10000)
        self.spin_loop_interval.setSingleStep(100)
        self.spin_loop_interval.setValue(0)
        self.spin_loop_interval.setSuffix(" ms")

        loop_row = QWidget()
        loop_row_layout = QVBoxLayout(loop_row)
        loop_row_layout.setContentsMargins(0, 0, 0, 0)
        loop_row_layout.addWidget(self.chk_loop)
        loop_line = QHBoxLayout()
        loop_line.addWidget(QLabel("次数"))
        loop_line.addWidget(self.spin_loop_count)
        loop_line.addWidget(self.chk_infinite)
        loop_row_layout.addLayout(loop_line)
        loop_line2 = QHBoxLayout()
        loop_line2.addWidget(QLabel("循环间隔"))
        loop_line2.addWidget(self.spin_loop_interval)
        loop_row_layout.addLayout(loop_line2)
        params_layout.addRow("循环设置", loop_row)

        self.chk_hotkeys = QCheckBox("启用全局热键")
        self.edit_hotkey_start = QLineEdit("ctrl+shift+s")
        self.edit_hotkey_pause = QLineEdit("ctrl+shift+p")
        self.edit_hotkey_stop = QLineEdit("ctrl+shift+x")
        params_layout.addRow(self.chk_hotkeys)
        params_layout.addRow("开始热键", self.edit_hotkey_start)
        params_layout.addRow("暂停热键", self.edit_hotkey_pause)
        params_layout.addRow("停止热键", self.edit_hotkey_stop)

        right_layout.addWidget(group_params, 1)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        self.setCentralWidget(splitter)

        status = QStatusBar(self)
        self.label_status = QLabel("准备")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        status.addWidget(self.label_status, 1)
        status.addPermanentWidget(self.progress, 1)
        self.setStatusBar(status)

        self.btn_get_pos.clicked.connect(self._on_get_pos_clicked)
        self.btn_add.clicked.connect(self._on_add_clicked)
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        self.btn_start.clicked.connect(self.startRequested.emit)
        self.btn_stop.clicked.connect(self.stopRequested.emit)
        self.btn_pause.clicked.connect(self._on_pause_clicked)
        self.spin_interval.valueChanged.connect(self.intervalChanged.emit)

        self.chk_loop.stateChanged.connect(self.loopUiChanged.emit)
        self.chk_infinite.stateChanged.connect(self.loopUiChanged.emit)
        self.spin_loop_count.valueChanged.connect(self.loopUiChanged.emit)
        self.spin_loop_interval.valueChanged.connect(self.loopUiChanged.emit)

        self.chk_hotkeys.stateChanged.connect(self.hotkeyUiChanged.emit)
        self.edit_hotkey_start.textChanged.connect(self.hotkeyUiChanged.emit)
        self.edit_hotkey_pause.textChanged.connect(self.hotkeyUiChanged.emit)
        self.edit_hotkey_stop.textChanged.connect(self.hotkeyUiChanged.emit)

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self._icon_for_state("准备"))
        tray_menu = QMenu()
        self.tray_action_show = QAction("显示/隐藏", self)
        self.tray_action_start = QAction("开始", self)
        self.tray_action_pause = QAction("暂停", self)
        self.tray_action_stop = QAction("停止", self)
        self.tray_action_exit = QAction("退出", self)
        tray_menu.addAction(self.tray_action_show)
        tray_menu.addSeparator()
        tray_menu.addAction(self.tray_action_start)
        tray_menu.addAction(self.tray_action_pause)
        tray_menu.addAction(self.tray_action_stop)
        tray_menu.addSeparator()
        tray_menu.addAction(self.tray_action_exit)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._on_tray_activated)

        self.tray_action_show.triggered.connect(self._toggle_visible)
        self.tray_action_start.triggered.connect(self.startRequested.emit)
        self.tray_action_stop.triggered.connect(self.stopRequested.emit)
        self.tray_action_pause.triggered.connect(self._on_pause_clicked)
        self.tray_action_exit.triggered.connect(self.request_quit)

        self.tray.show()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._force_quit:
            event.accept()
            return
        if QSystemTrayIcon.isSystemTrayAvailable():
            event.ignore()
            self.hide()
            self.notify_info("已最小化到系统托盘")
            return
        event.accept()

    def request_quit(self) -> None:
        self._force_quit = True
        self.close()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            if QSystemTrayIcon.isSystemTrayAvailable():
                QTimer.singleShot(0, self.hide)
                self.notify_info("已最小化到系统托盘")
        super().changeEvent(event)

    def _icon_for_state(self, state: str) -> QIcon:
        style = QApplication.style()
        if state == "运行":
            return style.standardIcon(style.StandardPixmap.SP_MediaPlay)
        if state == "暂停":
            return style.standardIcon(style.StandardPixmap.SP_MediaPause)
        if state == "停止":
            return style.standardIcon(style.StandardPixmap.SP_MediaStop)
        if state == "错误":
            return style.standardIcon(style.StandardPixmap.SP_MessageBoxCritical)
        return style.standardIcon(style.StandardPixmap.SP_ComputerIcon)

    def _on_get_pos_clicked(self) -> None:
        try:
            import pyautogui

            pos = pyautogui.position()
            self.spin_x.setValue(int(pos.x))
            self.spin_y.setValue(int(pos.y))
        except Exception as exc:  # noqa: BLE001
            self.show_error(f"获取坐标失败：{exc}")

    def _on_add_clicked(self) -> None:
        self.addPointRequested.emit(int(self.spin_x.value()), int(self.spin_y.value()))

    def _on_delete_clicked(self) -> None:
        rows = sorted({idx.row() for idx in self.table.selectionModel().selectedRows()})
        if not rows:
            return
        confirm = QMessageBox.question(
            self,
            "确认删除",
            f"确定删除选中的 {len(rows)} 个坐标点吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.deletePointsRequested.emit(rows)

    def _on_pause_clicked(self) -> None:
        if self.btn_pause.text() == "暂停":
            self.pauseRequested.emit()
        else:
            self.resumeRequested.emit()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_visible()

    def _toggle_visible(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def update_points(self, points: list[ClickPoint]) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for i, p in enumerate(points, start=1):
            row = self.table.rowCount()
            self.table.insertRow(row)
            item_index = QTableWidgetItem(str(i))
            item_index.setFlags(item_index.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, item_index)
            self.table.setItem(row, 1, QTableWidgetItem(str(int(round(p.x)))))
            self.table.setItem(row, 2, QTableWidgetItem(str(int(round(p.y)))))
        self.table.blockSignals(False)

    def set_point_bounds(self, max_x: int, max_y: int) -> None:
        self._max_x = max(0, int(max_x))
        self._max_y = max(0, int(max_y))
        self.spin_x.setRange(0, self._max_x)
        self.spin_y.setRange(0, self._max_y)

    def point_edit_bounds(self) -> tuple[int, int]:
        return self._max_x, self._max_y

    def points_from_table(self) -> list[ClickPoint]:
        points: list[ClickPoint] = []
        for row in range(self.table.rowCount()):
            x_item = self.table.item(row, 1)
            y_item = self.table.item(row, 2)
            try:
                x = int(x_item.text()) if x_item else 0
                y = int(y_item.text()) if y_item else 0
            except ValueError:
                x, y = 0, 0
            points.append(ClickPoint.from_abs(x=x, y=y))
        return points

    def refresh_indices(self) -> None:
        for row in range(self.table.rowCount()):
            item_index = self.table.item(row, 0)
            if item_index is not None:
                item_index.setText(str(row + 1))

    def set_state(self, state: str) -> None:
        self._base_state = state
        self._refresh_status_label()
        self.tray.setIcon(self._icon_for_state(state))
        self.tray.setToolTip(f"顺序连点器 - {state}")

    def set_cycle(self, current: int, total: int) -> None:
        if total > 0:
            self._cycle_text = f"（循环 {current}/{total}）"
        else:
            self._cycle_text = f"（循环 {current}/∞）"
        self._refresh_status_label()

    def clear_cycle(self) -> None:
        self._cycle_text = ""
        self._refresh_status_label()

    def _refresh_status_label(self) -> None:
        self.label_status.setText(f"{self._base_state}{self._cycle_text}")

    def set_running_controls(self, running: bool, paused: bool = False) -> None:
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.btn_pause.setEnabled(running)
        self.btn_pause.setText("继续" if paused else "暂停")

        self.tray_action_start.setEnabled(not running)
        self.tray_action_stop.setEnabled(running)
        self.tray_action_pause.setEnabled(running)
        self.tray_action_pause.setText("继续" if paused else "暂停")

    def set_progress(self, current: int, total: int) -> None:
        if total <= 0:
            self.progress.setValue(0)
            self.progress.setFormat("")
            return
        percent = int((current / total) * 100)
        self.progress.setValue(percent)
        self.progress.setFormat(f"{current}/{total}")

    def update_recent_files(self, paths: list[str]) -> None:
        self.recent_menu.clear()
        if not paths:
            action = QAction("(空)", self)
            action.setEnabled(False)
            self.recent_menu.addAction(action)
            return
        for p in paths:
            act = QAction(p, self)
            act.triggered.connect(lambda _, x=p: self.recentFileRequested.emit(x))
            self.recent_menu.addAction(act)

    def loop_ui_state(self) -> LoopUiState:
        return LoopUiState(
            enabled=self.chk_loop.isChecked(),
            infinite=self.chk_infinite.isChecked(),
            count=int(self.spin_loop_count.value()),
            interval_ms=int(self.spin_loop_interval.value()),
        )

    def hotkey_ui_state(self) -> HotkeyUiState:
        return HotkeyUiState(
            enabled=self.chk_hotkeys.isChecked(),
            start=self.edit_hotkey_start.text().strip(),
            pause=self.edit_hotkey_pause.text().strip(),
            stop=self.edit_hotkey_stop.text().strip(),
        )

    def show_error(self, message: str) -> None:
        self.set_state("错误")
        QMessageBox.critical(self, "错误", message)
        if self.tray.supportsMessages():
            self.tray.showMessage("顺序连点器", message, QSystemTrayIcon.MessageIcon.Critical)

    def notify_info(self, message: str) -> None:
        if self.tray.supportsMessages():
            self.tray.showMessage("顺序连点器", message, QSystemTrayIcon.MessageIcon.Information)
