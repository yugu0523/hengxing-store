"""通用 UI 组件 — Toast、MsgBox、DropdownSelect、StatCard、icon_badge 等"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QFrame, QScrollArea, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
    QSizePolicy, QStyle, QStyledItemDelegate, QDialog,
)
from PyQt6.QtCore import Qt, QPoint, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QEvent
from PyQt6.QtGui import QPalette, QColor

from core.config import get_app_dir
from ui.theme import t, T, IS_DARK, CAT_COLORS, _color_for


# ── 红字委托 ──
class RedTextDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        opt = option.__class__(option)
        self.initStyleOption(opt, index)
        opt.palette.setColor(QPalette.ColorRole.Text, QColor("#ef4444"))
        opt.palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ef4444"))
        opt.widget.style().drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)


def add_shadow(w, blur=24, alpha=60):
    e = QGraphicsDropShadowEffect()
    e.setBlurRadius(blur)
    e.setOffset(0, 4)
    e.setColor(QColor(0, 0, 0, alpha))
    w.setGraphicsEffect(e)


# ── Toast ──
class Toast(QWidget):
    def __init__(self, parent, msg: str):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.Tool |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._eff = QGraphicsOpacityEffect(self)
        self._eff.setOpacity(0.0)
        self.setGraphicsEffect(self._eff)

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)

        box = QFrame()
        box.setFixedHeight(44)
        box.setStyleSheet(f"""
            QFrame {{
                background: {t('accent')};
                border-radius: 15px;
            }}
        """)
        sh = QGraphicsDropShadowEffect()
        sh.setBlurRadius(24)
        sh.setOffset(0, 4)
        sh.setColor(QColor(251, 114, 153, 90))
        box.setGraphicsEffect(sh)

        bl = QHBoxLayout(box)
        bl.setContentsMargins(24, 0, 24, 0)

        txt_lbl = QLabel(msg)
        txt_lbl.setStyleSheet(
            "background: transparent;"
            "color: white;"
            "font-size: 15px; font-weight: 700;"
            "font-family: 'Microsoft YaHei';"
        )
        txt_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bl.addWidget(txt_lbl)

        root.addWidget(box)
        self.adjustSize()

    def _reposition(self):
        p = self.parent()
        if p:
            pw, ph = p.width(), p.height()
            self.move((pw - self.width()) // 2, (ph - self.height()) // 2)

    def _run(self, stay_ms: int = 1800):
        self._reposition()
        self.show()
        self.raise_()

        self._anim_in = QPropertyAnimation(self._eff, b"opacity", self)
        self._anim_in.setDuration(250)
        self._anim_in.setStartValue(0.0)
        self._anim_in.setEndValue(1.0)
        self._anim_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim_in.start()

        QTimer.singleShot(stay_ms, self._fade_out)

    def _fade_out(self):
        self._anim_out = QPropertyAnimation(self._eff, b"opacity", self)
        self._anim_out.setDuration(350)
        self._anim_out.setStartValue(1.0)
        self._anim_out.setEndValue(0.0)
        self._anim_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim_out.finished.connect(self.deleteLater)
        self._anim_out.start()

    @staticmethod
    def show_msg(parent, msg: str, stay_ms: int = 1800):
        t_widget = Toast(parent, msg)
        t_widget._run(stay_ms)


def icon_badge(icon: str, bg: str, size: int = 44, radius: int = 12) -> QLabel:
    w = QLabel(icon)
    w.setFixedSize(size, size)
    w.setAlignment(Qt.AlignmentFlag.AlignCenter)
    w.setStyleSheet(f"QLabel{{background:{bg};border-radius:{radius}px;"
                    f"font-size:{size // 2}px;color:#ffffff;}}")
    return w


# ── DropdownSelect ──
class DropdownSelect(QWidget):
    value_changed = pyqtSignal(str)

    def __init__(self, items=None, parent=None):
        super().__init__(parent)
        self._items = items or []
        self._popup = None
        self._build()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        container = QFrame()
        container.setFixedHeight(34)
        container.setStyleSheet(f"""
            QFrame {{
                background: {t('input_bg')};
                border: 1.5px solid {t('border')};
                border-radius: 17px;
            }}
        """)
        container.setCursor(Qt.CursorShape.PointingHandCursor)
        cl = QHBoxLayout(container)
        cl.setContentsMargins(14, 0, 10, 0)
        cl.setSpacing(0)

        self._edit = QLineEdit()
        self._edit.setReadOnly(True)
        self._edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self._edit.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: """ + t('text') + """;
                font-size: 13px;
                font-family: "Microsoft YaHei";
            }
        """)
        if self._items:
            self._edit.setText(self._items[0])
        self._edit.mousePressEvent = lambda e: self._toggle_popup()

        self._arrow = QLabel("▾")
        self._arrow.setFixedSize(20, 34)
        self._arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._arrow.setStyleSheet(
            f"color: {t('text_sub')}; font-size: 14px; background: transparent; border: none;")
        self._arrow.setCursor(Qt.CursorShape.PointingHandCursor)
        self._arrow.mousePressEvent = lambda e: self._toggle_popup()

        cl.addWidget(self._edit)
        cl.addWidget(self._arrow)
        lay.addWidget(container)
        self._container = container

    def set_items(self, items):
        self._items = items
        if items and not self._edit.text():
            self._edit.setText(items[0])

    def current_text(self):
        return self._edit.text()

    def set_current_text(self, text):
        self._edit.setText(text)

    def _toggle_popup(self):
        if self._popup and self._popup.isVisible():
            self._popup.hide()
            return
        self._show_popup()

    def _show_popup(self):
        if self._popup:
            self._popup.deleteLater()

        popup = QFrame(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        popup.setStyleSheet("background: transparent; border: none;")

        outer = QVBoxLayout(popup)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        inner = QFrame()
        inner.setStyleSheet(f"""
            QFrame {{
                background: {t('card')};
                border: 1.5px solid {t('border')};
                border-radius: 12px;
            }}
        """)

        il = QVBoxLayout(inner)
        il.setContentsMargins(6, 6, 6, 6)
        il.setSpacing(0)

        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sa.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ background: {t('card2')}; width: 4px; border-radius: 2px; }}
            QScrollBar::handle:vertical {{ background: {t('border')}; border-radius: 2px; min-height: 20px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        pl = QVBoxLayout(content)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(2)

        for item in self._items:
            btn = QPushButton(item)
            btn.setFlat(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(36)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-radius: 8px;
                    color: {t('text')};
                    font-size: 13px;
                    text-align: left;
                    padding: 0 12px;
                    font-family: "Microsoft YaHei";
                }}
                QPushButton:hover {{
                    background: {t('sel')};
                    color: {t('accent')};
                }}
            """)
            btn.clicked.connect(lambda _, v=item: self._select(v, popup))
            pl.addWidget(btn)

        sa.setWidget(content)
        max_h = 8 * 36 + 7 * 2 + 12
        sa.setFixedHeight(min(len(self._items) * 38 + 12, max_h))

        il.addWidget(sa)
        outer.addWidget(inner)

        w = self._container.width()
        gpos = self._container.mapToGlobal(QPoint(0, self._container.height() + 2))
        popup.setFixedWidth(w)
        inner.setFixedWidth(w)
        sa.setFixedWidth(w)
        popup.adjustSize()
        popup.move(gpos)
        popup.show()
        self._popup = popup

    def _select(self, value, popup):
        self._edit.setText(value)
        popup.hide()
        self.value_changed.emit(value)


def cat_badge(cat: str) -> QLabel:
    color = _color_for(cat)
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    alpha = t('badge_alpha')
    bg = f"rgba({r},{g},{b},{alpha})"
    w = QLabel(cat)
    w.setAlignment(Qt.AlignmentFlag.AlignCenter)
    w.setStyleSheet(f"QLabel{{background:{bg};color:{color};border-radius:6px;"
                    f"padding:2px 10px;font-size:12px;font-weight:600;}}")
    return w


# ── StatCard ──
class StatCard(QFrame):
    def __init__(self, icon, ic_key, label, value_text, color, parent=None):
        super().__init__(parent)
        self._icon = icon
        self._ic_key = ic_key
        self._label = label
        self._color = color
        self.setObjectName("card")
        self.setMinimumHeight(96)
        add_shadow(self, 24, 40 if IS_DARK else 12)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(16)

        self._badge = icon_badge(icon, t(ic_key), 48, 14)
        lay.addWidget(self._badge)

        col = QVBoxLayout()
        col.setSpacing(4)
        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(f"color:{t('text_sub')};font-size:12px;")
        self._val = QLabel(value_text)
        self._val.setStyleSheet(f"color:{color};font-size:22px;font-weight:800;")
        col.addWidget(self._lbl)
        col.addWidget(self._val)
        lay.addLayout(col)
        lay.addStretch()

    def set_value(self, v):
        self._val.setText(v)

    def refresh_theme(self):
        self._badge.setStyleSheet(f"QLabel{{background:{t(self._ic_key)};border-radius:14px;"
                                  f"font-size:24px;color:#ffffff;}}")
        self._lbl.setStyleSheet(f"color:{t('text_sub')};font-size:12px;")
        self._val.setStyleSheet(f"color:{self._color};font-size:22px;font-weight:800;")
        add_shadow(self, 24, 40 if IS_DARK else 12)


# ── MsgBox ──
class MsgBox(QDialog):
    ICONS = {"info": "ℹ️", "warning": "⚠️", "question": "🗑️", "success": "✅", "error": "❌"}
    COLORS = {
        "info":     "#3b82f6",
        "warning":  "#f97316",
        "question": "#ef4444",
        "success":  "#22c55e",
        "error":    "#ef4444",
    }

    def __init__(self, parent, type_="info", title="提示", msg=""):
        super().__init__(parent)
        self._confirmed = False
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(400)
        self._build(type_, title, msg)
        self._center()

    def _center(self):
        p = self.parent()
        if p:
            self.move(p.x() + (p.width() - self.width()) // 2,
                      p.y() + (p.height() - self.height()) // 2)

    def _build(self, type_, title, msg):
        color = self.COLORS.get(type_, "#6366f1")
        icon  = self.ICONS.get(type_, "ℹ️")
        is_question = (type_ == "question")

        bg = "#f2f2f5" if not IS_DARK else t('surface')
        self.setStyleSheet(f"""
            QDialog {{ background: transparent; }}
            #msgbox_container {{
                background:{bg};
                border:2px solid {t('accent')};
                border-radius:16px;
            }}
            QLabel {{ background:transparent; color:{t('text')}; }}
            QPushButton {{ font-family:"Microsoft YaHei"; }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(0)

        container = QWidget()
        container.setObjectName("msgbox_container")
        add_shadow(container, 32, 80 if IS_DARK else 30)
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        root.addWidget(container)

        bar = QWidget()
        bar.setFixedHeight(4)
        bar.setStyleSheet(f"background:{t('accent')}; border-radius:16px 16px 0 0;")
        cl.addWidget(bar)

        body = QWidget()
        body.setStyleSheet(f"background:{bg}; border-radius:0 0 16px 16px;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(28, 24, 28, 24)
        bl.setSpacing(16)

        title_row = QHBoxLayout()
        title_row.setSpacing(14)
        ic_lbl = QLabel(icon)
        ic_lbl.setStyleSheet("font-size:28px; background:transparent;")
        ic_lbl.setFixedSize(40, 40)
        ic_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"font-size:16px; font-weight:700; color:{t('text')}; background:transparent;")
        title_row.addWidget(ic_lbl)
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        bl.addLayout(title_row)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color:{t('border')}; background:{t('border')}; max-height:1px;")
        bl.addWidget(line)

        msg_lbl = QLabel(msg)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(
            f"font-size:13px; color:{t('text_mid')}; line-height:1.6; background:transparent;")
        msg_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        bl.addWidget(msg_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        if is_question:
            cancel_btn = QPushButton("取消")
            cancel_btn.setFixedSize(90, 38)
            cancel_btn.setStyleSheet(f"""
                QPushButton {{ background:{t('btn2_bg')}; border:1.5px solid {t('border')};
                               border-radius:13px; color:{t('btn2_text')}; font-size:13px; }}
                QPushButton:hover {{ background:{t('btn2_hover')}; color:{t('text')}; }}
            """)
            cancel_btn.clicked.connect(self.reject)
            btn_row.addWidget(cancel_btn)

            confirm_btn = QPushButton("确认删除")
            confirm_btn.setFixedSize(100, 38)
            confirm_btn.setStyleSheet(f"""
                QPushButton {{ background:{t('accent')}; border:none;
                               border-radius:13px; color:white; font-size:13px; font-weight:700; }}
                QPushButton:hover {{ background:{t('accent_h')}; }}
            """)
            confirm_btn.clicked.connect(self._on_confirm)
        else:
            confirm_btn = QPushButton("知道了")
            confirm_btn.setFixedSize(90, 38)
            confirm_btn.setStyleSheet(f"""
                QPushButton {{ background:{t('accent')}; border:none;
                               border-radius:13px; color:white; font-size:13px; font-weight:700; }}
                QPushButton:hover {{ background:{t('accent_h')}; }}
            """)
            confirm_btn.clicked.connect(self.accept)

        btn_row.addWidget(confirm_btn)
        bl.addLayout(btn_row)
        cl.addWidget(body)

        self.adjustSize()

    def _on_confirm(self):
        self._confirmed = True
        self.accept()

    @staticmethod
    def info(parent, title, msg):
        d = MsgBox(parent, "info", title, msg)
        d.exec()

    @staticmethod
    def warning(parent, title, msg):
        d = MsgBox(parent, "warning", title, msg)
        d.exec()

    @staticmethod
    def confirm(parent, title, msg, confirm_text="确定", cancel_text="取消"):
        from PyQt6.QtWidgets import QPushButton as QPB
        d = MsgBox(parent, "question", title, msg)
        for btn in d.findChildren(QPB):
            if btn.text() == "确认删除":
                btn.setText(confirm_text)
            elif btn.text() == "取消":
                btn.setText(cancel_text)
        d.exec()
        return d._confirmed

    @staticmethod
    def success(parent, title, msg):
        d = MsgBox(parent, "success", title, msg)
        d.exec()
