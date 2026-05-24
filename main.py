"""恒星五金记账系统 — 入口文件"""
import sys, os, traceback, glob

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QLabel, QPushButton, QFrame,
    QMessageBox, QGraphicsDropShadowEffect, QSizePolicy,
)
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QIcon, QColor

from core.config import get_app_dir, APP_VERSION, UPDATE_CHECK_URL
from core.db import init_db, _ensure_checkmark, _ensure_arrow_icons
from core.update import _version_tuple, UpdateChecker, UpdateDialog
import ui.theme as theme
from ui.theme import (t, IS_DARK, T, DARK, LIGHT, make_qss, apply_global_qss,
                       CAT_COLORS, CAT_ICONS, _color_for, _icon_for, PINNED_COUNT)
from ui.widgets import icon_badge, Toast
from ui.product_page import ProductPage
from ui.customer_page import CustomerPage
from ui.print_page import PrintPage
from ui.stats_page import StatsPage
from ui.dialogs import DevPanel

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("恒星五金记账系统")
        self.resize(1320, 840); self.setMinimumSize(1000, 660)
        self._cur_tab = "商品管理"
        self._init_ui()

    def _init_ui(self):
        root = QWidget(); root.setObjectName("root_bg")
        self.setCentralWidget(root)
        ml = QVBoxLayout(root); ml.setContentsMargins(0,0,0,0); ml.setSpacing(0)

        # ── 导航栏 ──
        self.navbar = QFrame(); self.navbar.setObjectName("navbar")
        self.navbar.setFixedHeight(66)
        nl = QHBoxLayout(self.navbar); nl.setContentsMargins(24,0,24,0); nl.setSpacing(0)

        lr = QHBoxLayout(); lr.setSpacing(14)
        self._logo_badge = icon_badge("⭐", "transparent", 44, 12)
        lr.addWidget(self._logo_badge)
        lc = QVBoxLayout(); lc.setSpacing(2)
        self._logo_t1 = QLabel("恒星五金记账系统")
        self._logo_t1.setStyleSheet(f"font-size:16px;font-weight:700;color:{t('text')};")
        lc.addWidget(self._logo_t1)
        lr.addLayout(lc)
        nl.addLayout(lr); nl.addSpacing(40)

        self.tab_btns = {}
        for tab in ["商品管理","账单打印","客户","数据统计"]:
            b = QPushButton(tab); b.setObjectName("nav_tab"); b.setFixedHeight(40)
            b.clicked.connect(lambda _,tab=tab: self._switch_tab(tab))
            nl.addWidget(b); self.tab_btns[tab] = b
        nl.addStretch()

        self.theme_btn = QPushButton("🌙  深色模式")
        self.theme_btn.setObjectName("theme_btn"); self.theme_btn.setFixedHeight(34)
        self.theme_btn.clicked.connect(self._toggle_theme)
        nl.addWidget(self.theme_btn); nl.addSpacing(16)
        self._ver_lbl = QLabel(f"v{APP_VERSION}")
        self._ver_lbl.setStyleSheet(f"color:{t('text_sub')};font-size:11px;cursor:pointer;")
        self._ver_lbl.setToolTip("点击检查更新 | 双击打开开发者工具")
        self._ver_click_time = 0
        def _on_ver_click(_):
            import time as _t
            now = _t.time()
            if now - self._ver_click_time < 0.4:
                # 双击 → 打开开发者面板
                self._ver_click_time = 0
                dlg = DevPanel(self)
                dlg.exec()
            else:
                self._ver_click_time = now
                self._check_update()
        self._ver_lbl.mousePressEvent = _on_ver_click
        nl.addWidget(self._ver_lbl)
        ml.addWidget(self.navbar)

        # ── 页面栈 ──
        self.stack = QStackedWidget()
        self.page_prod  = ProductPage()
        self.page_print = PrintPage()
        self.page_cust  = CustomerPage()
        self.page_stats = StatsPage()
        self.stack.addWidget(self.page_prod)
        self.stack.addWidget(self.page_print)
        self.stack.addWidget(self.page_cust)
        self.stack.addWidget(self.page_stats)
        ml.addWidget(self.stack)

        # ── 状态栏 ──
        self.statusbar_frame = QFrame(); self.statusbar_frame.setObjectName("statusbar")
        self.statusbar_frame.setFixedHeight(30)
        sl = QHBoxLayout(self.statusbar_frame)
        sl.setContentsMargins(20,0,20,0)
        self.status_lbl = QLabel("就绪")
        self.status_lbl.setStyleSheet(f"color:{t('text_sub')};font-size:11px;")
        self._ver2 = QLabel(f"恒星五金记账系统  v{APP_VERSION}")
        self._ver2.setStyleSheet(f"color:{t('text_sub')};font-size:10px;")
        sl.addWidget(self.status_lbl); sl.addStretch(); sl.addWidget(self._ver2)
        ml.addWidget(self.statusbar_frame)

        self.page_prod.status_sig.connect(self.status_lbl.setText)
        self.page_prod.data_changed.connect(self.page_stats.refresh)
        self.page_prod.print_changed.connect(self.page_print.refresh)
        self.page_print.status_sig.connect(self.status_lbl.setText)
        self.page_cust.status_sig.connect(self.status_lbl.setText)
        self._switch_tab(self._cur_tab)
        self.apply_theme()
        self.page_prod.refresh()
        # 启动 3 秒后检查更新（不阻塞启动）
        QTimer.singleShot(3000, self._check_update)

    def _switch_tab(self, tab):
        self._cur_tab = tab
        for name, btn in self.tab_btns.items():
            btn.setProperty("active", name==tab)
            btn.style().unpolish(btn); btn.style().polish(btn)
        if tab == "商品管理":
            self.stack.setCurrentWidget(self.page_prod)
        elif tab == "数据统计":
            self.stack.setCurrentWidget(self.page_stats)
            self.page_stats.refresh()
        elif tab == "账单打印":
            self.stack.setCurrentWidget(self.page_print)
            self.page_print.refresh()
        elif tab == "客户":
            self.stack.setCurrentWidget(self.page_cust)
            self.page_cust.refresh()

    def _check_update(self):
        """检查是否有新版本"""
        if not UPDATE_CHECK_URL:
            return
        # 防止重复弹窗
        if hasattr(self, "_update_dlg") and self._update_dlg and self._update_dlg.isVisible():
            self._update_dlg.raise_()
            self._update_dlg.activateWindow()
            return
        self._checker = UpdateChecker(mode="check", url=UPDATE_CHECK_URL)
        self._checker.checked.connect(self._on_update_checked)
        self._checker.failed.connect(lambda _: None)  # 静默失败
        self._checker.start()

    def _on_update_checked(self, info):
        remote_ver = info.get("version", "0.0.0")
        if _version_tuple(remote_ver) > _version_tuple(APP_VERSION):
            self._update_info = info
            is_test = info.get("_test_mode", False)
            self._update_dlg = UpdateDialog(info, self, test_mode=is_test)
            self._update_dlg.show()  # 非模态：用户可最小化窗口继续使用软件

    def _start_download(self):
        """开始后台下载，底部显示进度条"""
        from PyQt6.QtWidgets import QProgressBar
        ver = self._update_info.get("version", "") if hasattr(self, "_update_info") else ""
        # 创建底部进度条
        if not hasattr(self, "_dl_bar"):
            self._dl_bar = QProgressBar()
            self._dl_bar.setFixedHeight(4)
            self._dl_bar.setTextVisible(False)
            self._dl_bar.setStyleSheet(
                f"QProgressBar{{background:{t('border')};border:0;}}"
                f"QProgressBar::chunk{{background:{t('accent')};}}")
            self.centralWidget().layout().insertWidget(3, self._dl_bar)
        self._dl_bar.setValue(0)
        self._dl_bar.show()
        self.status_lbl.setText(f"正在下载更新 v{ver}...")
        # 启动下载
        self._downloader = UpdateChecker(mode="download", url=self._update_info.get("download_url", ""))
        self._downloader.progress.connect(self._on_download_progress)
        self._downloader.finished_ok.connect(self._on_download_done)
        self._downloader.failed.connect(self._on_download_fail)
        self._downloader.start()

    def _on_download_progress(self, pct):
        if hasattr(self, "_dl_bar"):
            self._dl_bar.setValue(pct)
        if pct > 0:
            self.status_lbl.setText(f"正在下载更新：{pct}%")

    def _on_download_done(self, tmp_path):
        self._update_tmp = tmp_path
        if hasattr(self, "_dl_bar"):
            self._dl_bar.hide()
        ver = self._update_info.get("version", "") if hasattr(self, "_update_info") else ""
        self.status_lbl.setText(f"v{ver} 更新已就绪，重启后生效")
        # 状态栏添加重启按钮
        if not hasattr(self, "_restart_btn"):
            self._restart_btn = QPushButton("立即重启更新")
            self._restart_btn.setStyleSheet(
                f"QPushButton{{background:{t('accent')};color:white;border:0;"
                f"border-radius:6px;padding:2px 12px;font-size:11px;}}"
                f"QPushButton:hover{{background:{t('accent_h')};}}")
            self._restart_btn.clicked.connect(self._apply_update)
            self.statusbar_frame.layout().insertWidget(2, self._restart_btn)
        self._restart_btn.show()

    def _on_download_fail(self, err):
        self.status_lbl.setText(f"更新下载失败: {err}")

    def _apply_update(self):
        if hasattr(self, "_update_tmp") and os.path.exists(self._update_tmp):
            UpdateDialog._apply_update_static(self._update_tmp)

    def _toggle_theme(self):
        theme.IS_DARK = not theme.IS_DARK
        theme.T.update(theme.DARK if theme.IS_DARK else theme.LIGHT)
        self.theme_btn.setText("☀️  浅色模式" if theme.IS_DARK else "🌙  深色模式")
        self.apply_theme()

    def apply_theme(self):
        qss = make_qss()
        self.setStyleSheet(qss)
        # 更新导航栏内联样式
        self._logo_t1.setStyleSheet(f"font-size:16px;font-weight:700;color:{t('text')};")
        self._ver_lbl.setStyleSheet(f"color:{t('text_sub')};font-size:11px;")
        self._ver2.setStyleSheet(f"color:{t('text_sub')};font-size:10px;")
        self.status_lbl.setStyleSheet(f"color:{t('text_sub')};font-size:11px;")
        self.page_prod.refresh()
        if self._cur_tab == "数据统计":
            self.page_stats.refresh()

# ══════════════════════════════════════════════════════════════════════
#  入口
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # 把未捕获的异常写入日志文件，方便排查崩溃原因
    _log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error.log")
    def _excepthook(exc_type, exc_val, exc_tb):
        msg = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
        with open(_log, "a", encoding="utf-8") as f:
            import datetime
            f.write(f"\n{'='*60}\n{datetime.datetime.now()}\n{msg}\n")
        try:
            QMessageBox.critical(None, "程序错误", msg[:800])
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc_val, exc_tb)
    sys.excepthook = _excepthook

    # ── 清理历史遗留的 .old 文件（旧版更新流程产生的备份）──
    app_dir = os.path.dirname(os.path.abspath(
        sys.executable if getattr(sys, 'frozen', False) else __file__))
    for old_file in glob.glob(os.path.join(app_dir, "*.old")):
        try:
            os.remove(old_file)
        except OSError:
            pass

    init_db()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # ── 设置应用图标（任务栏 + 窗口标题栏）──
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后：图标在临时解压目录
        icon_path = os.path.join(sys._MEIPASS, "app_icon.ico")
    else:
        # 开发模式：图标在源码目录
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico")
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)  # 任务栏图标

    win = MainWindow()
    win.show()
    sys.exit(app.exec())
