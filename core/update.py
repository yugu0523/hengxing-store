"""自动更新 — UpdateChecker (QThread) + UpdateDialog (QDialog)"""
import sys, os, json, tempfile, subprocess

from PyQt6.QtCore import QThread, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QProgressBar, QApplication,
)

from core.config import get_app_dir, APP_VERSION
from ui.theme import t, IS_DARK
from ui.theme import make_qss as _make_qss  # 用于 dialogs 重新应用样式


def _version_tuple(v):
    return tuple(int(x) for x in v.split("."))


def _curl(args, timeout=300):
    r = subprocess.run(
        ["curl", "-sL", "--max-time", str(timeout)] + args,
        capture_output=True, timeout=timeout + 10,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    if r.returncode != 0:
        raise RuntimeError(f"curl exit {r.returncode}")
    return r.stdout


class UpdateChecker(QThread):
    checked = pyqtSignal(dict)
    progress = pyqtSignal(int)
    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)

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
        app_dir = get_app_dir()
        test_file = os.path.join(app_dir, "version_test.json")
        if os.path.exists(test_file):
            try:
                with open(test_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "version" in data:
                    data["_test_mode"] = True
                    if not data.get("download_url"):
                        data["download_url"] = ""
                    self.checked.emit(data)
                    return
            except Exception:
                pass

        import base64
        ts = str(int(__import__("time").time()))
        urls = [
            "https://api.github.com/repos/yugu0523/hengxing-store/contents/version.json?t=" + ts,
            self.url + ("&" if "?" in self.url else "?") + "t=" + ts,
            "https://cdn.jsdelivr.net/gh/yugu0523/hengxing-store@master/version.json?t=" + ts,
        ]
        for url in urls:
            try:
                raw = _curl(["--connect-timeout", "10", url], timeout=15)
                if not raw:
                    continue
                text = raw.decode("utf-8", errors="replace")
                data = json.loads(text)
                if "content" in data and "encoding" in data:
                    content_b64 = data["content"].replace("\n", "")
                    text = base64.b64decode(content_b64).decode("utf-8")
                    data = json.loads(text)
                if "version" in data:
                    self.checked.emit(data)
                    return
            except Exception:
                continue
        self.failed.emit("所有更新源均不可达")

    def _do_download(self):
        tmp = os.path.join(tempfile.gettempdir(), "hengxing_update.exe")
        for f in [tmp] + [tmp + f".part{i}" for i in range(4)]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except OSError:
                pass

        url = self.url
        last_err = ""

        dl_urls = [url]
        if "github.com" in url and "/releases/download/" in url:
            import re
            m = re.search(r'/releases/download/([^/]+)/([^/]+)$', url)
            if m:
                tag, fname = m.group(1), m.group(2)
                dl_urls.append(
                    f"https://cdn.jsdelivr.net/gh/yugu0523/hengxing-store@{tag}/{fname}"
                )

        for attempt in range(3):
            if attempt > 0:
                __import__("time").sleep(2 * attempt)

            dl_url = dl_urls[min(attempt, len(dl_urls) - 1)]

            try:
                total = 0
                r = subprocess.run(
                    ["curl", "-sL", "-I", "--connect-timeout", "15", "--max-time", "15", dl_url],
                    capture_output=True, timeout=20,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if r.returncode == 0:
                    for line in r.stdout.decode("utf-8", errors="replace").splitlines():
                        if line.lower().startswith("content-length:"):
                            total = int(line.split(":", 1)[1].strip())
                            break

                parts = [tmp + f".part{i}" for i in range(4)]
                procs = []
                if total > 0:
                    chunk = total // 4
                    for i in range(4):
                        start = i * chunk
                        end = total - 1 if i == 3 else (i + 1) * chunk - 1
                        p = subprocess.Popen(
                            ["curl", "-sL", "--connect-timeout", "30", "--max-time", "600",
                             "-r", f"{start}-{end}", "-o", parts[i], dl_url],
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                        procs.append(p)
                else:
                    p = subprocess.Popen(
                        ["curl", "-sL", "--connect-timeout", "30", "--max-time", "600",
                         "-o", tmp, dl_url],
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    procs.append(p)

                while any(p.poll() is None for p in procs):
                    downloaded = 0
                    for part in parts:
                        try:
                            downloaded += os.path.getsize(part)
                        except OSError:
                            pass
                    if total > 0:
                        self.progress.emit(min(int(downloaded * 100 / total), 99))
                    __import__("time").sleep(0.3)

                if any(p.returncode != 0 for p in procs):
                    raise RuntimeError(f"curl 进程异常退出 (返回码: {[p.returncode for p in procs]})")

                if total > 0:
                    with open(tmp, "wb") as out:
                        for part in parts:
                            with open(part, "rb") as inp:
                                out.write(inp.read())
                            os.remove(part)

                if not os.path.exists(tmp) or os.path.getsize(tmp) == 0:
                    raise RuntimeError("下载完成但文件为空")

                self.progress.emit(100)
                self.finished_ok.emit(tmp)
                return

            except Exception as e:
                last_err = f"{dl_url[:60]}... → {e}"
                for f in [tmp] + [tmp + f".part{i}" for i in range(4)]:
                    try:
                        if os.path.exists(f):
                            os.remove(f)
                    except OSError:
                        pass
                continue

        self.failed.emit(last_err or "下载失败：所有 URL 均不可达")


class UpdateDialog(QDialog):
    def __init__(self, info, parent=None, test_mode=False):
        super().__init__(parent)
        self.setWindowTitle("发现新版本")
        self.setMinimumSize(440, 320)
        self.resize(480, 400)
        self._info = info
        self._test_mode = test_mode
        self._downloader = None
        self._sim_timer = None
        self._sim_pct = 0
        self._build_ui()
        self._apply_theme()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(16)

        title_row = QHBoxLayout()
        self._title_lbl = QLabel("发现新版本")
        self._title_lbl.setStyleSheet("font-size:20px;font-weight:700;")
        title_row.addWidget(self._title_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)

        ver = self._info.get("version", "")
        self._ver_lbl = QLabel(f"v{ver} 现已可用")
        self._ver_lbl.setStyleSheet("font-size:28px;font-weight:700;")
        self._ver_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._ver_lbl)

        notes_text = self._info.get("notes", "").strip()
        if notes_text:
            card = QFrame()
            card.setObjectName("updateNotesCard")
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(16, 14, 16, 14)
            card_lay.setSpacing(6)
            notes_header = QLabel("更新内容")
            notes_header.setStyleSheet("font-size:13px;font-weight:600;")
            card_lay.addWidget(notes_header)
            notes_body = QLabel(notes_text)
            notes_body.setWordWrap(True)
            notes_body.setStyleSheet("font-size:13px;")
            card_lay.addWidget(notes_body)
            lay.addWidget(card)
            self._notes_card = card
        else:
            self._notes_card = None

        lay.addStretch()

        self._progress_lbl = QLabel("")
        self._progress_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._progress_lbl.setStyleSheet("font-size:12px;")
        self._progress_lbl.hide()
        lay.addWidget(self._progress_lbl)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setValue(0)
        self._progress_bar.hide()
        lay.addWidget(self._progress_bar)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self._skip_btn = QPushButton("跳过此版本")
        self._skip_btn.setObjectName("updateSkipBtn")
        self._skip_btn.setFixedHeight(38)
        self._skip_btn.clicked.connect(self.reject)
        self._update_btn = QPushButton("立即更新")
        self._update_btn.setObjectName("updateBtn")
        self._update_btn.setFixedHeight(38)
        self._update_btn.clicked.connect(self._start_update)
        btn_row.addWidget(self._skip_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._update_btn)
        lay.addLayout(btn_row)

    def _apply_theme(self):
        bg = t("bg")
        surface = t("surface")
        card_bg = t("card2")
        border = t("border")
        text_color = t("text")
        text_sub = t("text_sub")
        accent = t("accent")
        accent_h = t("accent_h")

        self.setStyleSheet(f"""
            UpdateDialog {{
                background: {surface};
            }}
            #updateNotesCard {{
                background: {card_bg};
                border: 1px solid {border};
                border-radius: 10px;
            }}
            #updateSkipBtn {{
                background: {t('btn2_bg')};
                color: {t('btn2_text')};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 8px 22px;
                font-size: 13px;
            }}
            #updateSkipBtn:hover {{
                background: {t('btn2_hover')};
            }}
            #updateBtn {{
                background: {accent};
                color: white;
                border: 0;
                border-radius: 8px;
                padding: 8px 28px;
                font-size: 13px;
                font-weight: 600;
            }}
            #updateBtn:hover {{
                background: {accent_h};
            }}
            #updateBtn:disabled {{
                background: {border};
                color: {text_sub};
            }}
        """)

        self._title_lbl.setStyleSheet(f"font-size:20px;font-weight:700;color:{text_color};")
        self._ver_lbl.setStyleSheet(f"font-size:28px;font-weight:700;color:{accent};")
        self._progress_lbl.setStyleSheet(f"font-size:12px;color:{text_sub};")
        self._progress_bar.setStyleSheet(f"""
            QProgressBar{{
                background:{card_bg};
                border:0;
                border-radius:3px;
            }}
            QProgressBar::chunk{{
                background:{accent};
                border-radius:3px;
            }}
        """)

    def _start_update(self):
        self._skip_btn.setEnabled(False)
        self._update_btn.setEnabled(False)
        self._update_btn.setText("下载中...")
        self._progress_bar.show()
        self._progress_lbl.show()
        self._progress_bar.setValue(0)

        url = self._info.get("download_url", "")
        if self._test_mode or not url:
            self._sim_pct = 0
            self._sim_timer = QTimer()
            self._sim_timer.timeout.connect(self._sim_tick)
            self._sim_timer.start(30)
            return

        self._downloader = UpdateChecker(mode="download", url=url)
        self._downloader.progress.connect(self._on_progress)
        self._downloader.finished_ok.connect(self._on_done)
        self._downloader.failed.connect(self._on_fail)
        self._downloader.start()

    def _sim_tick(self):
        self._sim_pct += 2
        if self._sim_pct >= 100:
            self._sim_pct = 100
            self._sim_timer.stop()
        self._progress_bar.setValue(self._sim_pct)
        self._progress_lbl.setText(f"已下载 {self._sim_pct}%")
        if self._sim_pct >= 100:
            self._progress_lbl.setText("下载完成，正在替换...")
            QTimer.singleShot(500, self._sim_done)

    def _sim_done(self):
        self._apply_update_static(
            os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)
        )

    def _on_progress(self, pct):
        self._progress_bar.setValue(pct)
        self._progress_lbl.setText(f"已下载 {pct}%")

    def _on_done(self, tmp_path):
        self._tmp_path = tmp_path
        self._progress_bar.setValue(100)
        self._progress_lbl.setText("下载完成，请重启应用以完成更新")
        self._update_btn.setEnabled(True)
        self._update_btn.setText("立即重启")
        try:
            self._update_btn.clicked.disconnect()
        except Exception:
            pass
        self._update_btn.clicked.connect(self._do_restart)
        self._skip_btn.setEnabled(True)
        self._skip_btn.setText("稍后重启")
        try:
            self._skip_btn.clicked.disconnect()
        except Exception:
            pass
        self._skip_btn.clicked.connect(self.reject)
        self.raise_()
        self.activateWindow()

    def _on_fail(self, err):
        self._sim_timer = None
        self._skip_btn.setEnabled(True)
        self._update_btn.setEnabled(True)
        self._update_btn.setText("重试")
        self._progress_lbl.setText(f"下载失败: {err}")
        self._progress_bar.setStyleSheet(f"""
            QProgressBar{{background:{t('card2')};border:0;border-radius:3px;}}
            QProgressBar::chunk{{background:{t('danger')};border-radius:3px;}}
        """)

    def _do_restart(self):
        self._apply_update_static(self._tmp_path)

    @staticmethod
    def _apply_update_static(new_exe):
        current_exe = os.path.abspath(
            sys.executable if getattr(sys, "frozen", False) else __file__)
        current_name = os.path.basename(current_exe)
        current_pid = os.getpid()
        bat = os.path.join(tempfile.gettempdir(), "hengxing_update.bat")
        with open(bat, "w", encoding="gbk") as f:
            f.write("@echo off\n")
            f.write("echo 正在更新恒星五金记账系统...\n")
            f.write("timeout /t 2 /nobreak >nul\n")
            f.write(f"taskkill /f /im \"{current_name}\" >nul 2>&1\n")
            f.write("timeout /t 1 /nobreak >nul\n")
            f.write(f"taskkill /f /pid {current_pid} >nul 2>&1\n")
            f.write("timeout /t 1 /nobreak >nul\n")
            f.write(f"copy /y \"{new_exe}\" \"{current_exe}\" >nul\n")
            f.write("if %errorlevel% neq 0 (\n")
            f.write("    echo 更新失败！请手动替换文件。\n")
            f.write("    pause\n")
            f.write("    exit /b 1\n")
            f.write(")\n")
            f.write(f"start \"\" \"{current_exe}\"\n")
            f.write("del \"%~f0\"\n")
        subprocess.Popen(["cmd", "/c", bat],
                         creationflags=subprocess.CREATE_NO_WINDOW,
                         close_fds=True)
        QApplication.quit()
