from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .theme import COLORS
from .vcd import VCDData, VCDSignal, parse_vcd, value_at


class WaveformCanvas(QWidget):
    cursor_changed = Signal(int)

    def __init__(self):
        super().__init__()
        self.data = VCDData()
        self.signals: list[VCDSignal] = []
        self.view_start = 0.0
        self.view_end = 100.0
        self.cursor_time = 0
        self.row_height = 42
        self.setMinimumWidth(700)
        self.setMinimumHeight(180)
        self.setMouseTracking(True)

    def set_data(self, data: VCDData, signals: list[VCDSignal] | None = None) -> None:
        self.data = data
        self.signals = signals if signals is not None else data.signals
        self.view_start = 0
        self.view_end = max(1, data.end_time)
        self.setMinimumHeight(max(180, 36 + len(self.signals) * self.row_height))
        self.update()

    def set_signals(self, signals: list[VCDSignal]) -> None:
        self.signals = signals
        self.setMinimumHeight(max(180, 36 + len(self.signals) * self.row_height))
        self.update()

    def zoom(self, factor: float) -> None:
        span = max(1.0, self.view_end - self.view_start)
        center = (self.view_start + self.view_end) / 2
        new_span = max(2.0, min(max(2.0, self.data.end_time), span * factor))
        self.view_start = max(0.0, center - new_span / 2)
        self.view_end = min(max(1.0, self.data.end_time), self.view_start + new_span)
        self.view_start = max(0.0, self.view_end - new_span)
        self.update()

    def zoom_all(self) -> None:
        self.view_start = 0
        self.view_end = max(1, self.data.end_time)
        self.update()

    def _time_to_x(self, value: float) -> float:
        usable = max(1, self.width() - 18)
        return 9 + (value - self.view_start) / max(1, self.view_end - self.view_start) * usable

    def _x_to_time(self, x: float) -> int:
        usable = max(1, self.width() - 18)
        ratio = max(0.0, min(1.0, (x - 9) / usable))
        return round(self.view_start + ratio * (self.view_end - self.view_start))

    def mousePressEvent(self, event) -> None:
        self.cursor_time = self._x_to_time(event.position().x())
        self.cursor_changed.emit(self.cursor_time)
        self.update()

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom(0.75 if event.angleDelta().y() > 0 else 1.35)
            event.accept()
            return
        super().wheelEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.rect(), QColor(COLORS["editor"]))
        if not self.signals:
            painter.setPen(QColor(COLORS["muted"]))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Run a test or open a VCD file to inspect signals")
            return

        top = 28
        span = max(1.0, self.view_end - self.view_start)
        step = self._nice_step(span / 8)
        first = int(self.view_start // step) * step
        painter.setFont(QFont("Cascadia Code", 8))
        grid_pen = QPen(QColor("#252b33"), 1)
        text_pen = QPen(QColor(COLORS["subtle"]), 1)
        tick = first
        while tick <= self.view_end:
            x = self._time_to_x(tick)
            painter.setPen(grid_pen)
            painter.drawLine(int(x), top, int(x), self.height())
            painter.setPen(text_pen)
            painter.drawText(int(x) + 4, 18, f"{tick:g} {self.data.timescale}")
            tick += step

        for index, signal in enumerate(self.signals):
            y_top = top + index * self.row_height
            painter.setPen(QColor("#20262e"))
            painter.drawLine(0, y_top + self.row_height - 1, self.width(), y_top + self.row_height - 1)
            self._draw_signal(painter, signal, y_top)

        cursor_x = self._time_to_x(self.cursor_time)
        painter.setPen(QPen(QColor(COLORS["orange"]), 1))
        painter.drawLine(int(cursor_x), top - 5, int(cursor_x), self.height())
        painter.fillRect(int(cursor_x) - 17, 0, 34, 16, QColor(COLORS["orange"]))
        painter.setPen(QColor("#21170c"))
        painter.drawText(int(cursor_x) - 15, 12, str(self.cursor_time))

    @staticmethod
    def _nice_step(raw: float) -> float:
        if raw <= 0:
            return 1
        magnitude = 1.0
        while raw >= 10:
            raw /= 10
            magnitude *= 10
        while raw < 1:
            raw *= 10
            magnitude /= 10
        nice = 1 if raw < 2 else 2 if raw < 5 else 5
        return nice * magnitude

    def _draw_signal(self, painter: QPainter, signal: VCDSignal, y_top: int) -> None:
        changes = signal.changes
        if not changes:
            return
        visible: list[tuple[int, str]] = []
        previous = changes[0]
        for change in changes:
            if change[0] <= self.view_start:
                previous = change
            elif change[0] <= self.view_end:
                visible.append(change)
        visible.insert(0, (int(self.view_start), previous[1]))
        visible.append((int(self.view_end), visible[-1][1]))
        wave_pen = QPen(QColor(COLORS["green"]), 2)
        unknown_pen = QPen(QColor(COLORS["red"]), 2)

        if signal.width == 1:
            high_y, low_y, mid_y = y_top + 8, y_top + 31, y_top + 20
            for index in range(len(visible) - 1):
                time, value = visible[index]
                next_time = visible[index + 1][0]
                x1, x2 = self._time_to_x(time), self._time_to_x(next_time)
                if value == "1":
                    y = high_y
                elif value == "0":
                    y = low_y
                else:
                    y = mid_y
                painter.setPen(wave_pen if value in {"0", "1"} else unknown_pen)
                painter.drawLine(int(x1), y, int(x2), y)
                if index:
                    previous_value = visible[index - 1][1]
                    previous_y = high_y if previous_value == "1" else low_y if previous_value == "0" else mid_y
                    painter.drawLine(int(x1), previous_y, int(x1), y)
        else:
            upper, lower = y_top + 9, y_top + 31
            for index in range(len(visible) - 1):
                time, value = visible[index]
                next_time = visible[index + 1][0]
                x1, x2 = self._time_to_x(time), self._time_to_x(next_time)
                painter.setPen(wave_pen if "x" not in value and "z" not in value else unknown_pen)
                painter.drawLine(int(x1), upper, int(x2), upper)
                painter.drawLine(int(x1), lower, int(x2), lower)
                painter.drawLine(int(x1), upper, int(x1) + 5, lower)
                if x2 - x1 > 34:
                    try:
                        label = f"0x{int(value, 2):X}"
                    except ValueError:
                        label = value.upper()
                    painter.setPen(QColor(COLORS["muted"]))
                    painter.drawText(int(x1) + 8, y_top + 25, label)


class WaveformPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.data = VCDData()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(10, 6, 10, 6)
        title = QLabel("VCD WAVEFORM")
        title.setObjectName("sectionTitle")
        toolbar.addWidget(title)
        toolbar.addStretch()
        self.cursor_label = QLabel("Cursor  0 ns")
        self.cursor_label.setObjectName("muted")
        toolbar.addWidget(self.cursor_label)
        for text, tooltip, callback in (
            ("−", "Zoom out", lambda: self.canvas.zoom(1.35)),
            ("+", "Zoom in", lambda: self.canvas.zoom(0.75)),
            ("Fit", "Zoom to full simulation", self._zoom_all),
        ):
            button = QPushButton(text)
            button.setToolTip(tooltip)
            button.setMaximumHeight(27)
            button.clicked.connect(callback)
            toolbar.addWidget(button)
        root.addLayout(toolbar)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.signal_list = QListWidget()
        self.signal_list.setMinimumWidth(210)
        self.signal_list.itemChanged.connect(self._selection_changed)
        split.addWidget(self.signal_list)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.canvas = WaveformCanvas()
        self.canvas.cursor_changed.connect(self._cursor_changed)
        scroll.setWidget(self.canvas)
        split.addWidget(scroll)
        split.setSizes([240, 900])
        root.addWidget(split)

    def load_file(self, path: Path) -> None:
        self.data = parse_vcd(path)
        self.signal_list.blockSignals(True)
        self.signal_list.clear()
        for signal in self.data.signals:
            item = QListWidgetItem(signal.name)
            item.setData(Qt.ItemDataRole.UserRole, signal)
            item.setCheckState(Qt.CheckState.Checked)
            self.signal_list.addItem(item)
        self.signal_list.blockSignals(False)
        self.canvas.set_data(self.data)
        self._cursor_changed(0)

    def _selection_changed(self) -> None:
        selected = []
        for index in range(self.signal_list.count()):
            item = self.signal_list.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.data(Qt.ItemDataRole.UserRole))
        self.canvas.set_signals(selected)

    def _cursor_changed(self, time: int) -> None:
        values = []
        for signal in self.canvas.signals[:2]:
            values.append(f"{signal.name.split('.')[-1]}={value_at(signal, time)}")
        suffix = "  ·  " + "  ".join(values) if values else ""
        self.cursor_label.setText(f"Cursor  {time} {self.data.timescale}{suffix}")

    def _zoom_all(self) -> None:
        self.canvas.zoom_all()
