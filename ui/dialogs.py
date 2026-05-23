"""弹窗 — ProductDialog, CategoryDialog, DevPanel"""
import sys, os, json, uuid, hashlib, shutil

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QFrame, QScrollArea, QFileDialog,
    QGridLayout, QWidget, QSpinBox,
    QListWidget, QListWidgetItem, QAbstractItemView,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QColor

from core.config import get_app_dir, APP_VERSION, UPDATE_CHECK_URL
from core.db import (db_cat_names, db_cat_add, db_cat_update, db_cat_reorder,
                     db_cat_delete, db_cats, _img_dir)
from ui.theme import (t, T, IS_DARK, CAT_COLORS, CAT_ICONS, _color_for, _icon_for,
                       make_qss, PINNED_COUNT, DEFAULT_COLORS, DEFAULT_ICONS)
from ui.widgets import add_shadow, icon_badge, cat_badge, MsgBox, DropdownSelect

class DevPanel(QDialog):
    """开发者工具面板 —— 双击版本号标签打开"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("开发者工具")
        self.setMinimumSize(420, 300)
        self.resize(440, 340)
        self._build_ui()
        self._apply_theme()
        self._refresh_status()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        title = QLabel("开发者工具")
        title.setStyleSheet("font-size:18px;font-weight:700;")
        lay.addWidget(title)

        # ── 状态信息 ──
        status_card = QFrame()
        status_card.setObjectName("devStatusCard")
        sc_lay = QVBoxLayout(status_card)
        sc_lay.setContentsMargins(16, 12, 16, 12)
        sc_lay.setSpacing(6)
        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet("font-size:12px;")
        sc_lay.addWidget(self._status_lbl)
        lay.addWidget(status_card)

        # ── 测试版本号输入 ──
        ver_row = QHBoxLayout()
        ver_row.setSpacing(8)
        ver_label = QLabel("测试版本号:")
        ver_label.setStyleSheet("font-size:12px;")
        self._test_ver = QLineEdit("99.0.0")
        self._test_ver.setFixedWidth(100)
        self._test_ver.setStyleSheet("font-size:12px;padding:4px 8px;")
        ver_row.addWidget(ver_label)
        ver_row.addWidget(self._test_ver)
        ver_row.addStretch()
        lay.addLayout(ver_row)

        # ── 测试更新日志 ──
        notes_row = QHBoxLayout()
        notes_row.setSpacing(8)
        notes_label = QLabel("测试日志:")
        notes_label.setStyleSheet("font-size:12px;")
        self._test_notes = QLineEdit("开发者测试更新（模拟）")
        self._test_notes.setStyleSheet("font-size:12px;padding:4px 8px;")
        notes_row.addWidget(notes_label)
        notes_row.addWidget(self._test_notes)
        lay.addLayout(notes_row)

        # ── 按钮区 ──
        btn_grid = QGridLayout()
        btn_grid.setSpacing(8)

        self._gen_btn = QPushButton("生成测试版本文件")
        self._gen_btn.setObjectName("devGenBtn")
        self._gen_btn.setFixedHeight(38)
        self._gen_btn.clicked.connect(self._gen_test_file)
        btn_grid.addWidget(self._gen_btn, 0, 0, 1, 2)

        self._clear_btn = QPushButton("清除测试文件")
        self._clear_btn.setObjectName("devClearBtn")
        self._clear_btn.setFixedHeight(38)
        self._clear_btn.clicked.connect(self._clear_test_file)
        btn_grid.addWidget(self._clear_btn, 0, 2)

        self._force_check_btn = QPushButton("强制检查更新")
        self._force_check_btn.setObjectName("devCheckBtn")
        self._force_check_btn.setFixedHeight(38)
        self._force_check_btn.clicked.connect(self._force_check)
        btn_grid.addWidget(self._force_check_btn, 1, 0, 1, 2)

        self._close_btn = QPushButton("关闭")
        self._close_btn.setObjectName("devCloseBtn")
        self._close_btn.setFixedHeight(38)
        self._close_btn.clicked.connect(self.accept)
        btn_grid.addWidget(self._close_btn, 1, 2)

        lay.addLayout(btn_grid)

    def _apply_theme(self):
        surface = t("surface")
        card_bg = t("card2")
        border = t("border")
        text_color = t("text")
        text_sub = t("text_sub")
        accent = t("accent")
        accent_h = t("accent_h")
        input_bg = t("input_bg")
        input_border = t("input_border")

        self.setStyleSheet(f"""
            DevPanel {{
                background: {surface};
            }}
            #devStatusCard {{
                background: {card_bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            #devGenBtn {{
                background: {accent};
                color: white;
                border: 0;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            #devGenBtn:hover {{
                background: {accent_h};
            }}
            #devClearBtn {{
                background: {t('danger_bg')};
                color: {t('danger')};
                border: 1px solid {t('danger_border')};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
            }}
            #devCheckBtn {{
                background: {t('btn2_bg')};
                color: {t('btn2_text')};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
            }}
            #devCheckBtn:hover {{
                background: {t('btn2_hover')};
            }}
            #devCloseBtn {{
                background: {t('btn2_bg')};
                color: {t('btn2_text')};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
            }}
            #devCloseBtn:hover {{
                background: {t('btn2_hover')};
            }}
        """)
        self._test_ver.setStyleSheet(
            f"font-size:12px;padding:4px 8px;background:{input_bg};"
            f"color:{text_color};border:1px solid {input_border};border-radius:4px;"
        )
        self._test_notes.setStyleSheet(
            f"font-size:12px;padding:4px 8px;background:{input_bg};"
            f"color:{text_color};border:1px solid {input_border};border-radius:4px;"
        )
        self._status_lbl.setStyleSheet(f"font-size:12px;color:{text_color};")

    def _get_app_dir(self):
        return os.path.dirname(os.path.abspath(
            sys.executable if getattr(sys, "frozen", False) else __file__
        ))

    def _get_test_path(self):
        return os.path.join(self._get_app_dir(), "version_test.json")

    def _refresh_status(self):
        test_path = self._get_test_path()
        lines = [
            f"当前版本: v{APP_VERSION}",
        ]
        if os.path.exists(test_path):
            try:
                with open(test_path, "r", encoding="utf-8") as f:
                    td = json.load(f)
                lines.append(f"测试文件: 存在 (v{td.get('version', '?')})")
                lines.append(f"  日志: {td.get('notes', '无')}")
                lines.append(f"  下载URL: {'模拟下载' if not td.get('download_url') else td['download_url'][:50] + '...'}")
            except Exception:
                lines.append("测试文件: 存在（但无法解析）")
        else:
            lines.append("测试文件: 无")
        lines.append(f"远程检查: {'已启用' if UPDATE_CHECK_URL else '已禁用'}")
        self._status_lbl.setText("\n".join(lines))

    def _gen_test_file(self):
        ver = self._test_ver.text().strip() or "99.0.0"
        notes = self._test_notes.text().strip() or "测试更新"
        data = {
            "version": ver,
            "download_url": "",
            "notes": notes,
        }
        path = self._get_test_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._refresh_status()
        QMessageBox.information(self, "已生成",
            f"测试版本文件已创建:\n{path}\n\n"
            f"版本: v{ver}\n"
            f"下次检查更新时将使用此文件。\n"
            f"删除此文件即可恢复正常检查。")

    def _clear_test_file(self):
        path = self._get_test_path()
        if os.path.exists(path):
            os.remove(path)
            self._refresh_status()
            QMessageBox.information(self, "已清除", "测试版本文件已删除，恢复正常更新检查。")
        else:
            self._refresh_status()
            QMessageBox.information(self, "提示", "没有测试文件需要清除。")

    def _force_check(self):
        """强制立即检查更新"""
        if self.parent() and hasattr(self.parent(), "_check_update"):
            self.parent()._check_update()
            self.accept()  # 关闭面板



class ProductDialog(QDialog):
    def __init__(self, parent, data=None):
        super().__init__(parent)
        self.data = data
        self.setWindowTitle("编辑商品" if data else "新增商品")
        self.setFixedSize(480, 680)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        bg = "#e6e6ec" if not IS_DARK else t('surface')
        self.setStyleSheet(f"""
            QDialog {{ background: transparent; }}
            #dialog_container {{
                background: {bg};
                border: none;
                border-radius: 16px;
            }}
            QWidget {{ background: transparent; color: {t('text')}; }}
            QScrollArea {{ background: {bg}; border: none; }}
            QScrollArea > QWidget > QWidget {{ background: {bg}; }}
            QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {{
                background: {t('input_bg')};
                border: 2px solid {'#a8a8c8' if not IS_DARK else t('input_border')};
                border-radius: 17px;
                color: {t('text')};
                padding: 0 14px;
                font-size: 13px;
                font-family: "Microsoft YaHei";
            }}
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {{
                border-color: {t('accent')};
                border-width: 2px;
                background: {t('card')};
            }}
            QComboBox::drop-down {{ border: none; width: 28px; }}
            QDoubleSpinBox::up-button, QSpinBox::up-button,
            QDoubleSpinBox::down-button, QSpinBox::down-button {{
                background: {t('btn2_bg')}; border: none; width: 20px;
            }}
            QScrollBar:vertical {{ background: {t('card2')}; width: 6px; border-radius: 3px; }}
            QScrollBar::handle:vertical {{ background: {t('border')}; border-radius: 3px; min-height: 30px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        self._build()
        self._center()

    def _center(self):
        p = self.parent()
        if p:
            self.move(p.x()+(p.width()-self.width())//2,
                      p.y()+(p.height()-self.height())//2)

    def _inp(self, ph=""):
        w = QLineEdit(); w.setObjectName("form_input")
        w.setPlaceholderText(ph); w.setFixedHeight(34); return w

    def _build(self):
        bg = "#e6e6ec" if not IS_DARK else t('surface')
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(0)

        container = QWidget()
        container.setObjectName("dialog_container")
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        add_shadow(container, 32, 80 if IS_DARK else 30)
        root.addWidget(container)

        # 顶部粉色条
        bar = QWidget()
        bar.setFixedHeight(4)
        bar.setStyleSheet(f"background:{t('accent')}; border-radius:16px 16px 0 0;")
        cl.addWidget(bar)

        # 表单
        sa = QScrollArea(); sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        fw = QWidget()
        fw.setStyleSheet(f"background:{bg};")
        fl = QVBoxLayout(fw); fl.setContentsMargins(24,16,24,10); fl.setSpacing(10)

        def add_field(lbl_text, widget):
            lbl = QLabel(lbl_text)
            lbl.setStyleSheet(f"color:{t('text_mid')};font-size:11px;font-weight:600;")
            fl.addWidget(lbl); fl.addWidget(widget)

        self.e_name = self._inp("请输入商品名称")
        add_field("商品名称  *", self.e_name)

        self.e_spec = self._inp("")
        add_field("规格尺寸", self.e_spec)

        self.e_cat = DropdownSelect(db_cat_names())
        self.e_cat.setFixedHeight(34)
        add_field("分类  *", self.e_cat)

        self.e_purchase_price = self._inp("")
        self.e_purchase_price.setFixedHeight(34)
        add_field("进货价", self.e_purchase_price)

        self.e_price = self._inp("")
        self.e_price.setFixedHeight(34)
        add_field("零售价  *", self.e_price)

        self.e_size = self._inp("")
        add_field("单位", self.e_size)

        self.e_loc = self._inp("")
        add_field("存放位置", self.e_loc)

        self.e_remark = self._inp("其他说明（可选）")
        add_field("备注", self.e_remark)

        # 图片
        img_lbl = QLabel("商品图片")
        img_lbl.setStyleSheet(f"color:{t('text_mid')};font-size:11px;font-weight:600;")
        fl.addWidget(img_lbl)

        self._img_path = ""
        img_row = QHBoxLayout(); img_row.setSpacing(10)

        # 可点击的图片框
        self._img_preview = QLabel()
        self._img_preview.setFixedSize(80, 80)
        self._img_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_preview.setCursor(Qt.CursorShape.PointingHandCursor)
        self._img_preview.setStyleSheet(f"""QLabel{{
            background:{t('input_bg')};
            border:1.5px dashed {t('input_border')};
            border-radius:12px;
            color:{t('text_sub')};
            font-size:26px;
        }}""")
        self._img_preview.setText("+")
        self._img_preview.mousePressEvent = lambda e: self._show_full() if self._img_path else self._pick_image()

        self._img_clear = QPushButton("清除")
        self._img_clear.setFixedHeight(32); self._img_clear.setFixedWidth(60)
        self._img_clear.setStyleSheet(f"""QPushButton{{background:{t('danger_bg')};
            border:1.5px solid {t('danger_border')};border-radius:12px;
            color:{t('danger')};font-size:12px;}}
            QPushButton:hover{{background:{t('danger')};color:white;}}""")
        self._img_clear.clicked.connect(self._clear_image)
        self._img_clear.hide()

        img_row.addWidget(self._img_preview)
        img_row.addWidget(self._img_clear)
        img_row.addStretch()
        fl.addLayout(img_row)

        sa.setWidget(fw); cl.addWidget(sa)

        # 按钮栏
        bb = QWidget(); bb.setFixedHeight(56)
        bb.setStyleSheet(f"background:{bg}; border-top:1px solid {t('border')};"
                         f"border-radius:0 0 16px 16px;")
        bl = QHBoxLayout(bb); bl.setContentsMargins(20,0,20,0)
        bl.addStretch()
        cancel = QPushButton("取消")
        cancel.setFixedSize(88,34)
        cancel.setStyleSheet(f"""QPushButton{{
            background:{t('btn2_bg')}; border:1.5px solid {t('border')};
            border-radius:14px; color:{t('btn2_text')}; font-size:13px;
        }}
        QPushButton:hover{{
            background:{t('btn2_hover')}; color:{t('text')}; border-color:{t('accent')};
        }}""")
        cancel.clicked.connect(self.reject)
        save = QPushButton("保存")
        save.setFixedSize(96,34)
        save.setStyleSheet(f"""QPushButton{{
            background:{t('accent')}; border:none;
            border-radius:14px; color:white; font-size:13px; font-weight:700;
        }}
        QPushButton:hover{{ background:{t('accent_h')}; }}""")
        save.clicked.connect(self._save)
        bl.addWidget(cancel); bl.addSpacing(10); bl.addWidget(save)
        cl.addWidget(bb)

        if self.data:
            self.e_name.setText(self.data[1]); self.e_cat.set_current_text(self.data[2])
            self.e_purchase_price.setText(str(self.data[3]))
            self.e_price.setText(str(self.data[4])); self.e_size.setText(self.data[5] or "")
            self.e_loc.setText(self.data[6] or "")
            self.e_remark.setText(self.data[7] or "")
            self.e_spec.setText(self.data[9] or "")
            if self.data[8]:
                self._img_path = self.data[8]
                self._update_preview()

    def _pick_image(self):
        if getattr(self, '_picking', False):
            return
        self._picking = True
        try:
            path, _ = QFileDialog.getOpenFileName(
                self, "选择图片", "", "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
            if not path: return
            import shutil, uuid, hashlib
            # 计算源文件哈希，检查是否已存在相同内容
            with open(path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            img_dir = _img_dir()
            for existing in os.listdir(img_dir):
                ep = os.path.join(img_dir, existing)
                if os.path.isfile(ep) and os.path.getsize(ep) == os.path.getsize(path):
                    with open(ep, 'rb') as f:
                        if hashlib.sha256(f.read()).hexdigest() == file_hash:
                            self._img_path = existing
                            self._update_preview()
                            return
            # 不重复，复制新文件
            ext = os.path.splitext(path)[1]
            fname = f"{uuid.uuid4().hex}{ext}"
            dest = os.path.join(img_dir, fname)
            shutil.copy2(path, dest)
            self._img_path = fname
            self._update_preview()
        finally:
            self._picking = False

    def _clear_image(self):
        self._img_path = ""
        self._img_preview.setPixmap(QPixmap())
        self._img_preview.setText("+")
        self._img_clear.hide()

    def _update_preview(self):
        full = os.path.join(_img_dir(), self._img_path)
        if self._img_path and os.path.exists(full):
            pix = QPixmap(full).scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
            self._img_preview.setPixmap(pix)
            self._img_preview.setText("")
            self._img_clear.show()
        else:
            self._img_preview.setPixmap(QPixmap())
            self._img_preview.setText("+")
            self._img_clear.hide()

    def _show_full(self):
        full = os.path.join(_img_dir(), self._img_path)
        if not self._img_path or not os.path.exists(full):
            return
        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        dlg.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        root = QVBoxLayout(dlg); root.setContentsMargins(8,8,8,8)
        container = QFrame()
        container.setStyleSheet(f"background:{t('card')}; border:2px solid {t('accent')}; border-radius:16px;")
        cl = QVBoxLayout(container); cl.setContentsMargins(16,16,16,16); cl.setSpacing(12)
        pix = QPixmap(full)
        if pix.width() > 550 or pix.height() > 450:
            pix = pix.scaled(550, 450, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        lbl = QLabel(); lbl.setPixmap(pix); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(lbl)
        close_btn = QPushButton("关闭")
        close_btn.setFixedSize(80, 34)
        close_btn.setStyleSheet(f"QPushButton{{background:{t('accent')}; border:none; border-radius:13px; color:white; font-size:13px;}} QPushButton:hover{{background:{t('accent_h')};}}")
        close_btn.clicked.connect(dlg.accept)
        btn_row = QHBoxLayout(); btn_row.addStretch(); btn_row.addWidget(close_btn); btn_row.addStretch()
        cl.addLayout(btn_row)
        add_shadow(container, 32, 80 if IS_DARK else 30)
        root.addWidget(container)
        dlg.exec()

    def _save(self):
        name = self.e_name.text().strip()
        if not name:
            MsgBox.warning(self, "输入错误", "商品名称不能为空，请填写后再保存。"); return
        try:
            purchase_price = float(self.e_purchase_price.text().strip() or "0")
        except ValueError:
            MsgBox.warning(self, "输入错误", "进货价请输入有效的数字。"); return
        try:
            price = float(self.e_price.text().strip() or "0")
        except ValueError:
            MsgBox.warning(self, "输入错误", "零售价请输入有效的数字。"); return
        self.result_data = (name, self.e_cat.current_text().strip(), purchase_price, price,
                            self.e_size.text().strip(), self.e_loc.text().strip(),
                            self.e_remark.text().strip(), self._img_path,
                            self.e_spec.text().strip())
        self.accept()



class CategoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("管理分类")
        self.setFixedSize(440, 500)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        bg = "#f2f2f5" if not IS_DARK else t('surface')
        self.setStyleSheet(f"""
            QDialog {{ background: transparent; }}
            #cat_container {{
                background: {bg};
                border: none;
                border-radius: 16px;
            }}
            QWidget {{ background: transparent; color: {t('text')}; }}
            QListWidget {{
                background: {t('card')};
                border: 2px solid {t('input_border')};
                border-radius: 10px;
                color: {t('text')};
                font-size: 14px;
                outline: none;
            }}
            QListWidget::item {{ padding: 8px 12px; border-radius: 8px; }}
            QListWidget::item:selected {{ background: {t('sel')}; color: {t('text')}; }}
            QLineEdit {{
                background: {t('input_bg')};
                border: 2px solid {t('input_border')};
                border-radius: 10px;
                color: {t('text')};
                padding: 0 12px;
                font-size: 14px;
            }}
            QLineEdit:focus {{ border-color: {t('accent')}; }}
        """)
        self._editing = None  # 正在编辑的分类名
        self._build()
        self._center()
        add_shadow(self.findChild(QWidget, "cat_container"), 32, 80 if IS_DARK else 30)

    def _center(self):
        p = self.parent()
        if p:
            self.move(p.x()+(p.width()-self.width())//2,
                      p.y()+(p.height()-self.height())//2)

    def _build(self):
        bg = "#f2f2f5" if not IS_DARK else t('surface')
        text_color = "#18181c" if not IS_DARK else t('text')
        root = QVBoxLayout(self)
        root.setContentsMargins(8,8,8,8); root.setSpacing(0)

        container = QWidget(); container.setObjectName("cat_container")
        add_shadow(container, 32, 80 if IS_DARK else 30)
        cl = QVBoxLayout(container); cl.setContentsMargins(20,20,20,16); cl.setSpacing(12)
        root.addWidget(container)

        # 标题行
        title_row = QHBoxLayout()
        title_lbl = QLabel("管理分类")
        title_lbl.setStyleSheet(f"font-size:16px;font-weight:700;color:{text_color};")
        close_btn = QPushButton("✕"); close_btn.setFixedSize(28,28)
        close_btn.setStyleSheet(f"""QPushButton{{background:{t('btn2_bg')};border:1px solid {t('border')};
            border-radius:8px;color:{t('text_mid')};font-size:13px;}}
            QPushButton:hover{{background:{t('danger')};color:white;}}""")
        close_btn.clicked.connect(self.accept)
        title_row.addWidget(title_lbl); title_row.addStretch(); title_row.addWidget(close_btn)
        cl.addLayout(title_row)

        # 分类列表（可拖拽排序，双击直接 inline 编辑）
        self.list_w = QListWidget()
        self.list_w.setFixedHeight(220)
        self.list_w.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_w.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_w.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.list_w.model().rowsMoved.connect(self._on_reorder)
        self.list_w.itemChanged.connect(self._on_item_changed)
        self._reload_list()
        cl.addWidget(self.list_w)

        # 操作按钮行
        op_row = QHBoxLayout(); op_row.setSpacing(8)
        self.btn_del_cat = QPushButton("删除")
        self.btn_del_cat.setObjectName("btn_danger"); self.btn_del_cat.setFixedHeight(34)
        self.btn_del_cat.clicked.connect(self._delete_cat)
        op_row.addStretch(); op_row.addWidget(self.btn_del_cat)
        cl.addLayout(op_row)

        # 分割线
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background:{t('border')};max-height:1px;")
        cl.addWidget(line)

        # 新增分类
        form_lbl = QLabel("新增分类")
        form_lbl.setStyleSheet(f"font-size:13px;font-weight:600;color:{text_color};")
        cl.addWidget(form_lbl)

        name_row = QHBoxLayout(); name_row.setSpacing(8)
        self.inp_name = QLineEdit(); self.inp_name.setPlaceholderText("分类名称")
        self.inp_name.setFixedHeight(36)
        name_row.addWidget(self.inp_name)
        cl.addLayout(name_row)

        save_row = QHBoxLayout(); save_row.setSpacing(8)
        btn_cancel_edit = QPushButton("取消")
        btn_cancel_edit.setFixedHeight(34); btn_cancel_edit.setFixedWidth(90)
        btn_cancel_edit.setStyleSheet(f"""QPushButton{{background:{t('btn2_bg')};border:1.5px solid {t('border')};
            border-radius:14px;color:{t('btn2_text')};font-size:13px;}}
            QPushButton:hover{{background:{t('btn2_hover')};color:{t('text')};}}""")
        btn_cancel_edit.clicked.connect(self.accept)
        btn_save = QPushButton("新增")
        btn_save.setFixedHeight(34); btn_save.setFixedWidth(90)
        btn_save.setStyleSheet(f"""QPushButton{{background:{t('accent')};border:none;
            border-radius:14px;color:white;font-size:13px;font-weight:700;}}
            QPushButton:hover{{background:{t('accent_h')};}}""")
        btn_save.clicked.connect(self._save_cat)
        save_row.addStretch()
        save_row.addWidget(btn_cancel_edit); save_row.addWidget(btn_save)
        cl.addLayout(save_row)

    def _reload_list(self):
        self._block_change = True
        self.list_w.clear()
        text_color = "#18181c" if not IS_DARK else t('text')
        for name, color, icon in db_cats():
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setForeground(QColor(text_color))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.list_w.addItem(item)
        self._block_change = False

    def _on_item_changed(self, item):
        if getattr(self, '_block_change', False): return
        old_name = item.data(Qt.ItemDataRole.UserRole)
        new_name = item.text().strip()
        if not new_name or new_name == old_name: return
        cats = {r[0]:(r[1],r[2]) for r in db_cats()}
        color, icon = cats.get(old_name, ("#64748b","📦"))
        db_cat_update(old_name, new_name, color, icon)
        CAT_COLORS.pop(old_name, None); CAT_ICONS.pop(old_name, None)
        CAT_COLORS[new_name] = color; CAT_ICONS[new_name] = icon
        item.setData(Qt.ItemDataRole.UserRole, new_name)

    def _on_reorder(self):
        names = [self.list_w.item(i).data(Qt.ItemDataRole.UserRole)
                 for i in range(self.list_w.count())]
        db_cat_reorder(names)

    def _on_select(self, row):
        pass

    def _load_edit_item(self, item):
        pass  # 现在 inline 编辑，不需要此方法

    def _load_edit(self):
        pass

    def _clear_form(self):
        self.inp_name.clear()

    def _save_cat(self):
        name = self.inp_name.text().strip()
        if not name:
            MsgBox.warning(self.parent(), "提示", "分类名称不能为空。"); return
        color = _color_for(name)
        icon = _icon_for(name)
        db_cat_add(name, color, icon)
        CAT_COLORS[name] = color
        CAT_ICONS[name] = icon
        self._clear_form()
        self._reload_list()

    def _delete_cat(self):
        item = self.list_w.currentItem()
        if not item:
            MsgBox.info(self.parent(), "提示", "请先选中一个分类再删除。"); return
        name = item.data(Qt.ItemDataRole.UserRole)
        if MsgBox.confirm(self.parent(), "确认删除",
                f"确定删除分类【{name}】吗？\n该分类下的商品将归入「其他」。"):
            self._block_change = True
            db_cat_delete(name)
            CAT_COLORS.pop(name, None)
            CAT_ICONS.pop(name, None)
            self._clear_form()
            self._reload_list()

