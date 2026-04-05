# -*- mode: python ; coding: utf-8 -*-


import sys
import os
from pathlib import Path

# 根据平台选择要打包的 ffmpeg
if sys.platform == 'darwin':
    ffmpeg_binaries = [('binaries/macos/ffmpeg', 'binaries/macos')]
elif sys.platform == 'win32':
    # Windows: 包含 ffmpeg.exe 和所有 DLL 依赖
    ffmpeg_binaries = []
    windows_bin_dir = Path('binaries/windows')
    for file in windows_bin_dir.glob('*'):
        if file.is_file():
            ffmpeg_binaries.append((str(file), 'binaries/windows'))
else:
    ffmpeg_binaries = []

a = Analysis(
    ['ncm2mp3.py'],
    pathex=[],
    binaries=ffmpeg_binaries,
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ncm2mp3',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ncm2mp3',
)
app = BUNDLE(
    coll,
    name='ncm2mp3.app',
    icon=None,
    bundle_identifier=None,
)
