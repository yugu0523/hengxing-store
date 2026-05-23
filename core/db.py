"""数据库层 — SQLite CRUD 操作、打印清单、图片缓存"""
import sys, os, sqlite3

from core.config import get_app_dir

# ── 全局状态 ──
_IMG_CACHE: dict = {}               # fname -> QPixmap(40x40缩略图)
_CHECKMARK_PATH: str = ""
PRINT_CART: list = []               # [{pid, name, spec, price, qty, unit}]


def _db():
    return os.path.join(get_app_dir(), "hardware_store.db")


def _img_dir():
    d = os.path.join(os.path.dirname(_db()), "product_images")
    os.makedirs(d, exist_ok=True)
    return d


def _ensure_arrow_icons() -> tuple:
    """生成上下箭头 SVG，返回 (up_path, down_path) 供 QSS url() 使用"""
    base = get_app_dir()
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
    base = get_app_dir()
    path = os.path.join(base, "chk.svg")
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 14 14">'
           '<polyline points="2,8 6,12 12,2" stroke="white" stroke-width="2.2"'
           ' fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    _CHECKMARK_PATH = path.replace("\\", "/")
    return _CHECKMARK_PATH


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
        c.execute("UPDATE products SET sort_order = id WHERE sort_order = 0")
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
        count = c.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if count == 0:
            defaults = [("螺丝", "#3b82f6", "🔩", 0), ("管材", "#22c55e", "🪠", 1),
                        ("工具", "#f97316", "🔧", 2), ("电料", "#eab308", "⚡", 3),
                        ("涂料", "#a855f7", "🪣", 4), ("其他", "#64748b", "📦", 5)]
            for name, color, icon, order in defaults:
                c.execute("INSERT INTO categories(name,color,icon,sort_order) VALUES(?,?,?,?)",
                          (name, color, icon, order))


# ── 分类 CRUD ──
def db_cats():
    with sqlite3.connect(_db()) as c:
        rows = c.execute("SELECT name,color,icon FROM categories ORDER BY sort_order,id").fetchall()
    return rows


def db_cat_names():
    return [r[0] for r in db_cats()]


def db_cat_add(name, color, icon):
    with sqlite3.connect(_db()) as c:
        order = (c.execute("SELECT MAX(sort_order) FROM categories").fetchone()[0] or 0) + 1
        c.execute("INSERT INTO categories(name,color,icon,sort_order) VALUES(?,?,?,?)",
                  (name, color, icon, order))


def db_cat_update(old_name, new_name, color, icon):
    with sqlite3.connect(_db()) as c:
        c.execute("UPDATE categories SET name=?,color=?,icon=? WHERE name=?",
                  (new_name, color, icon, old_name))
        if old_name != new_name:
            c.execute("UPDATE products SET category=? WHERE category=?", (new_name, old_name))


def db_cat_reorder(names):
    with sqlite3.connect(_db()) as c:
        for i, name in enumerate(names):
            c.execute("UPDATE categories SET sort_order=? WHERE name=?", (i, name))


def db_cat_delete(name):
    with sqlite3.connect(_db()) as c:
        c.execute("DELETE FROM categories WHERE name=?", (name,))
        c.execute("UPDATE products SET category='其他' WHERE category=?", (name,))


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


# ── 商品 CRUD ──
def _build_where(kw, cat):
    sql, p = " WHERE 1=1", []
    if kw:
        sql += " AND (name LIKE ? OR spec LIKE ? OR remark LIKE ?)"
        p += [f"%{kw}%"] * 3
    if cat != "全部":
        sql += " AND category=?"
        p.append(cat)
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
    with sqlite3.connect(_db()) as c:
        return c.execute(
            "SELECT id,name,category,purchase_price,price,size,location,remark,image_path,spec"
            " FROM products WHERE id=?", (pid,)).fetchone()


def db_insert(n, c, pp, p, s, l, r, img="", sp=""):
    with sqlite3.connect(_db()) as db:
        max_ord = db.execute("SELECT IFNULL(MAX(sort_order),0) FROM products").fetchone()[0]
        db.execute(
            "INSERT INTO products(name,category,purchase_price,price,size,location,remark,image_path,spec,sort_order) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (n, c, pp, p, s, l, r, img, sp, max_ord + 1))


def db_update(pid, n, c, pp, p, s, l, r, img="", sp=""):
    with sqlite3.connect(_db()) as db:
        db.execute(
            "UPDATE products SET name=?,category=?,purchase_price=?,price=?,size=?,location=?,remark=?,image_path=?,spec=? WHERE id=?",
            (n, c, pp, p, s, l, r, img, sp, pid))


def db_copy_after(pid):
    with sqlite3.connect(_db()) as db:
        row = db.execute(
            "SELECT name,category,purchase_price,price,size,location,remark,image_path,spec,sort_order FROM products WHERE id=?",
            (pid,)).fetchone()
        if not row:
            return
        n, c, pp, p, s, l, r, img, sp, orig_ord = row
        db.execute("UPDATE products SET sort_order=sort_order+1 WHERE sort_order>?", (orig_ord,))
        db.execute(
            "INSERT INTO products(name,category,purchase_price,price,size,location,remark,image_path,spec,sort_order) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (n, c, pp, p, s, l, r, img, sp, orig_ord + 1))


def db_delete(pid):
    with sqlite3.connect(_db()) as db:
        db.execute("DELETE FROM products WHERE id=?", (pid,))


# ── 统计 ──
def db_weekly_additions():
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
    end = int(this_year)
    result = []
    for y in range(start, end + 1):
        result.append((str(y), yr_map.get(str(y), 0)))
    return result


def db_stats():
    with sqlite3.connect(_db()) as c:
        tot, val = c.execute(
            "SELECT COUNT(*),IFNULL(SUM(price),0) FROM products").fetchone()
        cats = c.execute(
            "SELECT category,COUNT(*),IFNULL(SUM(price),0) FROM products GROUP BY category"
        ).fetchall()
    return tot, val, cats
