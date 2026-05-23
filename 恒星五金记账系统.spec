# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[('app_icon.ico', '.')],
    hiddenimports=[
        'core.config', 'core.db', 'core.update',
        'ui.theme', 'ui.widgets', 'ui.dialogs',
        'ui.product_page', 'ui.customer_page', 'ui.print_page', 'ui.stats_page',
        'urllib.request', 'urllib.error',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 排除不需要的大库，减小体积
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'PIL',
              'tkinter', 'unittest', 'email', 'html',
              'xml', 'xmlrpc', 'multiprocessing',
              'lib2to3', 'pkg_resources', 'setuptools',
              'pydoc', 'doctest', 'argparse'],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='恒星五金记账系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=r'C:\Users\27635\app_icon.ico',
)
