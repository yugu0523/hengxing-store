import sys, os, sqlite3, traceback
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QLabel, QPushButton, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QDialog,
    QSpinBox, QDoubleSpinBox, QMessageBox, QScrollArea,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
    QAbstractItemView, QSizePolicy, QMenu, QListWidget, QListWidgetItem,
    QStyledItemDelegate,
    QCompleter, QFileDialog, QGridLayout, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QEvent, QRectF, QPointF, QRect, QTimer, QPropertyAnimation, QEasingCurve, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
from PyQt6.QtGui import QPageSize
from PyQt6.QtPdf import QPdfDocument
from PyQt6.QtGui import QColor, QAction, QPalette, QPixmap, QPainter, QPen, QBrush, QPainterPath, QFont, QImage

APP_VERSION = "1.0.0"
UPDATE_CHECK_URL = ""  # 填入你的 version.json 在线地址，如 GitHub Raw 链接

# ══════════════════════════════════════════════════════════════════════
#  自动更新
# ══════════════════════════════════════════════════════════════════════
import json, urllib.request, tempfile, subprocess

def _version_tuple(v):
    return tuple(int(x) for x in v.split("."))

class UpdateChecker(QThread):
    """后台线程：检查更新 / 下载更新"""
    checked = pyqtSignal(dict)   # 检查完毕，发出 version.json 内容
    progress = pyqtSignal(int)   # 下载进度百分比
    finished_ok = pyqtSignal(str)  # 下载完成，发出新 exe 路径
    failed = pyqtSignal(str)     # 出错

    def __init__(self, mode="check", url=""):
        super().__init__()
        self.mode = mode
        self.url = url

    def run(self):
        try:
            if self.mode == "check":
                self._do_check()
            else:
                self._do_download()
        except Exception as e:
            self.failed.emit(str(e))

    def _do_check(self):
        req = urllib.request.Request(self.url, headers={"User-Agent": "恒星五金记账系统/" + APP_VERSION})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        self.checked.emit(data)

    def _do_download(self):
        tmp = os.path.join(tempfile.gettempdir(), "hengxing_update.exe")
        req = urllib.request.Request(self.url, headers={"User-Agent": "恒星五金记账系统/" + APP_VERSION})
        with urllib.request.urlopen(req, timeout=300) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(tmp, "wb") as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        self.progress.emit(int(downloaded * 100 / total))
        self.finished_ok.emit(tmp)


class UpdateDialog(QDialog):
    """发现新版本的提示对话框"""
    def __init__(self, info, parent=None):
        super().__init__(parent)
        self.setWindowTitle("发现新版本")
        self.setFixedSize(460, 340)
        self._info = info
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(28,24,28,24); lay.setSpacing(14)

        title = QLabel(f"  新版本 {self._info.get('version','')} 可用")
        title.setStyleSheet("font-size:18px;font-weight:700;color:#333;")
        lay.addWidget(title)

        if self._info.get("notes"):
            notes = QLabel(self._info["notes"])
            notes.setWordWrap(True)
            notes.setStyleSheet("font-size:13px;color:#555;background:#f8f8f8;border:1px solid #e0e0e0;border-radius:8px;padding:12px;")
            notes.setMinimumHeight(100)
            lay.addWidget(notes)

        lay.addStretch()

        self._progress_lbl = QLabel("")
        self._progress_lbl.setStyleSheet("font-size:12px;color:#888;")
        lay.addWidget(self._progress_lbl)

        from PyQt6.QtWidgets import QProgressBar
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet("QProgressBar{background:#eee;border:0;border-radius:3px;}QProgressBar::chunk{background:#fb7299;border-radius:3px;}")
        self._progress_bar.setValue(0)
        self._progress_bar.hide()
        lay.addWidget(self._progress_bar)

        btn_row = QHBoxLayout(); btn_row.setSpacing(12)
        self._skip_btn = QPushButton("跳过此版本")
        self._skip_btn.setStyleSheet("QPushButton{background:transparent;color:#888;border:1px solid #ddd;border-radius:6px;padding:8px 20px;font-size:13px;}QPushButton:hover{background:#f5f5f5;}")
        self._skip_btn.clicked.connect(self.reject)
        self._update_btn = QPushButton("  立即更新")
        self._update_btn.setStyleSheet("QPushButton{background:#fb7299;color:white;border:0;border-radius:6px;padding:8px 24px;font-size:13px;font-weight:600;}QPushButton:hover{background:#e05a7a;}")
        self._update_btn.clicked.connect(self._start_update)
        btn_row.addWidget(self._skip_btn); btn_row.addStretch(); btn_row.addWidget(self._update_btn)
        lay.addLayout(btn_row)

    def _start_update(self):
        self._skip_btn.setEnabled(False)
        self._update_btn.setEnabled(False)
        self._update_btn.setText("下载中...")
        self._progress_bar.show()
        self._downloader = UpdateChecker(mode="download", url=self._info.get("download_url", ""))
        self._downloader.progress.connect(self._on_progress)
        self._downloader.finished_ok.connect(self._on_done)
        self._downloader.failed.connect(self._on_fail)
        self._downloader.start()

    def _on_progress(self, pct):
        self._progress_bar.setValue(pct)
        self._progress_lbl.setText(f"已下载 {pct}%")

    def _on_done(self, tmp_path):
        self._progress_lbl.setText("下载完成，正在替换...")
        self._apply_update(tmp_path)
        self.accept()

    def _on_fail(self, err):
        self._skip_btn.setEnabled(True)
        self._update_btn.setEnabled(True)
        self._update_btn.setText("重试")
        self._progress_lbl.setText(f"下载失败: {err}")
        self._progress_bar.hide()

    def _apply_update(self, new_exe):
        """写批处理脚本，等当前进程退出后替换 exe 并重启"""
        current_exe = os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)
        bat = os.path.join(tempfile.gettempdir(), "hengxing_update.bat")
        with open(bat, "w", encoding="gbk") as f:
            f.write(f"@echo off\n")
            f.write(f"echo 正在更新恒星五金记账系统...\n")
            f.write(f"timeout /t 2 /nobreak >nul\n")
            f.write(f"taskkill /f /im \"{os.path.basename(current_exe)}\" >nul 2>&1\n")
            f.write(f"timeout /t 1 /nobreak >nul\n")
            f.write(f"copy /y \"{new_exe}\" \"{current_exe}\" >nul\n")
            f.write(f"start \"\" \"{current_exe}\"\n")
            f.write(f"del \"%~f0\"\n")
        subprocess.Popen(["cmd", "/c", bat],
                         creationflags=subprocess.CREATE_NO_WINDOW,
                         close_fds=True)
        # 直接退出当前进程
        QApplication.quit()


# ══════════════════════════════════════════════════════════════════════
#  主题系统
# ══════════════════════════════════════════════════════════════════════
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
    # 统计卡图标背景
    "ic_blue":   "#1a2a3d",
    "ic_green":  "#1a3028",
    "ic_orange": "#3d2a14",
    "ic_purple": "#3d1e28",
    # shadow
    "shadow": "rgba(0,0,0,0.6)",
    # 分类badge背景透明度
    "badge_alpha": "0.18",
    # 次要按钮
    "btn2_bg":    "#252529",
    "btn2_hover": "#2e2e35",
    "btn2_text":  "#a0a0b8",
    # 关闭按钮
    "close_bg":   "#252529",
    # logo badge bg
    "logo_badge": "#fb7299",
    # 统计行卡片
    "stat_row_bg":    "#252529",
    "stat_row_hover": "#2e2e38",
    "cat_icon_bg":    "#1e1e24",
}
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

def t(k): return T[k]

CAT_COLORS = {
    "螺丝": "#3b82f6", "管材": "#22c55e", "工具": "#f97316",
    "电料": "#eab308", "涂料": "#a855f7", "其他": "#64748b",
}
CAT_ICONS = {"螺丝":"🔩","管材":"🪠","工具":"🔧","电料":"⚡","涂料":"🪣","其他":"📦"}
CATEGORIES = list(CAT_COLORS.keys())

DEFAULT_COLORS = ["#3b82f6","#22c55e","#f97316","#eab308","#a855f7","#64748b",
                  "#ec4899","#14b8a6","#f43f5e","#8b5cf6","#06b6d4","#84cc16"]
DEFAULT_ICONS  = ["🔩","🪠","🔧","⚡","🪣","📦","🛠️","🪛","🔑","📎","🧲","⚙️"]

PINNED_COUNT = 5  # 直接显示的分类数，其余收入"更多"

def _color_for(name):
    return CAT_COLORS.get(name, DEFAULT_COLORS[hash(name) % len(DEFAULT_COLORS)])

def _icon_for(name):
    return CAT_ICONS.get(name, DEFAULT_ICONS[hash(name) % len(DEFAULT_ICONS)])

# ══════════════════════════════════════════════════════════════════════
#  数据库
# ══════════════════════════════════════════════════════════════════════
_IMG_CACHE: dict = {}  # fname -> QPixmap(40x40缩略图)
_CHECKMARK_PATH: str = ""

def _ensure_arrow_icons() -> tuple:
    """生成上下箭头 SVG，返回 (up_path, down_path) 供 QSS url() 使用"""
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
           else os.path.dirname(os.path.abspath(__file__))
    up_path = os.path.join(base, "arrow_up.svg")
    down_path = os.path.join(base, "arrow_down.svg")
    up_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 6"><polygon points="5,0 10,6 0,6" fill="#888"/></svg>'
    down_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 6"><polygon points="5,6 10,0 0,0" fill="#888"/></svg>'
    for p, s in [(up_path, up_svg), (down_path, down_svg)]:
        with open(p, "w", encoding="utf-8") as f:
            f.write(s)
    return up_path.replace("\\", "/"), down_path.replace("\\", "/")

def _ensure_checkmark() -> str:
    """把白色勾号 SVG 写到程序目录，返回 QSS url() 可用的正斜杠路径"""
    global _CHECKMARK_PATH
    if _CHECKMARK_PATH and os.path.exists(_CHECKMARK_PATH.replace("/", os.sep)):
        return _CHECKMARK_PATH
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
           else os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "chk.svg")
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 14 14">'
           '<polyline points="2,8 6,12 12,2" stroke="white" stroke-width="2.2"'
           ' fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    _CHECKMARK_PATH = path.replace("\\", "/")
    return _CHECKMARK_PATH
def _db():
    base = os.path.dirname(sys.executable) if getattr(sys,"frozen",False) \
           else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "hardware_store.db")

def init_db():
    with sqlite3.connect(_db()) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, category TEXT NOT NULL,
            purchase_price REAL DEFAULT 0,
            price REAL NOT NULL, size TEXT, location TEXT,
            stock INTEGER DEFAULT 0, remark TEXT,
            image_path TEXT, spec TEXT,
            sort_order INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        # 旧数据库迁移
        cols = [r[1] for r in c.execute("PRAGMA table_info(products)").fetchall()]
        if "purchase_price" not in cols:
            c.execute("ALTER TABLE products ADD COLUMN purchase_price REAL DEFAULT 0")
        if "image_path" not in cols:
            c.execute("ALTER TABLE products ADD COLUMN image_path TEXT")
        if "spec" not in cols:
            c.execute("ALTER TABLE products ADD COLUMN spec TEXT")
        if "sort_order" not in cols:
            c.execute("ALTER TABLE products ADD COLUMN sort_order INTEGER DEFAULT 0")
        if "created_at" not in cols:
            c.execute("ALTER TABLE products ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
        # 无论新建还是迁移，确保 sort_order=0 的记录都按 id 初始化
        c.execute("UPDATE products SET sort_order = id WHERE sort_order = 0")
        # 索引（已存在时 IF NOT EXISTS 跳过）
        c.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_products_sort ON products(sort_order, id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)")
        c.execute("""CREATE TABLE IF NOT EXISTS customers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT DEFAULT '',
            phone TEXT DEFAULT '')""")
        c.execute("""CREATE TABLE IF NOT EXISTS categories(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT NOT NULL,
            icon TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0)""")
        # 只有分类表为空时才插入默认分类
        count = c.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if count == 0:
            defaults = [("螺丝","#3b82f6","🔩",0),("管材","#22c55e","🪠",1),
                        ("工具","#f97316","🔧",2),("电料","#eab308","⚡",3),
                        ("涂料","#a855f7","🪣",4),("其他","#64748b","📦",5)]
            for name,color,icon,order in defaults:
                c.execute("INSERT INTO categories(name,color,icon,sort_order) VALUES(?,?,?,?)",
                          (name,color,icon,order))

def _img_dir():
    d = os.path.join(os.path.dirname(_db()), "product_images")
    os.makedirs(d, exist_ok=True)
    return d

def db_cats():
    with sqlite3.connect(_db()) as c:
        rows = c.execute("SELECT name,color,icon FROM categories ORDER BY sort_order,id").fetchall()
    return rows  # [(name,color,icon), ...]

def db_cat_names():
    return [r[0] for r in db_cats()]

def db_cat_add(name, color, icon):
    with sqlite3.connect(_db()) as c:
        order = (c.execute("SELECT MAX(sort_order) FROM categories").fetchone()[0] or 0) + 1
        c.execute("INSERT INTO categories(name,color,icon,sort_order) VALUES(?,?,?,?)",(name,color,icon,order))

def db_cat_update(old_name, new_name, color, icon):
    with sqlite3.connect(_db()) as c:
        c.execute("UPDATE categories SET name=?,color=?,icon=? WHERE name=?",(new_name,color,icon,old_name))
        if old_name != new_name:
            c.execute("UPDATE products SET category=? WHERE category=?",(new_name,old_name))

def db_cat_reorder(names):
    """按 names 列表顺序更新 sort_order"""
    with sqlite3.connect(_db()) as c:
        for i, name in enumerate(names):
            c.execute("UPDATE categories SET sort_order=? WHERE name=?",(i,name))

def db_cat_delete(name):
    with sqlite3.connect(_db()) as c:
        c.execute("DELETE FROM categories WHERE name=?",(name,))
        c.execute("UPDATE products SET category='其他' WHERE category=?",(name,))

# ── 客户 CRUD ──
def db_customers():
    with sqlite3.connect(_db()) as c:
        return c.execute("SELECT id,name,address,phone FROM customers ORDER BY id").fetchall()

def db_customer_add(name, address, phone):
    with sqlite3.connect(_db()) as c:
        c.execute("INSERT INTO customers(name,address,phone) VALUES(?,?,?)",
                  (name, address, phone))

def db_customer_update(cid, name, address, phone):
    with sqlite3.connect(_db()) as c:
        c.execute("UPDATE customers SET name=?,address=?,phone=? WHERE id=?",
                  (name, address, phone, cid))

def db_customer_delete(cid):
    with sqlite3.connect(_db()) as c:
        c.execute("DELETE FROM customers WHERE id=?", (cid,))

def _build_where(kw, cat):
    sql, p = " WHERE 1=1", []
    if kw:
        sql += " AND (name LIKE ? OR spec LIKE ? OR remark LIKE ?)"
        p += [f"%{kw}%"] * 3
    if cat != "全部":
        sql += " AND category=?"; p.append(cat)
    return sql, p

def db_count(kw="", cat="全部") -> int:
    where, p = _build_where(kw, cat)
    with sqlite3.connect(_db()) as c:
        return c.execute("SELECT COUNT(*) FROM products" + where, p).fetchone()[0]

def db_all(kw="", cat="全部", limit=100, offset=0):
    where, p = _build_where(kw, cat)
    sql = ("SELECT id,name,category,purchase_price,price,size,location,remark,image_path,spec"
           " FROM products" + where + " ORDER BY sort_order ASC, id ASC LIMIT ? OFFSET ?")
    with sqlite3.connect(_db()) as c:
        return c.execute(sql, p + [limit, offset]).fetchall()

def db_get(pid):
    """按 id 精确查一条，避免全表扫描"""
    with sqlite3.connect(_db()) as c:
        return c.execute(
            "SELECT id,name,category,purchase_price,price,size,location,remark,image_path,spec"
            " FROM products WHERE id=?", (pid,)).fetchone()

def db_insert(n,c,pp,p,s,l,r,img="",sp=""):
    with sqlite3.connect(_db()) as db:
        max_ord = db.execute("SELECT IFNULL(MAX(sort_order),0) FROM products").fetchone()[0]
        db.execute(
            "INSERT INTO products(name,category,purchase_price,price,size,location,remark,image_path,spec,sort_order) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (n,c,pp,p,s,l,r,img,sp,max_ord+1))

def db_update(pid,n,c,pp,p,s,l,r,img="",sp=""):
    with sqlite3.connect(_db()) as db: db.execute(
        "UPDATE products SET name=?,category=?,purchase_price=?,price=?,size=?,location=?,remark=?,image_path=?,spec=? WHERE id=?",(n,c,pp,p,s,l,r,img,sp,pid))

def db_copy_after(pid):
    """复制 pid 对应的商品，插入到原商品正下方"""
    with sqlite3.connect(_db()) as db:
        row = db.execute(
            "SELECT name,category,purchase_price,price,size,location,remark,image_path,spec,sort_order FROM products WHERE id=?",
            (pid,)).fetchone()
        if not row: return
        n,c,pp,p,s,l,r,img,sp,orig_ord = row
        db.execute("UPDATE products SET sort_order=sort_order+1 WHERE sort_order>?", (orig_ord,))
        db.execute(
            "INSERT INTO products(name,category,purchase_price,price,size,location,remark,image_path,spec,sort_order) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (n,c,pp,p,s,l,r,img,sp,orig_ord+1))

def db_delete(pid):
    with sqlite3.connect(_db()) as db: db.execute("DELETE FROM products WHERE id=?",(pid,))

def db_weekly_additions():
    """过去 7 天每天新增商品数，缺失的天填 0"""
    from datetime import date, timedelta
    today = date.today()
    with sqlite3.connect(_db()) as c:
        rows = c.execute("""
            SELECT DATE(created_at) as day, COUNT(*)
            FROM products
            WHERE DATE(created_at) >= DATE('now','-6 days')
            GROUP BY day ORDER BY day
        """).fetchall()
    day_map = dict(rows)
    result = []
    for i in range(6, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        result.append((d, day_map.get(d, 0)))
    return result

def db_monthly_additions():
    """过去 12 个月每月新增商品数，缺失的月填 0"""
    from datetime import date
    today = date.today()
    months = []
    for i in range(11, -1, -1):
        y = today.year - (1 if today.month - 1 - i < 0 else 0)
        m = (today.month - 1 - i) % 12 + 1
        months.append(f"{y:04d}-{m:02d}")
    with sqlite3.connect(_db()) as c:
        rows = c.execute("""
            SELECT STRFTIME('%Y-%m', created_at) as mo, COUNT(*)
            FROM products
            WHERE STRFTIME('%Y-%m', created_at) >= ?
            GROUP BY mo ORDER BY mo
        """, (months[0],)).fetchall()
    day_map = dict(rows)
    return [(mo, day_map.get(mo, 0)) for mo in months]

def db_yearly_additions():
    """各年份新增商品数（有记录的年份 + 当年，缺失填 0）"""
    from datetime import date
    this_year = str(date.today().year)
    with sqlite3.connect(_db()) as c:
        rows = c.execute("""
            SELECT STRFTIME('%Y', created_at) as yr, COUNT(*)
            FROM products
            GROUP BY yr ORDER BY yr
        """).fetchall()
    if not rows:
        return [(this_year, 0)]
    yr_map = dict(rows)
    start = int(rows[0][0])
    end   = int(this_year)
    result = []
    for y in range(start, end + 1):
        result.append((str(y), yr_map.get(str(y), 0)))
    return result

PRINT_CART: list = []  # [{pid, name, spec, price, qty, unit}]

def db_stats():
    with sqlite3.connect(_db()) as c:
        tot,val = c.execute(
            "SELECT COUNT(*),IFNULL(SUM(price),0) FROM products").fetchone()
        cats = c.execute(
            "SELECT category,COUNT(*),IFNULL(SUM(price),0) FROM products GROUP BY category"
        ).fetchall()
    return tot,val,cats

# ══════════════════════════════════════════════════════════════════════
#  全局 QSS（全部颜色从 T 读取）
# ══════════════════════════════════════════════════════════════════════
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
#nav_tab {{ background:transparent; border:none; color:{t('text_mid')};
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
QTableWidget::item:selected {{ background:{t('sel')}; border-bottom:1px solid {t('accent')}; }}
QTableWidget::item:selected:!active {{ background:{t('sel')}; border-bottom:1px solid {t('accent')}; }}
QTableWidget::item:alternate:selected {{ background:{t('sel')}; border-bottom:1px solid {t('accent')}; }}
QTableWidget::item:alternate:selected:!active {{ background:{t('sel')}; border-bottom:1px solid {t('accent')}; }}
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

# ══════════════════════════════════════════════════════════════════════
#  通用工具
# ══════════════════════════════════════════════════════════════════════
class RedTextDelegate(QStyledItemDelegate):
    """强制文字显示为红色，不受选中状态影响"""
    def paint(self, painter, option, index):
        from PyQt6.QtWidgets import QStyle
        opt = option.__class__(option)
        self.initStyleOption(opt, index)
        opt.palette.setColor(QPalette.ColorRole.Text, QColor("#ef4444"))
        opt.palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ef4444"))
        opt.widget.style().drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)


def add_shadow(w, blur=24, alpha=60):
    e = QGraphicsDropShadowEffect()
    e.setBlurRadius(blur); e.setOffset(0, 4)
    e.setColor(QColor(0, 0, 0, alpha))
    w.setGraphicsEffect(e)


# ──────────────────────────────────────────────────────────────────────
#  Toast 浮动提示（仿 Android / iOS 风格）
# ──────────────────────────────────────────────────────────────────────
class Toast(QWidget):
    """
    轻量 Toast：在父窗口正中浮现，停留后淡出消失。
    用法：Toast.show_msg(parent_window, "提示文字")
    """

    def __init__(self, parent, msg: str):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.Tool |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 透明度效果
        self._eff = QGraphicsOpacityEffect(self)
        self._eff.setOpacity(0.0)
        self.setGraphicsEffect(self._eff)

        # 外层布局（为阴影留边距）
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)

        # 圆角框容器
        box = QFrame()
        box.setFixedHeight(44)
        box.setStyleSheet(f"""
            QFrame {{
                background: {t('accent')};
                border-radius: 15px;
            }}
        """)
        sh = QGraphicsDropShadowEffect()
        sh.setBlurRadius(24); sh.setOffset(0, 4)
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

        # 淡入 250ms
        self._anim_in = QPropertyAnimation(self._eff, b"opacity", self)
        self._anim_in.setDuration(250)
        self._anim_in.setStartValue(0.0)
        self._anim_in.setEndValue(1.0)
        self._anim_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim_in.start()

        # stay_ms 后开始淡出
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

def icon_badge(icon:str, bg:str, size:int=44, radius:int=12) -> QLabel:
    w = QLabel(icon)
    w.setFixedSize(size, size)
    w.setAlignment(Qt.AlignmentFlag.AlignCenter)
    w.setStyleSheet(f"QLabel{{background:{bg};border-radius:{radius}px;"
                    f"font-size:{size//2}px;color:#ffffff;}}")
    return w

# ══════════════════════════════════════════════════════════════════════
#  自定义下拉选择框（圆角 + hover 高亮）
# ══════════════════════════════════════════════════════════════════════
class DropdownSelect(QWidget):
    """外观是圆角输入框，点击弹出可hover高亮的列表"""
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

        # 外层容器，用来实现圆角边框 + 右侧箭头叠加
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
        self._arrow.setStyleSheet(f"color: {t('text_sub')}; font-size: 14px; background: transparent; border: none;")
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

        # 滚动区域
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
        # 最多显示8个，每个36px + 2px间距，加上上下padding 12px
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

def cat_badge(cat:str) -> QLabel:
    color = _color_for(cat)
    r,g,b = int(color[1:3],16), int(color[3:5],16), int(color[5:7],16)
    alpha = t('badge_alpha')
    bg = f"rgba({r},{g},{b},{alpha})"
    w = QLabel(cat)
    w.setAlignment(Qt.AlignmentFlag.AlignCenter)
    w.setStyleSheet(f"QLabel{{background:{bg};color:{color};border-radius:6px;"
                    f"padding:2px 10px;font-size:12px;font-weight:600;}}")
    return w

# ══════════════════════════════════════════════════════════════════════
#  统计卡片（动态样式）
# ══════════════════════════════════════════════════════════════════════
class StatCard(QFrame):
    def __init__(self, icon, ic_key, label, value_text, color, parent=None):
        super().__init__(parent)
        self._icon = icon; self._ic_key = ic_key
        self._label = label; self._color = color
        self.setObjectName("card")
        self.setMinimumHeight(96)
        add_shadow(self, 24, 40 if IS_DARK else 12)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(20,0,20,0); lay.setSpacing(16)

        self._badge = icon_badge(icon, t(ic_key), 48, 14)
        lay.addWidget(self._badge)

        col = QVBoxLayout(); col.setSpacing(4)
        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(f"color:{t('text_sub')};font-size:12px;")
        self._val = QLabel(value_text)
        self._val.setStyleSheet(f"color:{color};font-size:22px;font-weight:800;")
        col.addWidget(self._lbl); col.addWidget(self._val)
        lay.addLayout(col); lay.addStretch()

    def set_value(self, v): self._val.setText(v)

    def refresh_theme(self):
        self._badge.setStyleSheet(f"QLabel{{background:{t(self._ic_key)};border-radius:14px;"
                                  f"font-size:24px;color:#ffffff;}}")
        self._lbl.setStyleSheet(f"color:{t('text_sub')};font-size:12px;")
        self._val.setStyleSheet(f"color:{self._color};font-size:22px;font-weight:800;")
        add_shadow(self, 24, 40 if IS_DARK else 12)

# ══════════════════════════════════════════════════════════════════════
#  自定义提示弹窗（替换 QMessageBox）
# ══════════════════════════════════════════════════════════════════════
class MsgBox(QDialog):
    """
    type_: "info" | "warning" | "question" | "success"
    返回 True 表示确认
    """
    ICONS = {"info":"ℹ️", "warning":"⚠️", "question":"🗑️", "success":"✅", "error":"❌"}
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
            self.move(p.x()+(p.width()-self.width())//2,
                      p.y()+(p.height()-self.height())//2)

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

        # 顶部色条
        bar = QWidget()
        bar.setFixedHeight(4)
        bar.setStyleSheet(f"background:{t('accent')}; border-radius:16px 16px 0 0;")
        cl.addWidget(bar)

        # 内容区
        body = QWidget()
        body.setStyleSheet(f"background:{bg}; border-radius:0 0 16px 16px;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(28, 24, 28, 24)
        bl.setSpacing(16)

        # 图标 + 标题行
        title_row = QHBoxLayout(); title_row.setSpacing(14)
        ic_lbl = QLabel(icon)
        ic_lbl.setStyleSheet(f"font-size:28px; background:transparent;")
        ic_lbl.setFixedSize(40, 40)
        ic_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size:16px; font-weight:700; color:{t('text')}; background:transparent;")
        title_row.addWidget(ic_lbl)
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        bl.addLayout(title_row)

        # 分割线
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color:{t('border')}; background:{t('border')}; max-height:1px;")
        bl.addWidget(line)

        # 消息文本
        msg_lbl = QLabel(msg)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(f"font-size:13px; color:{t('text_mid')}; line-height:1.6; background:transparent;")
        msg_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        bl.addWidget(msg_lbl)

        # 按钮区
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
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

        # 自适应高度
        self.adjustSize()

    def _on_confirm(self):
        self._confirmed = True
        self.accept()

    @staticmethod
    def info(parent, title, msg):
        d = MsgBox(parent, "info", title, msg); d.exec()

    @staticmethod
    def warning(parent, title, msg):
        d = MsgBox(parent, "warning", title, msg); d.exec()

    @staticmethod
    def confirm(parent, title, msg, confirm_text="确定", cancel_text="取消"):
        """弹出确认对话框，返回 True/False"""
        d = MsgBox(parent, "question", title, msg)
        # 找到按钮并修改文字
        for btn in d.findChildren(QPushButton):
            if btn.text() == "确认删除":
                btn.setText(confirm_text)
            elif btn.text() == "取消":
                btn.setText(cancel_text)
        d.exec()
        return d._confirmed

    @staticmethod
    def success(parent, title, msg):
        d = MsgBox(parent, "success", title, msg); d.exec()


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

# ══════════════════════════════════════════════════════════════════════
#  管理分类弹窗
# ══════════════════════════════════════════════════════════════════════
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

# ══════════════════════════════════════════════════════════════════════
#  商品管理页
# ══════════════════════════════════════════════════════════════════════
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
        h1.setStyleSheet(f"font-size:17px;font-weight:700;color:{t('text')};")
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
        dlg.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        root = QVBoxLayout(dlg); root.setContentsMargins(8,8,8,8)
        container = QFrame(); container.setObjectName("img_container")
        container.setStyleSheet(f"""QFrame{{background:{'#18181c' if IS_DARK else '#f2f2f5'};
            border-radius:16px;border:none;}}""")
        add_shadow(container, 32, 80 if IS_DARK else 30)
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

# ══════════════════════════════════════════════════════════════════════
#  数据统计页
# ══════════════════════════════════════════════════════════════════════
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
            pass

    def _paint(self):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if not self._data:
            return

        pad_l, pad_r, pad_t, pad_b = 36, 16, 20, 28
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

        steps = 4
        for i in range(steps + 1):
            y = pad_t + int(chart_h * (steps - i) / steps)
            painter.setPen(mid_c)
            painter.drawText(QRect(0, y - 8, pad_l - 5, 16),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             str(int(max_v * i / steps)))
            painter.setPen(QPen(bdr_c, 1, Qt.PenStyle.DashLine))
            painter.drawLine(pad_l, y, w - pad_r, y)

        painter.setPen(mid_c)
        for i, lbl in enumerate(labels):
            x = pad_l + int(i * chart_w / (n - 1)) if n > 1 else pad_l + chart_w // 2
            painter.drawText(QRect(x - 20, h - pad_b + 4, 40, 18),
                             Qt.AlignmentFlag.AlignCenter, lbl)

        pts = []
        for i, v in enumerate(values):
            x = pad_l + int(i * chart_w / (n - 1)) if n > 1 else pad_l + chart_w // 2
            y = pad_t + chart_h - int(v / max_v * chart_h)
            pts.append(QPointF(x, y))

        path = QPainterPath()
        path.moveTo(pts[0].x(), pad_t + chart_h)
        for p in pts:
            path.lineTo(p)
        path.lineTo(pts[-1].x(), pad_t + chart_h)
        path.closeSubpath()
        fill = QColor(accent); fill.setAlpha(28)
        painter.fillPath(path, fill)

        painter.setPen(QPen(accent, 2.5))
        for i in range(len(pts) - 1):
            painter.drawLine(pts[i], pts[i + 1])

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


# ══════════════════════════════════════════════════════════════════════
#  客户对话框
# ══════════════════════════════════════════════════════════════════════
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
        h1.setStyleSheet(f"font-size:17px;font-weight:700;color:{t('text')};")
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
            self.table.setItem(r, 0, QTableWidgetItem(row[1] or ""))
            self.table.setItem(r, 1, QTableWidgetItem(row[2] or ""))
            self.table.setItem(r, 2, QTableWidgetItem(row[3] or ""))
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


# ══════════════════════════════════════════════════════════════════════
#  账单打印页
# ══════════════════════════════════════════════════════════════════════
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
        h1.setStyleSheet(f"font-size:17px;font-weight:700;color:{t('text')};")
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


# ══════════════════════════════════════════════════════════════════════
#  主窗口
# ══════════════════════════════════════════════════════════════════════
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

        self.theme_btn = QPushButton("🌙  夜间模式")
        self.theme_btn.setObjectName("theme_btn"); self.theme_btn.setFixedHeight(34)
        self.theme_btn.clicked.connect(self._toggle_theme)
        nl.addWidget(self.theme_btn); nl.addSpacing(16)
        self._ver_lbl = QLabel(f"v{APP_VERSION}")
        self._ver_lbl.setStyleSheet(f"color:{t('text_sub')};font-size:11px;cursor:pointer;")
        self._ver_lbl.setToolTip("点击检查更新")
        self._ver_lbl.mousePressEvent = lambda _: self._check_update()
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
        self._checker = UpdateChecker(mode="check", url=UPDATE_CHECK_URL)
        self._checker.checked.connect(self._on_update_checked)
        self._checker.failed.connect(lambda _: None)  # 静默失败
        self._checker.start()

    def _on_update_checked(self, info):
        remote_ver = info.get("version", "0.0.0")
        if _version_tuple(remote_ver) > _version_tuple(APP_VERSION):
            dlg = UpdateDialog(info, self)
            dlg.exec()

    def _toggle_theme(self):
        global IS_DARK, T
        IS_DARK = not IS_DARK
        T.update(DARK if IS_DARK else LIGHT)
        self.theme_btn.setText("🌙  夜间模式" if IS_DARK else "☀️  日间模式")
        self._rebuild_pages()
        self.apply_theme()

    def _rebuild_pages(self):
        """销毁并重建页面，确保所有内联样式用新主题重新渲染"""
        cur = self._cur_tab
        search_txt = self.page_prod.search.text()
        cur_cat    = self.page_prod._cur_cat

        self.stack.removeWidget(self.page_prod)
        self.stack.removeWidget(self.page_print)
        self.stack.removeWidget(self.page_cust)
        self.stack.removeWidget(self.page_stats)
        self.page_prod.deleteLater()
        self.page_print.deleteLater()
        self.page_cust.deleteLater()
        self.page_stats.deleteLater()

        self.page_prod  = ProductPage()
        self.page_print = PrintPage()
        self.page_cust  = CustomerPage()
        self.page_stats = StatsPage()
        self.stack.addWidget(self.page_prod)
        self.stack.addWidget(self.page_print)
        self.stack.addWidget(self.page_cust)
        self.stack.addWidget(self.page_stats)
        self.page_prod.status_sig.connect(self.status_lbl.setText)
        self.page_prod.data_changed.connect(self.page_stats.refresh)
        self.page_prod.print_changed.connect(self.page_print.refresh)
        self.page_print.status_sig.connect(self.status_lbl.setText)
        self.page_cust.status_sig.connect(self.status_lbl.setText)

        # 恢复搜索和分类状态
        self.page_prod.search.setText(search_txt)
        self.page_prod._set_cat(cur_cat)
        self._switch_tab(cur)

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

    init_db()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
