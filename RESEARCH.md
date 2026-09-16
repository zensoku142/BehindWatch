# 同类实现调研（2026-09-16）

| 项目 | 实际实现 | 适用性与差异 |
| --- | --- | --- |
| [SeatSentinel](https://github.com/ZheLZZ/SeatSentinel) | Python、OpenVINO、本地人脸检测；CPU/NPU、托盘、多人脸毛玻璃、离席锁屏，MIT | Windows 桌面工程最接近；检测主要基于人脸，不是 Windows Hello。复用其摄像头管理模块。 |
| [SafeScreen](https://github.com/kv4u/safescreen) | Flutter、Media Foundation、BlazeFace、头部姿态；多人脸遮屏、托盘、过期帧处理，MIT | 可参考故障与连续确认逻辑；迁移 Flutter 工具链对当前 Python 原型不是最小改动。其备用摄像头路径会暂存图片。 |
| [WatchMyBack](https://github.com/lorenzodifuccia/WatchMyBack) | Python、MediaPipe 旧版 solutions API，多脸提醒、低头锁屏 | 原型简单，但主要检测人脸，按帧计数阈值随实际帧率变化。未发现独立 LICENSE 文件，不复制其代码。 |
| [iSee](https://github.com/hackergod00001/iSee) | macOS 菜单栏工具，多脸提醒 | 可参考交互；不适用于 Windows 当前交付。未实测。 |
| [Tobii Aware](https://help.tobii.com/hc/en-us/articles/6560844829457-Questions-and-answers-about-Tobii-Aware) | 商业设备集成的人体在场与注意力检测 | 需要兼容设备，不是可直接嵌入任意电脑的开源 Windows Hello 接口。 |

## Windows Hello 的角色

[Windows Hello 应用开发文档](https://learn.microsoft.com/en-us/windows/apps/develop/security/windows-hello)提供身份验证能力；它不是现成的多人窥屏分类器。
Windows 另有 [Presence sensors](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/sensors-presence-sensors) 与 [WinBioMonitorPresence](https://learn.microsoft.com/en-us/windows/win32/api/winbio/nf-winbio-winbiomonitorpresence)，受硬件、驱动和系统支持限制，不能据此假设所有 Hello 摄像头都能输出多人头部朝向或旁观者视线。
SeatSentinel 的源码实际使用 OpenCV 采集普通摄像头画面、OpenVINO 推理，并未调用 Hello 完成多人检测。

本实现采用普通 RGB 摄像头、本地人体检测和人脸头部朝向估计。头部朝向只能表示可能看向屏幕附近，不能确认对方视线落点或阅读行为；电脑摄像头无法观测视野外和完全遮挡区域。
