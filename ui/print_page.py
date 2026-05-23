"""账单打印页"""
import sys, os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QAbstractItemView, QCheckBox, QSpinBox, QDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QTimer, QUrl
from PyQt6.QtGui import QColor, QPainter, QPalette, QPageSize
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
from PyQt6.QtPdf import QPdfDocument

from core.config import get_app_dir
from core.db import (PRINT_CART, db_customers, _ensure_checkmark, _ensure_arrow_icons)
from ui.theme import t, IS_DARK
from ui.widgets import add_shadow, icon_badge, Toast, MsgBox
from ui.customer_page import CustomerSelectDialog

class PrintPage(QWidget):
    status_sig = pyqtSignal(str)

    PRINT_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ font-family: "Microsoft YaHei","PingFang SC",sans-serif; padding: 0; margin: 0 auto; width: 190mm; color: #000; }}
  .store-header {{ text-align: center; border-bottom: 3px double #000; padding-bottom: 10px; margin-bottom: 12px; }}
  .store-header h1 {{ font-size: 22px; font-weight: 900; margin: 0 0 6px; letter-spacing: 4px; }}
  .store-header .info {{ font-size: 12px; color: #333; line-height: 1.8; }}
  .info-row {{ display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 8px; }}
  .info-row .label {{ color: #333; }}
  .info-row .value {{ border-bottom: 1px solid #000; min-width: 120px; padding: 0 8px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
  th, td {{ border: 1px solid #000; padding: 5px 8px; text-align: center; font-size: 12px; }}
  th {{ background: #eee; font-weight: 700; }}
  .num {{ text-align: right; }}
  .total-row {{ font-weight: 700; font-size: 14px; }}
  .total-row td {{ border-top: 2px solid #000; }}
  .sign-row {{ display: flex; justify-content: space-between; font-size: 12px; margin-top: 16px; }}
  .sign-item {{ min-width: 160px; }}
  .sign-item span {{ border-bottom: 1px solid #000; padding: 0 24px; }}
  .bottom-note {{ font-size: 10px; color: #888; text-align: center; margin-top: 12px; }}
</style></head><body>
<div class="store-header">
  <h1>恒星五金机电送货单</h1>
  <div class="info">
    地址：{shop_address} &nbsp;&nbsp; 电话：{shop_tel}
  </div>
</div>
<div class="info-row">
  <span><span class="label">客户名称：</span><span class="value">{customer_name}</span></span>
  <span><span class="label">日期：</span><span class="value">{date}</span></span>
</div>
<div class="info-row">
  <span><span class="label">客户地址：</span><span class="value">{customer_address}</span></span>
  <span><span class="label">客户电话：</span><span class="value">{customer_phone}</span></span>
</div>
<div class="info-row">
  <span><span class="label">单号：</span><span class="value">{order_no}</span></span>
</div>
<table>
<tr><th>序号</th><th>规格型号</th><th>商品名称</th><th>单位</th><th>数量</th><th>单价</th><th>金额</th><th>备注</th></tr>
{rows}
<tr class="total-row"><td colspan="4" style="text-align:right; padding-right:10px;">合计（大写）：{total_cn}</td><td>{total_qty}</td><td></td><td>¥{total_amount}</td><td></td></tr>
</table>
<div class="sign-row">
  <div class="sign-item">经手人：<span></span></div>
  <div class="sign-item">客户签收：<span></span></div>
</div>
<div class="bottom-note">打印时间：{print_time}</div>
</body></html>"""

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
        left.addWidget(icon_badge("🧾", t('ic_orange'), 48, 14))
        ic = QVBoxLayout(); ic.setSpacing(3)
        h1 = QLabel("账单打印")
        h1.setStyleSheet("font-size:17px;font-weight:700;")
        ic.addWidget(h1)
        left.addLayout(ic)
        hl.addLayout(left)
        # 右侧：客户信息 | stretch → [选择客户] [移除勾选] [清空清单]
        right_grp = QHBoxLayout(); right_grp.setSpacing(10)
        self.customer_info = QLabel("")
        self.customer_info.setStyleSheet(f"color:{t('accent')};font-size:12px;font-weight:600;")
        right_grp.addWidget(self.customer_info)
        right_grp.addStretch()
        self.btn_select_cust = QPushButton("选择客户")
        self.btn_select_cust.setObjectName("btn_secondary")
        self.btn_select_cust.setFixedHeight(36)
        self.btn_select_cust.clicked.connect(self._on_select_customer)
        right_grp.addWidget(self.btn_select_cust)
        self.btn_remove = QPushButton("移除勾选"); self.btn_remove.setObjectName("btn_secondary")
        self.btn_remove.setFixedHeight(36)
        right_grp.addWidget(self.btn_remove)
        self.btn_clear = QPushButton("清空清单"); self.btn_clear.setObjectName("btn_secondary")
        self.btn_clear.setFixedHeight(36)
        right_grp.addWidget(self.btn_clear)
        hl.addLayout(right_grp)
        lay.addWidget(hc)
        self._selected_customer = None  # 当前选中的客户数据

        # ── 表格 ──
        tc = QFrame(); tc.setObjectName("card")
        add_shadow(tc, 20, 25 if IS_DARK else 8)
        tcl = QVBoxLayout(tc); tcl.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        pal = self.table.palette()
        pal.setColor(QPalette.ColorRole.Highlight, QColor(t('sel')))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor(t('text')))
        pal.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Highlight, QColor(t('sel')))
        pal.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.HighlightedText, QColor(t('text')))
        self.table.setPalette(pal)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["", "规格型号", "商品名称", "单位", "单价", "数量", "金额"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 50)
        for c in range(1, 7):
            self.table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        tcl.addWidget(self.table)

        # 表头全选按钮（居中靠 sectionResized 信号更新位置）
        self._chk_all = QPushButton("全选", self.table.horizontalHeader().viewport())
        self._chk_all.setFixedSize(44, 22)
        self._chk_all.setCheckable(True)
        self._chk_all.clicked.connect(self._on_select_all)
        self._chk_all.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none;
                color:{t('text_mid')}; font-size:12px; font-weight:600; }}
            QPushButton:hover {{ color:{t('accent')}; }}
            QPushButton:checked {{ color:{t('accent')}; }}
        """)
        self.table.horizontalHeader().sectionResized.connect(self._repos_chk)
        # 延迟初始定位（等布局完成）
        QTimer.singleShot(100, self._repos_chk)

        # 空状态
        self.empty_w = QWidget(self.table)
        el = QVBoxLayout(self.empty_w)
        el.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for txt, sz in [("🧾", 48), ("暂无商品，请在商品管理页勾选并点击「＋ 加入打印」", 13)]:
            lb = QLabel(txt); lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lb.setStyleSheet(f"font-size:{sz}px;color:{t('text_sub')};")
            el.addWidget(lb)
        self.empty_w.hide()
        lay.addWidget(tc)

        # ── 底部汇总 + 打印 ──
        bottom = QHBoxLayout(); bottom.setSpacing(16)
        self.total_lbl = QLabel("合计：0 件  |  ¥0.00")
        self.total_lbl.setStyleSheet(f"font-size:18px;font-weight:800;color:{t('accent')};")
        bottom.addWidget(self.total_lbl); bottom.addStretch()

        self.btn_preview = QPushButton("打印预览"); self.btn_preview.setObjectName("btn_secondary")
        self.btn_print   = QPushButton("直接打印"); self.btn_print.setObjectName("btn_primary")
        for b in (self.btn_preview, self.btn_print):
            b.setFixedHeight(38); b.setMinimumWidth(110)
        bottom.addWidget(self.btn_preview); bottom.addSpacing(8); bottom.addWidget(self.btn_print)
        lay.addLayout(bottom)

        self.btn_remove.clicked.connect(self._remove_item)
        self.btn_clear.clicked.connect(self._clear_all)
        self.btn_preview.clicked.connect(self._print_preview)
        self.btn_print.clicked.connect(self._do_print)

    def _on_select_customer(self):
        """弹出客户选择对话框"""
        dlg = CustomerSelectDialog(db_customers(), self.window())
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected:
            self._selected_customer = dlg.selected
            name, addr, phone = dlg.selected[1] or "", dlg.selected[2] or "", dlg.selected[3] or ""
            info = f"当前客户：{name}"
            if addr: info += f"  |  {addr}"
            if phone: info += f"  |  {phone}"
            self.customer_info.setText(info)
        elif dlg._cleared:
            self._selected_customer = None
            self.customer_info.setText("")

    def _toggle_empty(self, show):
        if show:
            self.empty_w.setGeometry(self.table.rect())
            self.empty_w.show()
        else:
            self.empty_w.hide()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "empty_w") and self.empty_w.isVisible():
            self.empty_w.setGeometry(self.table.rect())

    def refresh(self):
        self.table.blockSignals(True)
        total_qty = 0
        total_amt = 0.0
        rows = PRINT_CART
        self.table.setRowCount(len(rows))
        self._row_checkboxes = []
        ck = _ensure_checkmark()
        up_arrow, down_arrow = _ensure_arrow_icons()
        chk_style = f"""
            QCheckBox::indicator {{ width:18px; height:18px; border-radius:5px;
                border:1.5px solid {t('input_border')}; background:{t('input_bg')}; }}
            QCheckBox::indicator:checked {{ background:{t('accent')};
                border-color:{t('accent')}; image:url("{ck}"); }}
        """
        for r, item in enumerate(rows):
            price = item['price']
            qty = item['qty']
            amt = price * qty
            total_qty += qty
            total_amt += amt
            # Col 0: 勾选框
            chk_w = QWidget(); chk_w.setStyleSheet("background:transparent;")
            chk_l = QHBoxLayout(chk_w); chk_l.setContentsMargins(0,0,0,0)
            chk_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk = QCheckBox(); chk.setStyleSheet(chk_style)
            chk_l.addWidget(chk)
            self._row_checkboxes.append(chk)
            self.table.setCellWidget(r, 0, chk_w)
            # Col 1: 规格型号
            self._set_cell(r, 1, item.get('spec', '—'))
            # Col 2: 商品名称
            self._set_cell(r, 2, item['name'])
            # Col 3: 单位
            self._set_cell(r, 3, item.get('unit', '—'))
            # Col 4: 单价（红色）
            pi = QTableWidgetItem(f"¥{price:.2f}")
            pi.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            pi.setForeground(QColor("#ef4444"))
            self.table.setItem(r, 4, pi)
            # Col 5: 数量 SpinBox
            sb = QSpinBox()
            sb.setRange(1, 99999)
            sb.setValue(qty)
            sb.setStyleSheet(f"""
                QSpinBox {{ background:{t('input_bg')}; border:1.5px solid {t('border')};
                            border-radius:8px; color:{t('text')}; font-size:14px;
                            padding:2px 30px 2px 10px; min-height:30px; }}
                QSpinBox::up-button {{ subcontrol-origin:border; subcontrol-position:top right;
                            width:28px; border:none; border-left:1px solid {t('border')};
                            border-bottom:1px solid {t('border')};
                            border-radius:0 7px 0 0; background:{t('btn2_bg')}; }}
                QSpinBox::up-button:hover {{ background:{t('btn2_hover')}; }}
                QSpinBox::down-button {{ subcontrol-origin:border; subcontrol-position:bottom right;
                            width:28px; border:none; border-left:1px solid {t('border')};
                            border-radius:0 0 7px 0; background:{t('btn2_bg')}; }}
                QSpinBox::down-button:hover {{ background:{t('btn2_hover')}; }}
                QSpinBox::up-arrow {{ image:url("{up_arrow}"); width:10px; height:6px; }}
                QSpinBox::down-arrow {{ image:url("{down_arrow}"); width:10px; height:6px; }}
            """)
            sb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sb.valueChanged.connect(lambda val, idx=r: self._qty_changed(idx, val))
            sw = QWidget(); sl = QHBoxLayout(sw)
            sl.setContentsMargins(8, 6, 8, 6)
            sl.addWidget(sb)
            sw.setStyleSheet("background:transparent;")
            self.table.setCellWidget(r, 5, sw)
            # Col 6: 金额
            ai = QTableWidgetItem(f"¥{amt:.2f}")
            ai.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            ai.setForeground(QColor("#ef4444"))
            self.table.setItem(r, 6, ai)

        self.table.blockSignals(False)
        self._toggle_empty(len(rows) == 0)
        self.total_lbl.setText(f"合计：{total_qty} 件  |  ¥{total_amt:,.2f}")
        self.status_sig.emit(f"打印清单共 {len(rows)} 种商品，{total_qty} 件  |  ¥{total_amt:,.2f}")
        # 重置全选按钮
        if hasattr(self, '_chk_all'):
            self._chk_all.blockSignals(True)
            self._chk_all.setChecked(False)
            self._chk_all.setText("全选")
            self._chk_all.blockSignals(False)

    def _set_cell(self, r, c, text):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(r, c, item)

    def _qty_changed(self, idx, val):
        if idx < len(PRINT_CART):
            PRINT_CART[idx]['qty'] = val
            amt = PRINT_CART[idx]['price'] * val
            self.table.item(idx, 6).setText(f"¥{amt:.2f}")
            self._update_total()

    def _remove_at(self, idx):
        if 0 <= idx < len(PRINT_CART):
            PRINT_CART.pop(idx)
        self.refresh()

    def _remove_item(self):
        """移除勾选的行（从后往前删避免索引错乱）"""
        to_remove = []
        for r, chk in enumerate(self._row_checkboxes):
            if chk.isChecked():
                to_remove.append(r)
        if not to_remove:
            Toast.show_msg(self.window(), "请先勾选要移除的商品")
            return
        for idx in reversed(to_remove):
            if 0 <= idx < len(PRINT_CART):
                PRINT_CART.pop(idx)
        self.refresh()

    def _repos_chk(self):
        """把表头全选按钮居中放置在第 0 列"""
        x = self.table.horizontalHeader().sectionViewportPosition(0)
        w = self.table.horizontalHeader().sectionSize(0)
        self._chk_all.move(x + (w - 44) // 2, 3)

    def _on_select_all(self):
        checked = self._chk_all.isChecked()
        self._chk_all.setText("取消" if checked else "全选")
        for chk in getattr(self, '_row_checkboxes', []):
            chk.setChecked(checked)

    def _clear_all(self):
        if not PRINT_CART:
            return
        if MsgBox.confirm(self.window(), "清空清单", "确定清空整个打印清单吗？"):
            PRINT_CART.clear()
            self.refresh()

    def _update_total(self):
        total_qty = sum(it['qty'] for it in PRINT_CART)
        total_amt = sum(it['price'] * it['qty'] for it in PRINT_CART)
        self.total_lbl.setText(f"合计：{total_qty} 件  |  ¥{total_amt:,.2f}")

    # ── 打印 ──
    SHOP_ADDRESS = "江门市蓬江区杜阮镇江杜中路200号"
    SHOP_TEL     = "13632086363"
    ORDER_NO     = ""  # 单号由日期+序号自动生成

    @staticmethod
    def _num_cn(n: float) -> str:
        """金额转中文大写"""
        units = ["", "拾", "佰", "仟", "万"]
        digits = "零壹贰叁肆伍陆柒捌玖"
        if n <= 0: return "零元整"
        total_cents = int(round(n * 100))
        yuan = total_cents // 100
        jiao = (total_cents % 100) // 10
        fen  = total_cents % 10
        result = ""
        if yuan == 0: result = "零"
        s = str(yuan)
        for i, ch in enumerate(s):
            d = int(ch)
            pos = len(s) - 1 - i
            result += (digits[d] + (units[pos % 5] if pos % 5 != 0 else ""))
            if pos == 4: result += "万"
        result = result.rstrip("零") + "元"
        if jiao == 0 and fen == 0: result += "整"
        else:
            if jiao > 0: result += digits[jiao] + "角"
            if fen  > 0: result += digits[fen]  + "分"
        return "".join(c for i, c in enumerate(result)
                       if not (c == "零" and i + 1 < len(result) and result[i + 1] in "零万元整角分"))

    def _gen_html(self):
        from datetime import datetime
        now = datetime.now()
        # 自动生成单号
        date_prefix = now.strftime("%Y%m%d")
        n = len(PRINT_CART)
        order_no = f"{date_prefix}-{n:03d}"
        rows_html = ""
        total_qty = 0
        total_amt = 0.0
        for i, item in enumerate(PRINT_CART, 1):
            amt = item['price'] * item['qty']
            total_qty += item['qty']
            total_amt += amt
            rows_html += (
                f"<tr><td>{i}</td><td>{item.get('spec','—')}</td><td>{item['name']}</td>"
                f"<td>{item.get('unit','—')}</td><td class='num'>{item['qty']}</td>"
                f"<td class='num'>¥{item['price']:.2f}</td>"
                f"<td class='num'>¥{amt:.2f}</td><td></td></tr>"
            )
        # 获取选中的客户信息
        cust_data = self._selected_customer
        if cust_data:
            customer_name = cust_data[1] or ""
            customer_address = cust_data[2] or ""
            customer_phone = cust_data[3] or ""
        else:
            customer_name = ""
            customer_address = ""
            customer_phone = ""
        html = self.PRINT_HTML.format(
            date=now.strftime("%Y-%m-%d"),
            rows=rows_html,
            total_qty=total_qty,
            total_amount=f"{total_amt:,.2f}",
            total_cn=self._num_cn(total_amt),
            shop_address=self.SHOP_ADDRESS,
            shop_tel=self.SHOP_TEL,
            customer_name=customer_name,
            customer_address=customer_address,
            customer_phone=customer_phone,
            order_no=order_no,
            print_time=now.strftime("%Y-%m-%d %H:%M"),
        )
        # 保存 HTML 到项目目录，方便查阅
        base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
               else os.path.dirname(os.path.abspath(__file__))
        html_path = os.path.join(base, "送货单模板.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        return html

    def _print_preview(self):
        if not PRINT_CART:
            Toast.show_msg(self.window(), "打印清单为空，请先添加商品")
            return
        try:
            self._gen_html()  # 内部会保存 送货单模板.html
            base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
                   else os.path.dirname(os.path.abspath(__file__))
            html_path = os.path.join(base, "送货单模板.html")
            os.startfile(html_path)
            self.status_sig.emit("✓  已在浏览器中打开打印预览")
        except Exception as e:
            MsgBox.warning(self.window(), "打印预览失败",
                           f"无法打开浏览器预览。\n\n错误：{e}")

    def _do_print(self):
        if not PRINT_CART:
            Toast.show_msg(self.window(), "打印清单为空，请先添加商品")
            return
        # 如果未选择客户，弹出确认
        if self._selected_customer is None:
            if not MsgBox.confirm(self.window(), "未选择客户",
                                  "当前未选择客户，送货单将不显示客户信息。\n确定继续打印吗？",
                                  confirm_text="继续打印"):
                return
        try:
            self._gen_html()  # 保存 送货单模板.html
            base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
                   else os.path.dirname(os.path.abspath(__file__))
            html_path = os.path.join(base, "送货单模板.html")
            # 1) QWebEngineView (Chromium) 静默渲染 HTML → PDF
            self._print_view = QWebEngineView()
            self._print_view.setVisible(False)
            self._print_view.load(QUrl.fromLocalFile(html_path))
            self._print_view.loadFinished.connect(self._on_html_loaded)
        except Exception as e:
            MsgBox.warning(self.window(), "打印失败",
                           f"无法打印，请检查打印机连接。\n\n错误：{e}")

    def _on_html_loaded(self, ok: bool):
        if not ok:
            MsgBox.warning(self.window(), "打印失败", "页面加载失败")
            return
        pdf_path = os.path.join(os.environ.get("TEMP", "."), "恒星送货单.pdf")
        self._print_view.page().printToPdf(pdf_path)
        self._print_view.page().pdfPrintingFinished.connect(
            lambda fp, suc: self._on_pdf_ready(fp, suc))

    def _on_pdf_ready(self, file_path: str, success: bool):
        if not success:
            MsgBox.warning(self.window(), "打印失败", "PDF 生成失败")
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        dlg = QPrintDialog(printer, self.window())
        dlg.setWindowTitle("打印 - 恒星五金出货清单")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self._print_view = None
            return
        doc = QPdfDocument(None)
        doc.load(file_path)
        painter = QPainter(printer)
        for i in range(doc.pageCount()):
            if i > 0:
                printer.newPage()
            img = doc.render(i, printer.pageRect(QPrinter.Unit.DevicePixel).size().toSize())
            if not img.isNull():
                painter.drawImage(0, 0,
                    img.scaled(printer.pageRect(QPrinter.Unit.DevicePixel).size().toSize(),
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation))
        painter.end()
        self.status_sig.emit("✓  已发送到打印机")
        self._print_view = None
