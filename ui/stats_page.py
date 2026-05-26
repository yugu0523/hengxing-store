"""数据统计页"""
import sys, os, traceback

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QSizePolicy, QComboBox, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QPainterPath

from core.config import get_app_dir
from core.db import (db_weekly_additions, db_monthly_additions, db_yearly_additions,
                     db_stats, db_cats)
from ui.theme import t, IS_DARK, T, CAT_COLORS, DEFAULT_COLORS
from ui.widgets import add_shadow, icon_badge, StatCard, MsgBox

class DonutChart(QWidget):
    """纯 QPainter 甜甜圈饼图，无需 matplotlib"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._slices = []   # [(value, color, label)]
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_slices(self, slices):
        self._slices = slices
        self.update()

    def paintEvent(self, event):
        try:
            self._paint()
        except Exception:
            pass   # 绘图出错时静默跳过，不崩溃

    def _paint(self):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        total = sum(v for v, _, _ in self._slices) if self._slices else 0
        if not self._slices or total == 0:
            painter.setPen(QColor(t('text_sub')))
            painter.drawText(QRect(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "暂无数据")
            return

        chart_area_w = int(w * 0.55)
        cx, cy = chart_area_w // 2, h // 2
        outer_r = max(min(cx, cy) - 10, 20)
        inner_r = int(outer_r * 0.54)

        rect = QRect(cx - outer_r, cy - outer_r, outer_r * 2, outer_r * 2)
        angle = 90.0
        for value, color, label in self._slices:
            span = value / total * 360.0
            painter.setBrush(QBrush(QColor(color)))
            painter.setPen(QPen(QColor(t('card')), 2))
            painter.drawPie(rect, int(angle * 16), int(-span * 16))
            angle -= span

        painter.setBrush(QBrush(QColor(t('card'))))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRect(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2))

        painter.setFont(QFont("Microsoft YaHei", 9))
        lx = chart_area_w + 12
        ly = max(10, cy - len(self._slices) * 22 // 2)
        for value, color, label in self._slices:
            pct = value / total * 100
            painter.setBrush(QBrush(QColor(color)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRect(lx, ly + 2, 12, 12), 3, 3)
            painter.setPen(QColor(t('text')))
            rw = max(w - lx - 18, 10)
            painter.drawText(QRect(lx + 18, ly, rw, 18),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             f"{label}  {pct:.0f}%")
            ly += 24


class LineChart(QWidget):
    """纯 QPainter 折线图，无需 matplotlib"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []   # [(label, value)]
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, data):
        self._data = data
        self.update()

    def paintEvent(self, event):
        try:
            self._paint()
        except Exception:
            painter = QPainter(self)
            try:
                painter.setPen(QColor("#ef4444"))
                painter.setFont(QFont("Microsoft YaHei", 10))
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                                 f"绘图失败\n{traceback.format_exc()[:200]}")
            finally:
                painter.end()

    def _paint(self):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        if not self._data:
            painter.setPen(QColor(t('text_sub')))
            painter.setFont(QFont("Microsoft YaHei", 12))
            painter.drawText(QRect(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "暂无数据")
            return

        pad_l, pad_r, pad_t, pad_b = 38, 16, 20, 28
        chart_w = max(w - pad_l - pad_r, 1)
        chart_h = max(h - pad_t - pad_b, 1)
        labels = [d[0] for d in self._data]
        values = [d[1] for d in self._data]
        n = len(values)
        max_v = max(max(values), 1)

        accent = QColor(t('accent'))
        mid_c  = QColor(t('text_mid'))
        bdr_c  = QColor(t('border'))
        txt_c  = QColor(t('text'))
        painter.setFont(QFont("Microsoft YaHei", 8))

        # Y 轴刻度
        steps = 4
        for i in range(steps + 1):
            y = pad_t + int(chart_h * (steps - i) / steps)
            painter.setPen(mid_c)
            painter.drawText(QRect(0, y - 8, pad_l - 5, 16),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             str(int(max_v * i / steps)))
            painter.setPen(QPen(bdr_c, 1, Qt.PenStyle.DashLine))
            painter.drawLine(pad_l, y, w - pad_r, y)

        # X 轴标签
        painter.setPen(mid_c)
        if n == 1:
            x = pad_l + chart_w // 2
            painter.drawText(QRect(x - 20, h - pad_b + 4, 40, 18),
                             Qt.AlignmentFlag.AlignCenter, labels[0])
        else:
            for i, lbl in enumerate(labels):
                x = pad_l + int(i * chart_w / (n - 1))
                painter.drawText(QRect(x - 20, h - pad_b + 4, 40, 18),
                                 Qt.AlignmentFlag.AlignCenter, lbl)

        # 数据点坐标
        pts = []
        for i, v in enumerate(values):
            if n == 1:
                x = pad_l + chart_w // 2
            else:
                x = pad_l + int(i * chart_w / (n - 1))
            y = pad_t + chart_h - int(v / max_v * chart_h)
            pts.append(QPointF(x, y))

        # 填充区域
        path = QPainterPath()
        path.moveTo(pts[0].x(), pad_t + chart_h)
        for p in pts:
            path.lineTo(p)
        path.lineTo(pts[-1].x(), pad_t + chart_h)
        path.closeSubpath()
        fill = QColor(accent); fill.setAlpha(28)
        painter.fillPath(path, fill)

        # 折线
        if n > 1:
            painter.setPen(QPen(accent, 2.5))
            for i in range(len(pts) - 1):
                painter.drawLine(pts[i], pts[i + 1])

        # 数据点 + 数值标签
        for p, v in zip(pts, values):
            painter.setBrush(QBrush(accent))
            painter.setPen(QPen(QColor("white"), 1.8))
            painter.drawEllipse(p, 5, 5)
            if v > 0:
                painter.setPen(txt_c)
                painter.drawText(QRect(int(p.x()) - 15, int(p.y()) - 20, 30, 16),
                                 Qt.AlignmentFlag.AlignCenter, str(v))


class StatsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 8); lay.setSpacing(16)

        h1 = QLabel("数据统计")
        h1.setStyleSheet(f"font-size:20px;font-weight:800;color:{t('text')};")
        lay.addWidget(h1)

        # ── 汇总卡片 ──
        cr = QHBoxLayout(); cr.setSpacing(16)
        self.sc_total = StatCard("📦", "ic_blue",   "商品种数",   "0",     "#3b82f6")
        self.sc_value = StatCard("💰", "ic_green",  "零售总价值", "¥0.00", "#22c55e")
        self.sc_cats  = StatCard("🗂", "ic_purple", "分类数量",   "0",     "#a855f7")
        cr.addWidget(self.sc_total)
        cr.addWidget(self.sc_value)
        cr.addWidget(self.sc_cats)
        lay.addLayout(cr)

        # ── 图表行 ──
        charts = QHBoxLayout(); charts.setSpacing(16)

        pie_card = QFrame(); pie_card.setObjectName("card")
        add_shadow(pie_card, 20, 25 if IS_DARK else 8)
        pcl = QVBoxLayout(pie_card); pcl.setContentsMargins(16, 12, 16, 12); pcl.setSpacing(6)
        pcl.addWidget(self._chart_title("📊  各分类商品占比"))
        self._pie = DonutChart()
        pcl.addWidget(self._pie)
        charts.addWidget(pie_card, 1)

        line_card = QFrame(); line_card.setObjectName("card")
        add_shadow(line_card, 20, 25 if IS_DARK else 8)
        lcl = QVBoxLayout(line_card); lcl.setContentsMargins(16, 12, 16, 12); lcl.setSpacing(6)

        # 标题行 + 日/月/年切换按钮
        line_hdr = QHBoxLayout(); line_hdr.setSpacing(6)
        self._line_title = self._chart_title("📈  近 7 天新增商品数")
        line_hdr.addWidget(self._line_title); line_hdr.addStretch()
        self._line_mode = "日"
        self._line_mode_btns = {}
        for mode in ("日", "月", "年"):
            b = QPushButton(mode)
            b.setFixedSize(36, 26)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setCheckable(True)
            b.setChecked(mode == "日")
            b.setStyleSheet(self._mode_btn_style(mode == "日"))
            b.clicked.connect(lambda _, m=mode: self._set_line_mode(m))
            self._line_mode_btns[mode] = b
            line_hdr.addWidget(b)
        lcl.addLayout(line_hdr)

        self._line = LineChart()
        lcl.addWidget(self._line)
        charts.addWidget(line_card, 1)

        lay.addLayout(charts)

    def _chart_title(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size:14px;font-weight:700;color:{t('text')};background:transparent;")
        return lbl

    def _mode_btn_style(self, active: bool) -> str:
        if active:
            return (f"QPushButton{{background:{t('accent')};border:none;border-radius:8px;"
                    f"color:white;font-size:12px;font-weight:700;}}"
                    f"QPushButton:hover{{background:{t('accent_h')};}}")
        else:
            return (f"QPushButton{{background:{t('btn2_bg')};border:1px solid {t('border')};"
                    f"border-radius:8px;color:{t('text_mid')};font-size:12px;}}"
                    f"QPushButton:hover{{background:{t('nav_active')};color:{t('accent')};"
                    f"border-color:{t('accent')};}}")

    def _set_line_mode(self, mode: str):
        self._line_mode = mode
        for m, b in self._line_mode_btns.items():
            b.setChecked(m == mode)
            b.setStyleSheet(self._mode_btn_style(m == mode))
        titles = {"日": "📈  近 7 天新增商品数", "月": "📈  近 12 个月新增商品数", "年": "📈  各年份新增商品数"}
        self._line_title.setText(titles[mode])
        self._refresh_line()

    def _refresh_line(self):
        mode = self._line_mode
        if mode == "日":
            data = db_weekly_additions()
            pairs = [(d[5:], v) for d, v in data]          # MM-DD
        elif mode == "月":
            data = db_monthly_additions()
            pairs = [(d[5:], v) for d, v in data]          # MM
        else:
            data = db_yearly_additions()
            pairs = [(d[2:], v) for d, v in data]          # YY
        self._line.set_data(pairs)

    def refresh(self):
        try:
            tot, val, cats = db_stats()
            self.sc_total.set_value(str(tot))
            self.sc_value.set_value(f"¥{val:,.2f}")
            self.sc_cats.set_value(str(len(cats)))

            slices = [(c[1], CAT_COLORS.get(c[0], DEFAULT_COLORS[i % len(DEFAULT_COLORS)]), c[0])
                      for i, c in enumerate(cats)]
            self._pie.set_slices(slices)

            self._refresh_line()
        except Exception:
            err = traceback.format_exc()
            QMessageBox.critical(self, "统计页错误", err[:600])

