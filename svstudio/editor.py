from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QSyntaxHighlighter, QTextCharFormat, QTextCursor, QTextFormat
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from .theme import COLORS


class LineNumberArea(QWidget):
    def __init__(self, editor: "CodeEditor"):
        super().__init__(editor)
        self.editor = editor
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:
        self.editor.line_number_area_paint_event(event)

    def mousePressEvent(self, event) -> None:
        block = self.editor.firstVisibleBlock()
        top = self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top()
        while block.isValid():
            bottom = top + self.editor.blockBoundingRect(block).height()
            if top <= event.position().y() <= bottom:
                self.editor.toggle_breakpoint(block.blockNumber() + 1)
                return
            block = block.next()
            top = bottom


class SystemVerilogHighlighter(QSyntaxHighlighter):
    KEYWORDS = (
        "always always_comb always_ff always_latch and assign automatic begin bit break byte "
        "case casex casez cell chandle class clocking config const constraint continue cover "
        "covergroup coverpoint cross deassign default defparam design disable dist do edge else "
        "end endcase endclass endclocking endconfig endfunction endgenerate endgroup endinterface "
        "endmodule endpackage endprimitive endprogram endproperty endsequence endspecify endtable "
        "endtask enum event expect export extends extern final first_match for force foreach forever "
        "fork forkjoin function generate genvar highz0 highz1 if iff ifnone ignore_bins illegal_bins "
        "implements implies import incdir include initial inout input inside int integer interconnect "
        "interface intersect join join_any join_none large let liblist library local localparam logic "
        "longint macromodule matches medium modport module nand negedge nettype new nmos nor noshowcancelled "
        "not notif0 notif1 null or output package packed parameter pmos posedge primitive priority program "
        "property protected pull0 pull1 pulldown pullup pure rand randc randcase randsequence rcmos real "
        "realtime ref reg release repeat restrict return rnmos rpmos rtran rtranif0 rtranif1 scalared "
        "sequence shortint shortreal showcancelled signed small solve specify specparam static string strong "
        "strong0 strong1 struct super supply0 supply1 sync_accept_on sync_reject_on table tagged task this "
        "throughout time timeprecision timeunit tran tranif0 tranif1 tri tri0 tri1 triand trior trireg type "
        "typedef union unique unique0 unsigned use uwire var vectored virtual void wait wait_order wand weak "
        "weak0 weak1 while wildcard wire with within wor xnor xor"
    ).split()

    def __init__(self, document):
        super().__init__(document)
        self.rules: list[tuple[re.Pattern[str], QTextCharFormat]] = []

        def fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
            value = QTextCharFormat()
            value.setForeground(QColor(color))
            value.setFontWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
            value.setFontItalic(italic)
            return value

        keyword_fmt = fmt(COLORS["purple"], True)
        type_fmt = fmt(COLORS["blue"])
        macro_fmt = fmt(COLORS["green"])
        number_fmt = fmt(COLORS["orange"])
        string_fmt = fmt(COLORS["yellow"])
        comment_fmt = fmt(COLORS["subtle"], italic=True)

        self.rules.append((re.compile(r"\b(?:" + "|".join(self.KEYWORDS) + r")\b"), keyword_fmt))
        self.rules.append((re.compile(r"\b(?:uvm_[A-Za-z0-9_]+|logic|bit|int|string|time)\b"), type_fmt))
        self.rules.append((re.compile(r"`(?:uvm_[A-Za-z0-9_]+|define|include|ifdef|ifndef|endif|timescale)\b"), macro_fmt))
        self.rules.append((re.compile(r"\b(?:\d+'[sS]?[bodhBODH][0-9a-fA-F_xXzZ]+|\d+(?:\.\d+)?)\b"), number_fmt))
        self.rules.append((re.compile(r'"(?:\\.|[^"\\])*"'), string_fmt))
        self.rules.append((re.compile(r"//.*$"), comment_fmt))
        self.comment_format = comment_fmt

    def highlightBlock(self, text: str) -> None:
        for pattern, text_format in self.rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), text_format)

        self.setCurrentBlockState(0)
        start = 0
        if self.previousBlockState() != 1:
            start = text.find("/*")
        while start >= 0:
            end = text.find("*/", start + 2)
            if end < 0:
                self.setCurrentBlockState(1)
                length = len(text) - start
            else:
                length = end - start + 2
            self.setFormat(start, length, self.comment_format)
            start = text.find("/*", start + length)


class CodeEditor(QPlainTextEdit):
    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self.path = path
        self.breakpoints: set[int] = set()
        self.line_number_area = LineNumberArea(self)
        self.highlighter = SystemVerilogHighlighter(self.document())
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFont("Cascadia Code")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(10)
        self.setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.update_line_number_area_width(0)
        self.highlight_current_line()

    def line_number_area_width(self) -> int:
        digits = max(2, len(str(max(1, self.blockCount()))))
        return 22 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_line_number_area_width(self, _) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        contents = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(contents.left(), contents.top(), self.line_number_area_width(), contents.height())
        )

    def line_number_area_paint_event(self, event) -> None:
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor(COLORS["panel"]))
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        current_line = self.textCursor().blockNumber() + 1

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                line = block_number + 1
                color = COLORS["text"] if line == current_line else COLORS["subtle"]
                painter.setPen(QColor(color))
                painter.drawText(
                    16,
                    top,
                    self.line_number_area.width() - 20,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    str(line),
                )
                if line in self.breakpoints:
                    painter.setBrush(QColor(COLORS["red"]))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(5, top + 5, 7, 7)
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def toggle_breakpoint(self, line: int) -> None:
        if line in self.breakpoints:
            self.breakpoints.remove(line)
        else:
            self.breakpoints.add(line)
        self.line_number_area.update()

    def highlight_current_line(self) -> None:
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor("#191f25"))
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])
        self.line_number_area.update()

    def go_to_line(self, line: int) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, max(0, line - 1))
        self.setTextCursor(cursor)
        self.centerCursor()
        self.setFocus()
