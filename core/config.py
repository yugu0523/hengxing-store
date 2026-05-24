"""应用常量 + 路径工具"""
import sys, os

APP_VERSION = "1.0.37"
UPDATE_CHECK_URL = "https://raw.githubusercontent.com/yugu0523/hengxing-store/master/version.json"


def get_app_dir():
    """返回项目根目录（frozen 时 = exe 所在目录，源码时 = 项目根目录）

    config.py 位于 core/ 子目录，__file__ 是 core/config.py，
    需要向上两级才能得到项目根目录。
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        # core/config.py → core/ → 项目根目录
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
