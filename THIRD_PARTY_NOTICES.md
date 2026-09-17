# 来源与许可证

- `core/vendor/yolox.py` 原样复用 [OpenCV Zoo YOLOX](https://github.com/opencv/opencv_zoo/tree/47534e27c9851bb1128ccc0102f1145e27f23f98/models/object_detection_yolox)，固定提交 `47534e27c9851bb1128ccc0102f1145e27f23f98`，Apache-2.0；完整条款见 `core/vendor/LICENSE-YOLOX`。YOLOX 权重来自同一目录，来源及 SHA-256 固定在下载脚本。
- 人员跟踪调用 [Supervision 0.25.1](https://github.com/roboflow/supervision/tree/0.25.1) 中的 ByteTrack 实现（MIT），没有自行重写跟踪算法。应用仅使用本地推理、跟踪接口，不调用 Roboflow 云端服务。

- `core/camera.py` 原样复用 [SeatSentinel](https://github.com/ZheLZZ/SeatSentinel) 提交 `73ceec4`，Copyright (c) 2026 ZheZZ，MIT。完整条款见 `LICENSE-SeatSentinel.txt`。
- Qt 主题与语言绑定（`ui/qt_theme.py`、`ui/i18n.py`）、`ui/ui_widgets.py` 中的设置页签、开关、下拉框，以及 `core/autostart.py` 的开机自启方式适配自 [TokenMeter](https://github.com/zensoku142/TokenMeter) 的本地 TokenSpider 源码，Copyright (c) 2026 zensoku142，MIT。完整条款见 `LICENSE-TokenMeter.txt`。本应用不依赖另一个项目目录运行。
- 检测运行时：Google MediaPipe（Apache-2.0）、OpenCV（Apache-2.0）、NumPy（BSD-3-Clause）、Pillow（HPND）、cv2-enumerate-cameras（MIT）。界面使用 PySide6 / Qt（LGPL-3.0 / GPL-3.0 / 商业许可，按所用模块适用条款分发）；安装包中保留各依赖自身许可证。
- Windows 新闻通知使用 win11toast（MIT）；新闻标题和正文链接来自[中国新闻网国内新闻 RSS](https://www.chinanews.com.cn/rss/)，通知中注明来源，点击后跳转原文。
- 人脸关键点模型由安装脚本从 Google 官方 `mediapipe-models` 存储下载；注册识别模型 SFace 和人体检测 YOLOX 来自 [OpenCV Zoo](https://github.com/opencv/opencv_zoo)，对应模型目录标明 Apache-2.0。来源及 SHA-256 见 `scripts/download_models.py`。不将第三方模型权重提交到本项目仓库。
- 设计调研参考 [SafeScreen](https://github.com/kv4u/safescreen) 的失效状态处理和 [WatchMyBack](https://github.com/lorenzodifuccia/WatchMyBack) 的多人提醒流程，未复制这两个项目代码。


## 安装版的依赖条款

安装目录 `_internal/licenses/` 保留复用源码和构建环境中各依赖 wheel 自带的 LICENSE/COPYING/NOTICE。另附 Qt LGPL-3.0 与 GPL-3.0 原文，来源为 [Qt 6.11.2 的 LICENSES](https://github.com/qt/qtbase/tree/v6.11.2/LICENSES)。Qt 为独立动态库；本项目不修改 Qt/PySide6，源码和构建资料可从 [Qt](https://code.qt.io/cgit/qt/qtbase.git/) 与 [PySide](https://code.qt.io/cgit/pyside/pyside-setup.git/) 对应版本获取；许可说明见 [Qt for Python 官方页面](https://doc.qt.io/qtforpython-6/licenses.html)。依赖的许可证不代表本仓库的自有代码已整体授予同一许可证。
