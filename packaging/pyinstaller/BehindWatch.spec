# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from importlib.metadata import distributions
from PyInstaller.utils.hooks import copy_metadata

root = Path(SPECPATH).parents[1]
datas = [(str(root / 'models' / name), 'models')
         for name in ('person_yolox.onnx', 'face.task', 'sface.onnx')]
datas.append((str(root / 'core' / 'vendor' / 'LICENSE-YOLOX'), 'licenses'))
datas += [(str(root / name), 'licenses') for name in
          ('THIRD_PARTY_NOTICES.md', 'LICENSE-SeatSentinel.txt', 'LICENSE-TokenMeter.txt')]
datas += copy_metadata('supervision')
# 上游 wheel 的许可证不会自动随原生 DLL 收集；保留构建环境依赖的原始条款。
for distribution in distributions():
    for file in distribution.files or []:
        if '.dist-info/' in str(file) and any(word in file.name.lower() for word in ('license', 'copying', 'notice')):
            datas.append((str(distribution.locate_file(file)), str(Path('licenses') / file.parent)))
datas.append((str(root / 'packaging' / 'licenses'), 'licenses/Qt'))
version = root / 'build' / 'version.txt'
if version.is_file():
    datas.append((str(version), '.'))

a = Analysis(
    [str(root / 'app.py')], pathex=[str(root)], binaries=[], datas=datas,
    # MediaPipe imports Matplotlib drawing helpers, but monitoring never opens plots.
    # Keep its required import while avoiding unused interactive Qt backends.
    hiddenimports=[], hookspath=[], hooksconfig={'matplotlib': {'backends': 'Agg'}},
    # 本地推理不调用训练、LLM 转换或测试工具；避免开发环境的可选包进入安装器。
    runtime_hooks=[], excludes=['jax', 'jaxlib', 'tensorflow', 'torch', 'pytest', 'IPython'],
    noarchive=False,
)
# Qt6Core 使用 Windows 的 ICU 接口；其他依赖带入的同名 DLL 导出不兼容。
system_icu_names = {'icu.dll', 'icuuc.dll', 'icuin.dll'}
# The app uses Qt Widgets only; the bundled PDF/QML DLLs are optional Qt modules.
unused_qt_names = {
    'qt6pdf.dll', 'qt6quick.dll', 'qt6qml.dll', 'qt6qmlmodels.dll',
    'qt6qmlmeta.dll', 'qt6qmlworkerscript.dll', 'qt6virtualkeyboard.dll',
}
# Camera capture uses Windows backends; FFmpeg here only handles video files.
a.binaries = [item for item in a.binaries
              if Path(item[0].replace('\\', '/')).name.lower() not in system_icu_names | unused_qt_names
              and not Path(item[0].replace('\\', '/')).name.lower().startswith('opencv_videoio_ffmpeg')]
a.datas = [item for item in a.datas
           if Path(item[0].replace('\\', '/')).name.lower() not in system_icu_names]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='BehindWatch',
          debug=False, strip=False, upx=False, console=False,
          icon=str(root / 'assets' / 'BehindWatch.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='BehindWatch')
