"""主题系统 — 集中管理所有颜色和全局 QSS"""
from PyQt6.QtWidgets import QApplication

# ── 深色主题 ──
DARK = {
    "bg":             "#0d0d0f",
    "surface":        "#18181c",
    "card":           "#1e1e24",
    "card2":          "#252529",
    "border":         "#3a3a45",
    "input_bg":       "#111114",
    "input_border":   "#4a4a58",
    "accent":         "#fb7299",
    "accent_h":       "#e05a7a",
    "accent2":        "#ff94b4",
    "text":           "#f0f0f2",
    "text_sub":       "#6b6b80",
    "text_mid":       "#a0a0b8",
    "sel":            "#3d1e28",
    "row_alt":        "#16161a",
    "danger":         "#ef4444",
    "danger_bg":      "#2d1515",
    "danger_border":  "#5a1f1f",
    "success":        "#22c55e",
    "warning":        "#f97316",
    "nav_active":     "#252529",
    "ic_blue":   "#1a2a3d",
    "ic_green":  "#1a3028",
    "ic_orange": "#3d2a14",
    "ic_purple": "#3d1e28",
    "shadow": "rgba(0,0,0,0.6)",
    "badge_alpha": "0.18",
    "btn2_bg":    "#252529",
    "btn2_hover": "#2e2e35",
    "btn2_text":  "#a0a0b8",
    "close_bg":   "#252529",
    "logo_badge": "#fb7299",
    "stat_row_bg":    "#252529",
    "stat_row_hover": "#2e2e38",
    "cat_icon_bg":    "#1e1e24",
}

# ── 浅色主题 ──
LIGHT = {
    "bg":             "#f4f4f8",
    "surface":        "#ffffff",
    "card":           "#ffffff",
    "card2":          "#f8f8fc",
    "border":         "#e0e0ea",
    "input_bg":       "#f0f0f6",
    "input_border":   "#a8a8c8",
    "accent":         "#fb7299",
    "accent_h":       "#e05a7a",
    "accent2":        "#e05a7a",
    "text":           "#18181c",
    "text_sub":       "#8888a0",
    "text_mid":       "#4a4a60",
    "sel":            "#ffe0ea",
    "row_alt":        "#fafafa",
    "danger":         "#dc2626",
    "danger_bg":      "#fff1f1",
    "danger_border":  "#fca5a5",
    "success":        "#16a34a",
    "warning":        "#d97706",
    "nav_active":     "#fff0f4",
    "ic_blue":   "#dbeafe",
    "ic_green":  "#dcfce7",
    "ic_orange": "#fef3c7",
    "ic_purple": "#ffe0ea",
    "shadow": "rgba(180,100,120,0.12)",
    "badge_alpha": "0.13",
    "btn2_bg":    "#f0f0f6",
    "btn2_hover": "#e8e8f0",
    "btn2_text":  "#4a4a60",
    "close_bg":   "#f0f0f6",
    "logo_badge": "#fb7299",
    "stat_row_bg":    "#f8f8fc",
    "stat_row_hover": "#fff0f4",
    "cat_icon_bg":    "#ffffff",
}

T: dict = dict(LIGHT)
IS_DARK: bool = False


def t(k):
    return T[k]


# ── 分类颜色和图标 ──
CAT_COLORS = {
    "螺丝": "#3b82f6", "管材": "#22c55e", "工具": "#f97316",
    "电料": "#eab308", "涂料": "#a855f7", "其他": "#64748b",
}
CAT_ICONS = {"螺丝": "🔩", "管材": "🪠", "工具": "🔧", "电料": "⚡", "涂料": "🪣", "其他": "📦"}

DEFAULT_COLORS = ["#3b82f6", "#22c55e", "#f97316", "#eab308", "#a855f7", "#64748b",
                  "#ec4899", "#14b8a6", "#f43f5e", "#8b5cf6", "#06b6d4", "#84cc16"]
DEFAULT_ICONS = ["🔩", "🪠", "🔧", "⚡", "🪣", "📦", "🛠️", "🪛", "🔑", "📎", "🧲", "⚙️"]

PINNED_COUNT = 5


def _color_for(name):
    return CAT_COLORS.get(name, DEFAULT_COLORS[hash(name) % len(DEFAULT_COLORS)])


def _icon_for(name):
    return CAT_ICONS.get(name, DEFAULT_ICONS[hash(name) % len(DEFAULT_ICONS)])


# ── 全局 QSS ──
def make_qss() -> str:
    return f"""
QWidget {{ font-family:"Microsoft YaHei","PingFang SC",sans-serif; font-size:17px;
           color:{t('text')}; }}
QMainWindow, #root_bg {{ background:{t('bg')}; }}
/* 透明背景只给明确需要的容器 */
#transparent {{ background:transparent; }}

/* 导航栏 */
#navbar {{ background:{t('surface')}; border-bottom:1px solid {t('border')}; }}

/* Nav Tab */
#nav_tab {{ background:transparent; border:none; color:{t('text')};
            font-size:13px; padding:8px 20px; border-radius:14px; }}
#nav_tab:hover {{ background:{t('nav_active')}; color:{t('text')}; }}
#nav_tab[active=true] {{ background:{t('nav_active')}; color:{t('accent')};
                         font-weight:700; }}

/* 主题按钮 */
#theme_btn {{ background:{t('btn2_bg')}; border:1.5px solid {t('border')};
              border-radius:12px; color:{t('text_mid')}; font-size:12px; padding:5px 16px; }}
#theme_btn:hover {{ background:{t('btn2_hover')}; color:{t('text')}; border-color:{t('accent')}; }}

/* 卡片 */
#card {{ background:{t('card')}; border:1px solid {t('border')}; border-radius:16px; }}
#card2 {{ background:{t('card2')}; border:1px solid {t('border')}; border-radius:12px; }}

/* 主按钮 */
#btn_primary {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                   stop:0 {t('accent')},stop:1 {t('accent2')});
               border:none; border-radius:14px; color:white;
               font-size:13px; font-weight:700; padding:0 20px; }}
#btn_primary:hover {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                   stop:0 {t('accent_h')},stop:1 {t('accent')}); }}
#btn_primary:pressed {{ background:{t('accent_h')}; }}

/* 次要按钮 */
#btn_secondary {{ background:{t('btn2_bg')}; border:1.5px solid {t('border')};
                  border-radius:14px; color:{t('btn2_text')};
                  font-size:13px; padding:0 16px; }}
#btn_secondary:hover {{ background:{t('btn2_hover')};                        border-color:{t('accent')}; }}

/* 危险按钮 */
#btn_danger {{ background:{t('danger_bg')}; border:1.5px solid {t('danger_border')};
               border-radius:14px; color:{t('danger')}; font-size:13px; padding:0 16px; }}
#btn_danger:hover {{ background:{t('danger')}; color:white; border-color:{t('danger')}; }}

/* 搜索框 */
#search_box {{ background:{t('input_bg')}; border:1.5px solid {t('input_border')};
               border-radius:10px; color:{t('text')}; padding:0 14px; font-size:13px; }}
#search_box:focus {{ border-color:{t('accent')}; background:{t('card')}; }}
#search_box::placeholder {{ color:{t('text_sub')}; }}

/* 分类 Pill */
#pill {{ background:{t('btn2_bg')}; border:1.5px solid {t('border')};
         border-radius:18px; color:{t('text_mid')}; font-size:12px; padding:4px 14px; }}
#pill:hover {{ border-color:{t('accent')}; color:{t('accent')}; background:{t('nav_active')}; }}
#pill[active=true] {{ background:{t('accent')}; border-color:{t('accent')};
                      color:white; font-weight:700; }}

/* 表格 */
QTableWidget {{ background:{t('card')}; border:none;
                gridline-color:{t('border')}; outline:none;
                font-size:13px; color:{t('text')}; }}
QTableWidget::item {{ padding:0 12px; border-bottom:1px solid {t('border')}; }}
QTableWidget::item:selected {{ background:{t('sel')}; color:{t('text')}; border-bottom:1px solid {t('accent')}; }}
QTableWidget::item:selected:!active {{ background:{t('sel')}; color:{t('text')}; border-bottom:1px solid {t('accent')}; }}
QTableWidget::item:alternate:selected {{ background:{t('sel')}; color:{t('text')}; border-bottom:1px solid {t('accent')}; }}
QTableWidget::item:alternate:selected:!active {{ background:{t('sel')}; color:{t('text')}; border-bottom:1px solid {t('accent')}; }}
QTableWidget::item:alternate {{ background:{t('row_alt')}; }}
QHeaderView::section {{ background:{t('card2')}; color:{t('text_mid')};
                         font-size:12px; font-weight:600; padding:0 12px;
                         border:none; border-bottom:1px solid {t('border')};
                         border-right:1px solid {t('border')}; }}
QScrollBar:vertical {{ background:{t('card2')}; width:6px; border-radius:3px; }}
QScrollBar::handle:vertical {{ background:{t('border')}; border-radius:3px; min-height:30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar:horizontal {{ background:{t('card2')}; height:6px; border-radius:3px; }}
QScrollBar::handle:horizontal {{ background:{t('border')}; border-radius:3px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}

/* 弹窗表单 */
#form_label {{ color:{t('text_mid')}; font-size:12px; font-weight:600; }}
#form_input {{ background:{t('input_bg')}; border:1.5px solid {t('input_border')};
               border-radius:10px; color:{t('text')}; padding:0 14px; font-size:13px; }}
#form_input:focus {{ border-color:{t('accent')}; background:{t('card')}; }}
QComboBox#form_combo {{ background:{t('input_bg')}; border:1.5px solid {t('border')};
                         border-radius:17px; color:{t('text')}; padding:0 14px; font-size:13px; }}
QComboBox#form_combo:focus {{ border-color:{t('accent')}; }}
QComboBox#form_combo::drop-down {{ border:none; width:28px; }}
QComboBox QAbstractItemView {{ background:{t('card')}; border:1px solid {t('border')};
                                color:{t('text')}; selection-background-color:{t('sel')};
                                selection-color:{t('accent')}; outline:none; }}
QComboBox QAbstractItemView::item {{ padding:6px 14px; }}
QComboBox QAbstractItemView::item:hover {{ background:{t('sel')}; color:{t('accent')}; }}
QDoubleSpinBox#form_spin, QSpinBox#form_spin {{
    background:{t('input_bg')}; border:1.5px solid {t('border')};
    border-radius:10px; color:{t('text')}; padding:0 14px; font-size:13px; }}
QDoubleSpinBox#form_spin:focus, QSpinBox#form_spin:focus {{ border-color:{t('accent')}; }}
QDoubleSpinBox#form_spin::up-button, QSpinBox#form_spin::up-button,
QDoubleSpinBox#form_spin::down-button, QSpinBox#form_spin::down-button {{
    background:{t('btn2_bg')}; border:none; width:20px; }}

/* 状态栏 */
#statusbar {{ background:{t('surface')}; border-top:1px solid {t('border')}; }}
"""


def apply_global_qss(app: QApplication):
    """应用全局样式表"""
    app.setStyleSheet(make_qss())
