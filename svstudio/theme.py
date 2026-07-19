COLORS = {
    "background": "#111418",
    "panel": "#171b21",
    "panel_alt": "#1d222a",
    "panel_hover": "#252b35",
    "border": "#2a3039",
    "border_bright": "#3b4450",
    "text": "#e8edf2",
    "muted": "#8b96a5",
    "subtle": "#626d7c",
    "green": "#53d397",
    "green_hover": "#69dfa8",
    "blue": "#6aa9ff",
    "orange": "#ffb86c",
    "red": "#ff6b78",
    "purple": "#bd93f9",
    "yellow": "#e9d26f",
    "editor": "#13171c",
    "selection": "#264d43",
}


APP_STYLESHEET = f"""
* {{
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 12px;
    color: {COLORS['text']};
}}
QMainWindow, QDialog {{ background: {COLORS['background']}; }}
QWidget {{ background: transparent; }}
QToolTip {{
    background: {COLORS['panel_alt']}; color: {COLORS['text']};
    border: 1px solid {COLORS['border_bright']}; padding: 5px;
}}
QMenuBar {{ background: {COLORS['panel']}; border-bottom: 1px solid {COLORS['border']}; padding: 2px; }}
QMenuBar::item {{ padding: 5px 9px; border-radius: 4px; }}
QMenuBar::item:selected {{ background: {COLORS['panel_hover']}; }}
QMenu {{ background: {COLORS['panel_alt']}; border: 1px solid {COLORS['border_bright']}; padding: 5px; }}
QMenu::item {{ padding: 6px 26px 6px 10px; border-radius: 4px; }}
QMenu::item:selected {{ background: {COLORS['selection']}; }}
QToolBar {{
    background: {COLORS['panel']}; border: none; border-bottom: 1px solid {COLORS['border']};
    spacing: 5px; padding: 6px 10px;
}}
QToolButton {{ border: 0; border-radius: 5px; padding: 6px 9px; background: transparent; }}
QToolButton:hover {{ background: {COLORS['panel_hover']}; }}
QToolButton:pressed {{ background: {COLORS['selection']}; }}
QPushButton {{
    background: {COLORS['panel_alt']}; border: 1px solid {COLORS['border_bright']};
    border-radius: 6px; padding: 6px 12px; font-weight: 600;
}}
QPushButton:hover {{ background: {COLORS['panel_hover']}; border-color: {COLORS['subtle']}; }}
QPushButton#primaryButton {{ background: {COLORS['green']}; color: #0d1c15; border: 0; }}
QPushButton#primaryButton:hover {{ background: {COLORS['green_hover']}; }}
QPushButton#dangerButton {{ color: {COLORS['red']}; }}
QLineEdit, QComboBox, QSpinBox {{
    background: {COLORS['background']}; border: 1px solid {COLORS['border_bright']};
    border-radius: 5px; padding: 5px 7px; selection-background-color: {COLORS['selection']};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {COLORS['green']}; }}
QComboBox::drop-down {{ border: 0; width: 20px; }}
QComboBox QAbstractItemView {{ background: {COLORS['panel_alt']}; selection-background-color: {COLORS['selection']}; }}
QTreeWidget, QListWidget, QTreeView, QTableWidget {{
    background: {COLORS['panel']}; border: 0; outline: 0; alternate-background-color: {COLORS['panel_alt']};
}}
QTreeWidget::item, QListWidget::item, QTreeView::item {{ padding: 4px; border-radius: 4px; }}
QTreeWidget::item:hover, QListWidget::item:hover, QTreeView::item:hover {{ background: {COLORS['panel_hover']}; }}
QTreeWidget::item:selected, QListWidget::item:selected, QTreeView::item:selected {{ background: {COLORS['selection']}; }}
QHeaderView::section {{ background: {COLORS['panel_alt']}; border: 0; border-right: 1px solid {COLORS['border']}; padding: 6px; }}
QTabWidget::pane {{ border: 0; background: {COLORS['panel']}; }}
QTabBar {{ background: {COLORS['panel']}; }}
QTabBar::tab {{
    background: {COLORS['panel']}; color: {COLORS['muted']}; padding: 8px 13px;
    border-right: 1px solid {COLORS['border']}; border-top: 2px solid transparent;
}}
QTabBar::tab:selected {{ color: {COLORS['text']}; background: {COLORS['editor']}; border-top-color: {COLORS['green']}; }}
QTabBar::tab:hover:!selected {{ background: {COLORS['panel_hover']}; }}
QPlainTextEdit, QTextEdit {{
    background: {COLORS['editor']}; border: 0; selection-background-color: {COLORS['selection']};
    selection-color: {COLORS['text']};
}}
QSplitter::handle {{ background: {COLORS['border']}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}
QScrollBar:vertical {{ background: {COLORS['panel']}; width: 11px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {COLORS['border_bright']}; min-height: 28px; border-radius: 5px; margin: 2px; }}
QScrollBar::handle:vertical:hover {{ background: {COLORS['subtle']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: {COLORS['panel']}; height: 11px; }}
QScrollBar::handle:horizontal {{ background: {COLORS['border_bright']}; min-width: 28px; border-radius: 5px; margin: 2px; }}
QStatusBar {{ background: {COLORS['panel']}; border-top: 1px solid {COLORS['border']}; color: {COLORS['muted']}; }}
QStatusBar::item {{ border: 0; }}
QLabel#sectionTitle {{ font-size: 10px; font-weight: 700; color: {COLORS['muted']}; letter-spacing: 1px; }}
QLabel#brand {{ font-size: 15px; font-weight: 800; }}
QLabel#muted {{ color: {COLORS['muted']}; }}
QLabel#successBadge {{ background: #173b2d; color: {COLORS['green']}; border-radius: 8px; padding: 3px 7px; font-weight: 700; }}
QLabel#demoBadge {{ background: #3c3019; color: {COLORS['orange']}; border-radius: 8px; padding: 3px 7px; font-weight: 700; }}
QFrame#card {{ background: {COLORS['panel_alt']}; border: 1px solid {COLORS['border']}; border-radius: 7px; }}
"""
