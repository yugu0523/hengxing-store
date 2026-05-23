"""客户管理页"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QAbstractItemView, QDialog, QListWidget, QListWidgetItem,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPalette

from core.config import get_app_dir
from core.db import (db_customers, db_customer_add, db_customer_update, db_customer_delete)
from ui.theme import t, IS_DARK
from ui.widgets import add_shadow, icon_badge, Toast, MsgBox

class CustomerDialog(QDialog):
    def __init__(self, parent, data=None):
        super().__init__(parent)
        self.data = data
        self.setWindowTitle("编辑客户" if data else "新增客户")
        self.setFixedSize(420, 360)
        self._build()
        if data:
            self.e_name.setText(data[1] or "")
            self.e_address.setText(data[2] or "")
            self.e_phone.setText(data[3] or "")
        self._center()

    def _center(self):
        p = self.parent()
        if p:
            self.move(p.x() + (p.width() - self.width()) // 2,
                      p.y() + (p.height() - self.height()) // 2)

    def _inp(self, ph=""):
        w = QLineEdit(); w.setPlaceholderText(ph); w.setFixedHeight(34)
        return w

    def _build(self):
        self.setStyleSheet(f"""
            QDialog {{ background:{t('card')}; border-radius:12px; }}
            QLabel {{ color:{t('text')}; font-size:13px; }}
            QLineEdit {{ background:{t('input_bg')}; border:1.5px solid {t('border')};
                border-radius:8px; color:{t('text')}; padding:0 12px; font-size:13px; }}
            QLineEdit:focus {{ border-color:{t('accent')}; }}
        """)
        lay = QVBoxLayout(self); lay.setContentsMargins(24, 20, 24, 20); lay.setSpacing(12)

        title = QLabel("新增客户" if not self.data else "编辑客户")
        title.setStyleSheet(f"font-size:16px;font-weight:700;color:{t('text')};")
        lay.addWidget(title)

        lay.addWidget(QLabel("客户名称  *"))
        self.e_name = self._inp("请输入客户名称"); lay.addWidget(self.e_name)

        lay.addWidget(QLabel("客户地址"))
        self.e_address = self._inp("请输入客户地址"); lay.addWidget(self.e_address)

        lay.addWidget(QLabel("客户电话"))
        self.e_phone = self._inp("请输入客户电话"); lay.addWidget(self.e_phone)

        lay.addStretch()
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("取消"); cancel.setObjectName("btn_danger"); cancel.setFixedHeight(36)
        cancel.clicked.connect(self.reject); btn_row.addWidget(cancel)
        btn_row.addSpacing(10)
        save = QPushButton("  保  存  "); save.setObjectName("btn_primary"); save.setFixedHeight(36)
        save.clicked.connect(self._save); btn_row.addWidget(save)
        lay.addLayout(btn_row)

    def _save(self):
        name = self.e_name.text().strip()
        if not name:
            MsgBox.warning(self, "保存失败", "请填写客户名称。")
            return
        self.accept()

    def get_data(self):
        return (self.e_name.text().strip(),
                self.e_address.text().strip(),
                self.e_phone.text().strip())


# ══════════════════════════════════════════════════════════════════════
#  客户管理页
# ══════════════════════════════════════════════════════════════════════
class CustomerPage(QWidget):
    status_sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 8); lay.setSpacing(16)

        # ── 页头 ──
        hc = QFrame(); hc.setObjectName("card")
        add_shadow(hc, 20, 30 if IS_DARK else 10)
        hl = QHBoxLayout(hc); hl.setContentsMargins(20, 16, 20, 16)
        left = QHBoxLayout(); left.setSpacing(16)
        left.addWidget(icon_badge("🙋", t('ic_blue'), 48, 14))
        ic = QVBoxLayout(); ic.setSpacing(3)
        h1 = QLabel("客户管理")
        h1.setStyleSheet("font-size:17px;font-weight:700;")
        ic.addWidget(h1)
        left.addLayout(ic)
        hl.addLayout(left); hl.addStretch()
        self.btn_add = QPushButton("＋  新增客户"); self.btn_add.setObjectName("btn_primary")
        self.btn_add.setFixedHeight(36)
        self.btn_del = QPushButton("删除"); self.btn_del.setObjectName("btn_danger"); self.btn_del.setFixedHeight(36)
        self.btn_edit = QPushButton("编辑"); self.btn_edit.setObjectName("btn_secondary"); self.btn_edit.setFixedHeight(36)
        hl.addWidget(self.btn_edit); hl.addSpacing(8)
        hl.addWidget(self.btn_del); hl.addSpacing(8)
        hl.addWidget(self.btn_add)
        lay.addWidget(hc)

        # ── 表格 ──
        tc = QFrame(); tc.setObjectName("card")
        add_shadow(tc, 20, 25 if IS_DARK else 8)
        tcl = QVBoxLayout(tc); tcl.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        pal = self.table.palette()
        pal.setColor(QPalette.ColorRole.Highlight, QColor(t('sel')))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor(t('text')))
        self.table.setPalette(pal)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["客户名称", "地址", "电话"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        tcl.addWidget(self.table)

        # 空状态
        self.empty_lbl = QLabel("暂无客户，点击「＋ 新增客户」添加", self.table)
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_lbl.setStyleSheet(f"color:{t('text_sub')};font-size:14px;")
        self.empty_lbl.hide()
        lay.addWidget(tc)

        self.btn_add.clicked.connect(self._on_add)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_del.clicked.connect(self._on_del)
        self.table.cellDoubleClicked.connect(self._on_edit)

    def _toggle_empty(self):
        if self.table.rowCount() == 0:
            self.empty_lbl.setGeometry(self.table.rect())
            self.empty_lbl.show()
        else:
            self.empty_lbl.hide()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "empty_lbl") and self.empty_lbl.isVisible():
            self.empty_lbl.setGeometry(self.table.rect())

    def refresh(self):
        rows = db_customers()
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate([row[1] or "", row[2] or "", row[3] or ""]):
                it = QTableWidgetItem(val)
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(r, c, it)
        self._toggle_empty()

    def _on_add(self):
        dlg = CustomerDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            n, a, p = dlg.get_data()
            db_customer_add(n, a, p)
            self.refresh()
            self.status_sig.emit(f"✓  已添加客户：{n}")

    def _on_edit(self):
        r = self.table.currentRow()
        if r < 0:
            Toast.show_msg(self.window(), "请先选择要编辑的客户")
            return
        cid = db_customers()[r][0]
        dlg = CustomerDialog(self, (cid, self.table.item(r, 0).text(),
                                    self.table.item(r, 1).text(),
                                    self.table.item(r, 2).text()))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            n, a, p = dlg.get_data()
            db_customer_update(cid, n, a, p)
            self.refresh()
            self.status_sig.emit(f"✓  已更新客户：{n}")

    def _on_del(self):
        r = self.table.currentRow()
        if r < 0:
            Toast.show_msg(self.window(), "请先选择要删除的客户")
            return
        name = self.table.item(r, 0).text()
        reply = QMessageBox.question(self.window(), "确认删除",
                                     f"确定要删除客户「{name}」吗？此操作不可撤销。",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            db_customer_delete(db_customers()[r][0])
            self.refresh()
            self.status_sig.emit(f"✓  已删除客户：{name}")


# ══════════════════════════════════════════════════════════════════════
#  客户选择弹窗
# ══════════════════════════════════════════════════════════════════════
class CustomerSelectDialog(QDialog):
    def __init__(self, customers, parent=None):
        super().__init__(parent)
        self.selected = None
        self._cleared = False
        self.setWindowTitle("选择客户")
        self.setFixedSize(500, 400)
        self._build(customers)
        self._center()

    def _center(self):
        p = self.parent()
        if p:
            self.move(p.x() + (p.width() - self.width()) // 2,
                      p.y() + (p.height() - self.height()) // 2)

    def _build(self, customers):
        self.setStyleSheet(f"""
            QDialog {{ background:{t('card')}; border-radius:12px; }}
            QLabel {{ color:{t('text')}; font-size:13px; }}
            QTableWidget {{ background:{t('card')}; border:1.5px solid {t('border')};
                border-radius:8px; gridline-color:{t('border')}; color:{t('text')}; }}
            QTableWidget::item {{ padding:6px 10px; }}
            QTableWidget::item:selected {{ background:{t('sel')}; color:{t('text')}; }}
            QHeaderView::section {{ background:{t('card2')}; color:{t('text_mid')};
                border:none; border-bottom:2px solid {t('border')}; padding:8px 10px;
                font-size:12px; font-weight:600; }}
        """)
        lay = QVBoxLayout(self); lay.setContentsMargins(20, 16, 20, 16); lay.setSpacing(14)

        title = QLabel("选择客户")
        title.setStyleSheet(f"font-size:16px;font-weight:700;color:{t('text')};")
        lay.addWidget(title)

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["客户名称", "地址", "电话"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setRowCount(len(customers))
        for r, row in enumerate(customers):
            table.setItem(r, 0, QTableWidgetItem(row[1] or ""))
            table.setItem(r, 1, QTableWidgetItem(row[2] or ""))
            table.setItem(r, 2, QTableWidgetItem(row[3] or ""))
        if customers:
            table.selectRow(0)
        lay.addWidget(table)

        btn_row = QHBoxLayout()
        clear_btn = QPushButton("清除选择")
        clear_btn.setObjectName("btn_danger"); clear_btn.setFixedHeight(36)
        clear_btn.clicked.connect(lambda: (setattr(self, '_cleared', True), self.reject()))
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        cancel_btn = QPushButton("取消"); cancel_btn.setObjectName("btn_secondary"); cancel_btn.setFixedHeight(36)
        cancel_btn.clicked.connect(self.reject); btn_row.addWidget(cancel_btn)
        btn_row.addSpacing(8)
        ok_btn = QPushButton("  确  定  "); ok_btn.setObjectName("btn_primary"); ok_btn.setFixedHeight(36)
        ok_btn.clicked.connect(lambda: (
            setattr(self, 'selected', customers[table.currentRow()]) if table.currentRow() >= 0 and customers else None,
            self.accept()))
        btn_row.addWidget(ok_btn)
        lay.addLayout(btn_row)

