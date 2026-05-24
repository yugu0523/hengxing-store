"""商品管理页"""
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QAbstractItemView, QCheckBox, QDialog, QMenu, QSizePolicy,
    QGraphicsDropShadowEffect, QGridLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QTimer, QEvent, QUrl
from PyQt6.QtGui import QColor, QPixmap, QIcon, QPalette

from core.config import get_app_dir
from core.db import (db_count, db_all, db_get, db_insert, db_update, db_delete,
                     db_copy_after, db_cats, db_cat_names, PRINT_CART, _IMG_CACHE, _img_dir,
                     _ensure_checkmark)
from ui.theme import (t, IS_DARK, CAT_COLORS, CAT_ICONS, _icon_for, _color_for,
                       PINNED_COUNT, make_qss, is_dark_theme)
from ui.widgets import (add_shadow, icon_badge, Toast, MsgBox, cat_badge, RedTextDelegate)
from ui.dialogs import ProductDialog, CategoryDialog

class ProductPage(QWidget):
    status_sig   = pyqtSignal(str)
    data_changed = pyqtSignal()       # 新增/编辑/删除/复制/分类变动时触发
    print_changed = pyqtSignal()      # 打印清单变动时触发

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sel_id = None; self._cur_cat = "全部"
        self._more_btn = None
        self._page = 0          # 当前页（0-based）
        self._page_size = 100   # 每页条数
        self._total = 0         # 当前筛选下的总条数
        # 防抖定时器
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._on_search_timeout)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12,12,12,8); lay.setSpacing(16)

        # ── 页头卡片 ──
        hc = QFrame(); hc.setObjectName("card")
        add_shadow(hc, 20, 30 if IS_DARK else 10)
        hl = QHBoxLayout(hc); hl.setContentsMargins(20,16,20,16)

        left = QHBoxLayout(); left.setSpacing(16)
        left.addWidget(icon_badge("📦", t('ic_blue'), 48, 14))
        ic = QVBoxLayout(); ic.setSpacing(3)
        h1 = QLabel("商品管理")
        h1.setStyleSheet("font-size:17px;font-weight:700;")
        ic.addWidget(h1)
        left.addLayout(ic)
        hl.addLayout(left); hl.addStretch()

        self.btn_del   = QPushButton("删除");      self.btn_del.setObjectName("btn_danger")
        self.btn_print = QPushButton("＋  加入打印");  self.btn_print.setObjectName("btn_primary")
        self.btn_edit  = QPushButton("编辑");      self.btn_edit.setObjectName("btn_secondary")
        self.btn_copy  = QPushButton("复制");      self.btn_copy.setObjectName("btn_secondary")
        self.btn_cat   = QPushButton("管理分类");  self.btn_cat.setObjectName("btn_secondary")
        self.btn_add   = QPushButton("＋  新增商品");  self.btn_add.setObjectName("btn_primary")
        for b in (self.btn_del, self.btn_print, self.btn_edit, self.btn_copy, self.btn_cat, self.btn_add):
            b.setFixedHeight(40)
        self.btn_add.setMinimumWidth(120)
        self.btn_print.setMinimumWidth(120)
        hl.addWidget(self.btn_del); hl.addSpacing(8)
        hl.addWidget(self.btn_print); hl.addSpacing(8)
        hl.addWidget(self.btn_edit); hl.addSpacing(8)
        hl.addWidget(self.btn_copy); hl.addSpacing(8)
        hl.addWidget(self.btn_cat); hl.addSpacing(8)
        hl.addWidget(self.btn_add)
        lay.addWidget(hc)

        # ── 搜索 + 分类 ──
        fr = QHBoxLayout(); fr.setSpacing(10)
        fr.setContentsMargins(0,0,0,0)
        self.search = QLineEdit(); self.search.setObjectName("search_box")
        self.search.setPlaceholderText("🔍   搜索商品名称 / 规格 / 备注")
        self.search.setFixedHeight(40); self.search.setMinimumWidth(220)
        fr.addWidget(self.search); fr.addSpacing(4)
        fr.addStretch()
        self.pill_row = fr
        self.pills = {}
        self._build_pills(fr)
        lay.addLayout(fr)

        # ── 表格 ──
        tc = QFrame(); tc.setObjectName("card")
        add_shadow(tc, 20, 25 if IS_DARK else 8)
        tcl = QVBoxLayout(tc); tcl.setContentsMargins(0,0,0,0)

        self.table = QTableWidget()
        # 强制覆盖 Fusion 风格的选中色
        pal = self.table.palette()
        pal.setColor(QPalette.ColorRole.Highlight, QColor(t('sel')))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor(t('text')))
        pal.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Highlight, QColor(t('sel')))
        pal.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.HighlightedText, QColor(t('text')))
        self.table.setPalette(pal)
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels(["","商品序号","规格尺寸","商品名称","分类","进货价","零售价","单位","存放位置","图片","备注"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setItemDelegateForColumn(6, RedTextDelegate(self.table))
        self.table.verticalHeader().setDefaultSectionSize(56)
        for col, w in enumerate([50,80,120,185,105,90,90,80,145,60,160]):
            self.table.setColumnWidth(col, w)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.itemSelectionChanged.connect(self._on_select)
        self.table.doubleClicked.connect(self.on_edit)
        tcl.addWidget(self.table)

        # 空状态
        self.empty_w = QWidget(self.table)
        el = QVBoxLayout(self.empty_w)
        el.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for txt, sz, sub in [("📦",48,False),("暂无商品数据",15,False),
                              ("点击右上角「＋ 新增商品」开始添加",12,True)]:
            lb = QLabel(txt); lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lb.setStyleSheet(f"font-size:{sz}px;color:{t('text_sub')};")
            el.addWidget(lb)
        self.empty_w.hide()
        lay.addWidget(tc)

        # ── 分页控件 ──
        pg = QHBoxLayout(); pg.setContentsMargins(4, 0, 4, 0); pg.setSpacing(8)
        self.btn_prev = QPushButton("◀  上一页"); self.btn_prev.setObjectName("btn_secondary")
        self.btn_prev.setFixedHeight(32)
        self.btn_next = QPushButton("下一页  ▶"); self.btn_next.setObjectName("btn_secondary")
        self.btn_next.setFixedHeight(32)
        self.page_lbl = QLabel("第 1 页 / 共 1 页  |  共 0 条")
        self.page_lbl.setStyleSheet(f"color:{t('text_mid')};font-size:12px;")
        pg.addWidget(self.btn_prev)
        pg.addWidget(self.page_lbl)
        pg.addWidget(self.btn_next)
        pg.addStretch()
        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_next.clicked.connect(self._next_page)
        lay.addLayout(pg)

        self.btn_add.clicked.connect(self.on_add)
        self.btn_edit.clicked.connect(self.on_edit)
        self.btn_copy.clicked.connect(self.on_copy)
        self.btn_del.clicked.connect(self.on_delete)
        self.btn_cat.clicked.connect(self.on_manage_cat)
        self.btn_print.clicked.connect(self.on_print_add)
        self.search.textChanged.connect(self._on_search_changed)
        # 全选按钮放在表头第0列
        self._chk_all = QPushButton("全选", self.table.horizontalHeader().viewport())
        self._chk_all.setFixedSize(44, 22)
        self._chk_all.move(3, 3)
        self._chk_all.setCheckable(True)
        self._chk_all.clicked.connect(self._on_select_all)
        self._chk_all.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none;
                color:{t('text_mid')}; font-size:12px; font-weight:600; }}
            QPushButton:hover {{ color:{t('accent')}; }}
            QPushButton:checked {{ color:{t('accent')}; }}
        """)
        self._set_cat("全部", init=True)
        # 事件过滤：防止点击空白区域取消选中，失焦后强制保持高亮
        self.table.installEventFilter(self)
        self.table.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self.table.viewport() and event.type() == QEvent.Type.MouseButtonPress:
            idx = self.table.indexAt(event.pos())
            if not idx.isValid():
                return True   # 点击空白区域，阻止取消选中
        if obj == self.table and event.type() == QEvent.Type.FocusOut:
            self.table.viewport().update()   # 失焦后强制重绘（AlwaysActiveStyle 保证颜色不变）
        return super().eventFilter(obj, event)

    def _build_pills(self, fr):
        # 清除旧 pill
        for name, btn in self.pills.items():
            fr.removeWidget(btn); btn.deleteLater()
        self.pills = {}
        if hasattr(self, '_more_btn') and self._more_btn:
            fr.removeWidget(self._more_btn); self._more_btn.deleteLater()
            self._more_btn = None

        cats = db_cat_names()
        pinned = ["全部"] + cats[:PINNED_COUNT]
        extra  = cats[PINNED_COUNT:]

        for cat in pinned:
            b = QPushButton(cat); b.setObjectName("pill"); b.setFixedHeight(36)
            b.clicked.connect(lambda _, c=cat: self._set_cat(c))
            self.pills[cat] = b; fr.addWidget(b)

        if extra:
            self._more_btn = QPushButton("更多"); self._more_btn.setObjectName("pill")
            self._more_btn.setFixedHeight(36)
            self._more_btn.clicked.connect(lambda: self._show_more_menu(extra))
            fr.addWidget(self._more_btn)
        else:
            self._more_btn = None

    def _show_more_menu(self, extra_cats):
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

        COLS = 4
        grid = QGridLayout(inner)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setSpacing(4)

        for i, cat in enumerate(extra_cats):
            btn = QPushButton(cat)
            btn.setFlat(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(34)
            btn.setMinimumWidth(80)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-radius: 8px;
                    color: {t('text')};
                    font-size: 13px;
                    text-align: center;
                    padding: 0 14px;
                    font-family: "Microsoft YaHei";
                }}
                QPushButton:hover {{
                    background: {t('sel')};
                    color: {t('accent')};
                }}
            """)
            btn.clicked.connect(lambda _, c=cat, p=popup: (self._set_cat(c), p.hide()))
            grid.addWidget(btn, i // COLS, i % COLS)

        outer.addWidget(inner)
        outer.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)

        more = self._more_btn
        popup.adjustSize()
        gpos_br = more.mapToGlobal(QPoint(more.width(), more.height() + 2))
        popup.move(gpos_br.x() - popup.width(), gpos_br.y())
        popup.show()

    def _set_cat(self, cat, init=False):
        self._cur_cat = cat
        for name, btn in self.pills.items():
            btn.setProperty("active", name == cat)
            btn.style().unpolish(btn); btn.style().polish(btn)
        # 更多按钮高亮
        if hasattr(self,'_more_btn') and self._more_btn:
            cats = db_cat_names()
            in_extra = cat in cats[PINNED_COUNT:]
            self._more_btn.setProperty("active", in_extra)
            self._more_btn.style().unpolish(self._more_btn)
            self._more_btn.style().polish(self._more_btn)
        if not init:
            self._page = 0
            self.refresh()

    def _on_search_changed(self):
        """搜索框内容变化时启动防抖计时器"""
        self._search_timer.start()   # 重置为 300ms 后触发

    def _on_search_timeout(self):
        """防抖结束，重置到第 0 页再刷新"""
        self._page = 0
        self.refresh()

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self.refresh()
        else:
            Toast.show_msg(self.window(), "已经是第一页了")

    def _next_page(self):
        total_pages = max(1, (self._total + self._page_size - 1) // self._page_size)
        if self._page < total_pages - 1:
            self._page += 1
            self.refresh()
        else:
            Toast.show_msg(self.window(), "已经是最后一页了")

    def refresh(self):
        kw = self.search.text()
        self._total = db_count(kw, self._cur_cat)
        total_pages = max(1, (self._total + self._page_size - 1) // self._page_size)
        # 防止页码越界（比如删除后页数减少）
        if self._page >= total_pages:
            self._page = max(0, total_pages - 1)

        rows = db_all(kw, self._cur_cat, limit=self._page_size, offset=self._page * self._page_size)

        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        self._row_checkboxes = []   # 每次刷新重置
        ck = _ensure_checkmark()
        chk_style = f"""
            QCheckBox::indicator {{ width:18px; height:18px; border-radius:5px;
                border:1.5px solid {t('input_border')}; background:{t('input_bg')}; }}
            QCheckBox::indicator:checked {{ background:{t('accent')};
                border-color:{t('accent')}; image:url("{ck}"); }}
        """
        base_seq = self._page * self._page_size  # 序号基数
        for r, row in enumerate(rows):
            pid,name,cat,purchase_price,price,size,loc,remark,image_path,spec = row
            # col 0: 勾选框(widget); 1:序号 2:规格 3:名称 4:分类(widget) 5:进货 6:零售 7:单位 8:存放 9:图片(widget) 10:备注
            chk_w = QWidget(); chk_w.setStyleSheet("background:transparent;")
            chk_l = QHBoxLayout(chk_w); chk_l.setContentsMargins(0,0,0,0)
            chk_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk = QCheckBox(); chk.setStyleSheet(chk_style)
            chk.setProperty("pid", pid)
            chk_l.addWidget(chk)
            self._row_checkboxes.append(chk)   # 存入列表
            self.table.setCellWidget(r, 0, chk_w)

            vals = [str(base_seq + r + 1), spec or "—", name, cat,
                    f"¥{purchase_price:.2f}", f"¥{price:.2f}",
                    size or "—", loc or "—", None, remark or ""]
            for c, val in enumerate(vals):
                if c in (3, 8): continue  # 分类和图片用 widget
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if c == 0:
                    item.setForeground(QColor(t('text_sub')))
                    item.setData(Qt.ItemDataRole.UserRole, pid)
                if c == 5:
                    item.setForeground(QColor("#ef4444"))
                self.table.setItem(r, c + 1, item)
            # 分类 badge → col 4
            bw = QWidget(); bl = QHBoxLayout(bw)
            bl.setContentsMargins(6,6,6,6)
            badge = cat_badge(cat)
            badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            bl.addStretch(); bl.addWidget(badge); bl.addStretch()
            bw.setStyleSheet("background:transparent;")
            bw.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self.table.setCellWidget(r, 4, bw)
            # 图片缩略图 → col 9（缓存最多保留 200 张，超出时清空旧缓存）
            img_w = QWidget(); img_l = QHBoxLayout(img_w)
            img_l.setContentsMargins(4,4,4,4)
            img_w.setStyleSheet("background:transparent;")
            full_path = os.path.join(_img_dir(), image_path) if image_path else ""
            if full_path and os.path.exists(full_path):
                if image_path not in _IMG_CACHE:
                    if len(_IMG_CACHE) >= 200:
                        _IMG_CACHE.clear()
                    _IMG_CACHE[image_path] = QPixmap(full_path).scaled(
                        40, 40, Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)
                pix = _IMG_CACHE[image_path]
                lbl = QLabel()
                lbl.setPixmap(pix)
                lbl.setFixedSize(40, 40)
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet("border-radius:6px; background:transparent; cursor:pointer;")
                lbl.setCursor(Qt.CursorShape.PointingHandCursor)
                lbl.mousePressEvent = lambda e, fp=full_path: self._show_full_image(fp)
                lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
                img_l.addStretch(); img_l.addWidget(lbl); img_l.addStretch()
            else:
                ph = QLabel("—")
                ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
                ph.setStyleSheet(f"color:{t('text_sub')};font-size:13px;background:transparent;")
                ph.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                img_l.addWidget(ph)
                img_w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self.table.setCellWidget(r, 9, img_w)

        self.table.blockSignals(False)
        self._toggle_empty(self._total == 0)
        self._sel_id = None
        if hasattr(self, '_chk_all'):
            self._chk_all.blockSignals(True)
            self._chk_all.setChecked(False)
            self._chk_all.setText("全选")
            self._chk_all.blockSignals(False)

        # 更新分页控件
        self.page_lbl.setText(
            f"第 {self._page + 1} 页 / 共 {total_pages} 页  |  共 {self._total} 条")
        self.btn_prev.setEnabled(True)
        self.btn_next.setEnabled(True)
        self.status_sig.emit(f"共 {self._total} 条商品记录，当前第 {self._page + 1}/{total_pages} 页")

    def _show_full_image(self, path):
        dlg = QDialog(self.window())
        dlg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        bg = "#f2f2f5" if not is_dark_theme() else t('surface')
        dlg.setStyleSheet(f"QDialog{{background:{bg};border-radius:16px;}}")
        root = QVBoxLayout(dlg); root.setContentsMargins(0,0,0,0)
        container = QFrame(); container.setObjectName("img_container")
        container.setStyleSheet(f"""QFrame{{background:{'#18181c' if is_dark_theme() else '#f2f2f5'};
            border-radius:16px;border:none;}}""")
        add_shadow(container, 32, t('shadow_alpha'))
        cl = QVBoxLayout(container); cl.setContentsMargins(16,16,16,16); cl.setSpacing(12)
        pix = QPixmap(path)
        max_w, max_h = 600, 500
        if pix.width() > max_w or pix.height() > max_h:
            pix = pix.scaled(max_w, max_h, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        lbl = QLabel(); lbl.setPixmap(pix)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("background:transparent;")
        cl.addWidget(lbl)
        close_btn = QPushButton("关闭"); close_btn.setFixedHeight(36)
        close_btn.setStyleSheet(f"""QPushButton{{background:{t('accent')};border:none;
            border-radius:13px;color:white;font-size:13px;font-weight:700;}}
            QPushButton:hover{{background:{t('accent_h')};}}""")
        close_btn.clicked.connect(dlg.accept)
        cl.addWidget(close_btn)
        root.addWidget(container)
        p = self.window()
        dlg.adjustSize()
        dlg.move(p.x()+(p.width()-dlg.width())//2, p.y()+(p.height()-dlg.height())//2)
        dlg.exec()

    def _toggle_empty(self, show):
        if show:
            self.empty_w.setGeometry(self.table.rect())
            self.empty_w.show()
        else:
            self.empty_w.hide()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self,"empty_w") and self.empty_w.isVisible():
            self.empty_w.setGeometry(self.table.rect())

    def _on_select(self):
        sel = self.table.selectedItems()
        if sel:
            self._sel_id = self.table.item(self.table.currentRow(), 1).data(Qt.ItemDataRole.UserRole)
        else:
            self._sel_id = None

    def _on_select_all(self):
        checked = self._chk_all.isChecked()
        self._chk_all.setText("取消" if checked else "全选")
        for chk in getattr(self, '_row_checkboxes', []):
            chk.setChecked(checked)

    def on_add(self):
        dlg = ProductDialog(self.window())
        dlg.setStyleSheet(make_qss())
        if dlg.exec():
            db_insert(*dlg.result_data); self.refresh()
            self.status_sig.emit(f"✓  已新增：{dlg.result_data[0]}")
            self.data_changed.emit()

    def on_copy(self):
        if not self._sel_id:
            row = self.table.currentRow()
            item = self.table.item(row, 1) if row >= 0 else None
            if item:
                self._sel_id = item.data(Qt.ItemDataRole.UserRole)
        if not self._sel_id:
            MsgBox.info(self.window(), "提示", "请先选中一条商品记录，再点击复制。"); return
        try:
            data = db_get(self._sel_id)
            if not data:
                MsgBox.warning(self.window(), "错误", f"找不到商品 id={self._sel_id}"); return
            db_copy_after(self._sel_id)
            self.refresh()
            self.status_sig.emit(f"✓  已复制：{data[1]}")
            self.data_changed.emit()
        except Exception as e:
            MsgBox.warning(self.window(), "复制失败", str(e))

    def on_manage_cat(self):
        dlg = CategoryDialog(self.window())
        dlg.exec()
        # 刷新分类 pill 和商品列表
        self._build_pills(self.pill_row)
        if self._cur_cat not in ["全部"] + db_cat_names():
            self._cur_cat = "全部"
        self._set_cat(self._cur_cat, init=True)
        self.refresh()
        self.data_changed.emit()

    def on_print_add(self):
        """将打勾的商品加入打印清单，去重"""
        added = 0
        skipped = 0
        checked_any = False
        existing_pids = {item['pid'] for item in PRINT_CART}
        for r, chk in enumerate(getattr(self, '_row_checkboxes', [])):
            if not chk.isChecked():
                continue
            checked_any = True
            item = self.table.item(r, 1)
            if not item:
                continue
            pid = item.data(Qt.ItemDataRole.UserRole)
            if pid in existing_pids:
                skipped += 1
                continue
            data = db_get(pid)
            if not data:
                continue
            _pid, name, cat, _pp, price, size, loc, remark, image_path, spec = data
            PRINT_CART.append({
                'pid': pid, 'name': name, 'spec': spec or '', 'price': price,
                'qty': 1, 'unit': size or ''
            })
            added += 1
        if added:
            msg = f"已添加 {added} 件商品到打印清单"
            if skipped:
                msg += f"，{skipped} 件已在清单中"
            self.status_sig.emit(f"✓  {msg}")
            Toast.show_msg(self.window(), msg)
            self.print_changed.emit()
        elif skipped:
            Toast.show_msg(self.window(), f"所选 {skipped} 件商品已在打印清单中")
        else:
            Toast.show_msg(self.window(), "请先勾选商品，再点击加入打印")

    def on_edit(self):
        if not self._sel_id:
            row = self.table.currentRow()
            item = self.table.item(row, 1) if row >= 0 else None
            if item:
                self._sel_id = item.data(Qt.ItemDataRole.UserRole)
        if not self._sel_id:
            MsgBox.info(self.window(), "提示", "请先在列表中选中一条商品记录，再点击编辑。"); return
        data = db_get(self._sel_id)
        if not data: return
        dlg = ProductDialog(self.window(), data)
        dlg.setStyleSheet(make_qss())
        if dlg.exec():
            db_update(self._sel_id,*dlg.result_data); self.refresh()
            self.status_sig.emit(f"✓  已更新：{dlg.result_data[0]}")
            self.data_changed.emit()

    def on_delete(self):
        # 优先批量删除勾选项
        pids = []
        for r, chk in enumerate(getattr(self, '_row_checkboxes', [])):
            if chk.isChecked():
                item = self.table.item(r, 1)
                if item: pids.append(item.data(Qt.ItemDataRole.UserRole))
        if pids:
            if MsgBox.confirm(self.window(), "确认删除",
                    f"确定删除选中的 {len(pids)} 条商品吗？\n\n删除后数据将无法恢复。"):
                for pid in pids: db_delete(pid)
                self.refresh()
                self.status_sig.emit(f"✓  已删除 {len(pids)} 条商品")
                self.data_changed.emit()
            return
        # 无勾选时走单条删除
        if not self._sel_id:
            row = self.table.currentRow()
            item = self.table.item(row, 1) if row >= 0 else None
            if item:
                self._sel_id = item.data(Qt.ItemDataRole.UserRole)
        if not self._sel_id:
            MsgBox.info(self.window(), "提示", "请先在列表中选中或勾选商品，再点击删除。"); return
        data = db_get(self._sel_id)
        name = data[1] if data else ""
        if MsgBox.confirm(self.window(), "确认删除",
                f"确定要删除商品【{name}】吗？\n\n删除后数据将无法恢复，请谨慎操作。"):
            db_delete(self._sel_id); self.refresh()
            self.status_sig.emit(f"✓  已删除：{name}")
            self.data_changed.emit()

