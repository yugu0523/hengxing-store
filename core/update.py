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
    return tuple(int(x) for x in v.replace(",", ".").split("."))


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

    @staticmethod
    def _get_content_length(url):
        """检测文件大小，用 curl -I + -A 自定义 User-Agent。返回 0 表示无法获取。"""
        # 方法 1：curl HEAD（默认 User-Agent，部分 CDN 不拒绝）
        try:
            r = subprocess.run(
                ["curl", "-sL", "-I", "--connect-timeout", "10", "--max-time", "10", url],
                capture_output=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if r.returncode == 0:
                for line in r.stdout.decode("utf-8", errors="replace").splitlines():
                    if line.lower().startswith("content-length:"):
                        return int(line.split(":", 1)[1].strip())
        except Exception:
            pass

        # 方法 2：curl HEAD + 自定义 UA（GitHub 偶尔拒绝默认 curl UA）
        try:
            r = subprocess.run(
                ["curl", "-sL", "-I",
                 "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                 "--connect-timeout", "10", "--max-time", "10", url],
                capture_output=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if r.returncode == 0:
                for line in r.stdout.decode("utf-8", errors="replace").splitlines():
                    if line.lower().startswith("content-length:"):
                        return int(line.split(":", 1)[1].strip())
        except Exception:
            pass

        return 0

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

        # 预检：HEAD 请求确认文件存在
        try:
            r = subprocess.run(
                ["curl", "-sI", "-o", "/dev/null", "-w", "%{http_code}",
                 "--connect-timeout", "10", "--max-time", "10", url],
                capture_output=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            http_code = r.stdout.decode("utf-8", errors="replace").strip()
            if http_code == "404":
                self.failed.emit("服务器上未找到更新文件（可能已被删除），请联系开发者")
                return
            if http_code.startswith(("4", "5")):
                self.failed.emit(f"更新服务器返回错误 (HTTP {http_code})，请稍后重试")
                return
        except Exception:
            pass  # HEAD 失败不阻断，继续尝试下载

        dl_urls = []
        # 国内 GitHub 代理加速（免费公共代理，不需要任何配置）
        if "github.com" in url and "/releases/download/" in url:
            dl_urls.extend([
                url.replace("https://github.com/", "https://ghfast.top/https://github.com/"),
                url.replace("https://github.com/", "https://gh-proxy.com/https://github.com/"),
                url.replace("https://github.com/", "https://mirror.ghproxy.com/https://github.com/"),
            ])
        dl_urls.append(url)  # GitHub 原始链接作为兜底

        for attempt in range(3):
            if attempt > 0:
                __import__("time").sleep(2 * attempt)

            dl_url = dl_urls[min(attempt, len(dl_urls) - 1)]

            try:
                total = self._get_content_length(dl_url)

                parts = [tmp + f".part{i}" for i in range(4)]
                procs = []
                if total > 0:
                    # 分 4 路并行下载，实时百分比
                    chunk = total // 4
                    for i in range(4):
                        start = i * chunk
                        end = total - 1 if i == 3 else (i + 1) * chunk - 1
                        p = subprocess.Popen(
                            ["curl", "-sL",
                             "--connect-timeout", "30", "--max-time", "600",
                             "--retry", "3", "--retry-delay", "2",
                             "-r", f"{start}-{end}", "-o", parts[i], dl_url],
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                        procs.append(p)

                    while any(p.poll() is None for p in procs):
                        downloaded = sum(
                            os.path.getsize(part) for part in parts
                            if os.path.exists(part)
                        )
                        self.progress.emit(min(int(downloaded * 100 / total), 99))
                        __import__("time").sleep(0.2)

                    # 失败的分片单独重试一次
                    for i, p in enumerate(procs):
                        if p.returncode != 0:
                            start = i * chunk
                            end = total - 1 if i == 3 else (i + 1) * chunk - 1
                            p2 = subprocess.run(
                                ["curl", "-sL",
                                 "--connect-timeout", "30", "--max-time", "600",
                                 "--retry", "3", "--retry-delay", "2",
                                 "-r", f"{start}-{end}", "-o", parts[i], dl_url],
                                creationflags=subprocess.CREATE_NO_WINDOW,
                                timeout=620
                            )
                            if p2.returncode != 0:
                                raise RuntimeError(
                                    f"分片 {i} 下载失败 (返回码: {p2.returncode})")

                    # 合并分片
                    with open(tmp, "wb") as out:
                        for part in parts:
                            with open(part, "rb") as inp:
                                out.write(inp.read())
                            os.remove(part)
                else:
                    # 单路下载：实时轮询文件大小，估算进度
                    p = subprocess.Popen(
                        ["curl", "-sL",
                         "--connect-timeout", "30", "--max-time", "600",
                         "--retry", "3", "--retry-delay", "2",
                         "-o", tmp, dl_url],
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    procs.append(p)

                    last_size = 0
                    stall_ticks = 0
                    while p.poll() is None:
                        try:
                            cur = os.path.getsize(tmp)
                        except OSError:
                            cur = 0
                        if cur > last_size:
                            est_pct = min(int(cur / (192 * 1024 * 1024) * 100), 95)
                            self.progress.emit(max(est_pct, 1))
                            stall_ticks = 0
                        else:
                            stall_ticks += 1
                            # curl 自身有 --retry 重连中，不降进度
                        last_size = cur
                        __import__("time").sleep(0.2)

                    if p.returncode != 0:
                        raise RuntimeError(f"curl 进程异常退出 (返回码: {p.returncode})")

                if not os.path.exists(tmp) or os.path.getsize(tmp) == 0:
                    raise RuntimeError("下载完成但文件为空")

                # 验证下载的文件是有效的 Windows PE exe
                fsize = os.path.getsize(tmp)
                with open(tmp, "rb") as _f:
                    header = _f.read(2)
                if header != b"MZ":
                    raise RuntimeError(
                        f"下载的文件不是有效的 exe（MZ 头校验失败，"
                        f"文件大小 {fsize / 1024 / 1024:.1f}MB）")
                if fsize < 5 * 1024 * 1024:
                    raise RuntimeError(
                        f"下载的文件体积异常（仅 {fsize / 1024 / 1024:.1f}MB），"
                        f"可能下载不完整")

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
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowSystemMenuHint
        )
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
        accent2 = t("accent2")

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
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {accent},stop:1 {accent2});
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
        if pct >= 100:
            self._progress_lbl.setText("下载完成，正在校验...")
        elif pct > 0:
            self._progress_lbl.setText(f"正在下载... {pct}%")
        else:
            self._progress_lbl.setText("正在连接...")

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
        # 把临时文件复制到安全位置，防止 temp 目录被清理
        safe_dir = os.path.join(tempfile.gettempdir(), "hengxing_update")
        os.makedirs(safe_dir, exist_ok=True)
        safe_path = os.path.join(safe_dir, "hengxing_update.exe")
        try:
            import shutil
            shutil.copy2(self._tmp_path, safe_path)
        except Exception:
            self._progress_lbl.setText("更新文件丢失，请重新下载")
            self._update_btn.setText("重新下载")
            self._update_btn.setEnabled(True)
            try:
                self._update_btn.clicked.disconnect()
            except Exception:
                pass
            self._update_btn.clicked.connect(self._start_update)
            return
        self._apply_update_static(safe_path)

    @staticmethod
    def _apply_update_static(new_exe):
        current_exe = os.path.abspath(
            sys.executable if getattr(sys, "frozen", False) else __file__)
        current_pid = os.getpid()
        log_file = os.path.join(tempfile.gettempdir(), "hengxing_update.log")
        new_name_fallback = (
            current_exe[:-4] + "_new.exe"
            if current_exe.lower().endswith('.exe')
            else current_exe + "_new.exe"
        )

        bat = os.path.join(tempfile.gettempdir(), "hengxing_update.bat")
        with open(bat, "w", encoding="gbk") as f:
            f.write("@echo off\n")
            f.write(f"echo [%%date%% %%time%%] 开始更新 >> \"{log_file}\"\n")
            f.write(f"echo   旧文件: \"{current_exe}\" >> \"{log_file}\"\n")
            f.write(f"echo   新文件: \"{new_exe}\" >> \"{log_file}\"\n")
            f.write(f"echo   等待 PID={current_pid} 自然退出... >> \"{log_file}\"\n")

            # ── 轮询等待进程自然退出（最多 30 秒）──
            f.write("set TRIES=0\n")
            f.write(":wait_exit\n")
            f.write(f"tasklist /fi \"PID eq {current_pid}\" 2>nul | find \"{current_pid}\" >nul\n")
            f.write("if errorlevel 1 goto do_replace\n")
            f.write("ping 127.0.0.1 -n 2 >nul\n")
            f.write("set /a TRIES+=1\n")
            f.write("if %TRIES% lss 30 goto wait_exit\n")

            # 30 秒后仍未退出才强制杀进程（兜底）
            f.write(f"echo [%%date%% %%time%%] 进程未自然退出，强制结束 >> \"{log_file}\"\n")
            f.write(f"taskkill /f /pid {current_pid} >> \"{log_file}\" 2>&1\n")
            f.write("ping 127.0.0.1 -n 4 >nul\n")

            # ── 替换文件（move 同盘原子操作，不留 .old）──
            f.write(":do_replace\n")
            f.write(f"echo [%%date%% %%time%%] 进程已退出，开始替换文件 >> \"{log_file}\"\n")

            # 先清理历史遗留的 .old 文件
            f.write(f"if exist \"{current_exe}.old\" del /f \"{current_exe}.old\" >> \"{log_file}\" 2>&1\n")

            # move /y 直接覆盖：同盘是原子 rename，不产生 .old 备份
            f.write(f"move /y \"{new_exe}\" \"{current_exe}\" >> \"{log_file}\" 2>&1\n")
            f.write("if %errorlevel% equ 0 goto copy_ok\n")

            # move 失败（可能跨盘或短暂锁定），重试 move
            f.write("set RETRY=0\n")
            f.write(":retry_move\n")
            f.write("ping 127.0.0.1 -n 3 >nul\n")
            f.write(f"move /y \"{new_exe}\" \"{current_exe}\" >> \"{log_file}\" 2>&1\n")
            f.write("if %errorlevel% equ 0 goto copy_ok\n")
            f.write("set /a RETRY+=1\n")
            f.write("if %RETRY% leq 5 goto retry_move\n")

            # move 全部失败，用 copy 兜底
            f.write(f"echo [%%date%% %%time%%] move 失败，回退到 copy >> \"{log_file}\"\n")
            f.write("set CRETRY=0\n")
            f.write(":retry_copy\n")
            f.write(f"copy /y \"{new_exe}\" \"{current_exe}\" >> \"{log_file}\" 2>&1\n")
            f.write("if %errorlevel% equ 0 goto copy_ok\n")
            f.write("set /a CRETRY+=1\n")
            f.write("if %CRETRY% leq 5 goto retry_copy\n")

            # 最终兜底：以 _new 命名放到同目录
            f.write(f"echo [%%date%% %%time%%] 替换失败，使用 _new 兜底 >> \"{log_file}\"\n")
            f.write(f"copy /y \"{new_exe}\" \"{new_name_fallback}\" >> \"{log_file}\" 2>&1\n")
            f.write(f"if exist \"{new_name_fallback}\" start \"\" \"{new_name_fallback}\"\n")
            f.write("del \"%~f0\" & exit\n")

            # ── 替换成功，确保缓冲时间足够再启动 ──
            f.write(":copy_ok\n")
            f.write(f"echo [%%date%% %%time%%] 替换成功 >> \"{log_file}\"\n")
            f.write(f"del \"{new_exe}\" >> \"{log_file}\" 2>&1\n")
            # move 原子替换后只需短暂缓冲，让文件系统刷新即可
            f.write("ping 127.0.0.1 -n 3 >nul\n")
            f.write(f"start \"\" \"{current_exe}\"\n")
            f.write("del \"%~f0\" & exit\n")

        subprocess.Popen(["cmd", "/c", bat],
                         creationflags=subprocess.CREATE_NO_WINDOW,
                         close_fds=True)
        QApplication.quit()
