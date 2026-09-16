# 来源与许可证

- `camera.py` 原样复用 [SeatSentinel](https://github.com/ZheLZZ/SeatSentinel) 提交 `73ceec4`，Copyright (c) 2026 ZheZZ，MIT。完整条款见 `LICENSE-SeatSentinel.txt`。
- 检测运行时：Google MediaPipe（Apache-2.0）、OpenCV（Apache-2.0）、NumPy（BSD-3-Clause）、Pillow（HPND）、pystray（LGPL-3.0）、cv2-enumerate-cameras（MIT）。安装包中保留各依赖自身许可证。
- 模型由安装脚本从 Google 官方 `mediapipe-models` 存储下载；来源及固定版本见 `download_models.py`。不将第三方模型权重提交到本项目仓库。
- 设计调研参考 [SafeScreen](https://github.com/kv4u/safescreen) 的失效状态处理和 [WatchMyBack](https://github.com/lorenzodifuccia/WatchMyBack) 的多人提醒流程，未复制这两个项目代码。
