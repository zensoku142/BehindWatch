# 同类实现调研（2026-09-16）

## 固定工位误报与成熟方案（2026-09-17）

后续按用户要求将当前人体检测器试换为 YOLO26s ONNX，仍沿用 ByteTrack 与现有走动规则。已验证模型加载、空白帧推理和坐标接口；尚无同一现场视频的误报与召回对照，因此不能据此断言 YOLO26s 更准。下文 YOLOX 测量是此前版本的历史记录。

首次试换错误地用 OpenCV DNN 执行 YOLO26s 的端到端 TopK：空白帧通过，但含人物画面产生重复错框，现场还能报 `axis is 300` 并停止监测。现改为 ONNX Runtime，使用本地人物样本核对仅输出一个高置信度人体框。该样本只验证推理输出基本合理，仍不足以评估现场走动召回与静坐误报。

先查阅官方文档和项目仓库，随后接入 YOLOX + ByteTrack；Frigate 和姿态模型仅调研，未部署。

| 方案 | 已有能力 | 当前场景取舍 |
| --- | --- | --- |
| [Frigate 静止目标](https://docs.frigate.video/configuration/stationary_objects/) | 跟踪目标位置，区分 stationary / active；静止目标仍保留跟踪，避免重新发现时反复产生新目标 | 最值得借鉴的是保留身份、静止不重复触发。它是监控系统，不是现成的 Windows 桌面坐姿分类器。 |
| [ByteTrack](https://github.com/FoundationVision/ByteTrack) | 使用高、低置信度检测框关联轨迹，改善遮挡导致的轨迹碎片；仓库 MIT | 已通过 Supervision 接入，检测器保留低分候选用于延续已有轨迹，触发仍由独立走动规则决定；它本身不判断坐姿。仓库给出的性能不能直接套用到本机 CPU。 |
| [MediaPipe Pose Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker) | 输出身体关键点，可支持进一步的姿态规则 | 真正区分坐姿与站姿可评估肩、髋、膝关键点与可见度；工位桌板遮挡下肢时不能假设姿态可信，需要保留“未知”状态。需额外模型和多人推理开销，当前未接入。 |

用户后续反馈远处经过不触发，已接入 [OpenCV Zoo YOLOX](https://github.com/opencv/opencv_zoo/tree/47534e27c9851bb1128ccc0102f1145e27f23f98/models/object_detection_yolox) 官方推理实现与 Supervision 0.25.1 的 ByteTrack，摄像头路径不再使用手写贪心框关联。原算法仅保留兼容未携带 tracker_id 的旧调用。修复 0.4 秒检测间隔重置历史、整幅画面 6% 位移门槛和低帧率采样不足导致的漏报；不把示意红框作为固定区域。

本机使用用户提供的带标注截图裁出预览并缩放至 640×480 测试：旧 EfficientDet 输出 2 个身体目标；新 YOLOX 检出了后排小人体候选。YOLOX + 人脸处理 + ByteTrack 的三次耗时约 337 / 247 / 241 毫秒，旧身体检测单次约 30 毫秒（不含人脸处理，不能当作整链路等条件比较）。截图带旧框和红色标注，不能当作未污染的真实视频评测；检测数量不等于准确率，椅子等仍可能误检。新增连续轨迹测试验证 2 FPS 远处经过、短时漏检、低分框延续和静态抖动；尚无现场视频召回率数据。

下一步模型替换应在同一段本地工位样本上比较：每小时误报、经过召回、提醒延迟、忽略标记丢失次数及 CPU/FPS。样本应包含静坐打字、转头探身、起身经过、多人交叉、遮挡和光照变化；未得到这些数据前不能声称替换框架必然更准确。完全遮挡、相似衣着或相邻人脸交叉仍可能丢失或错误关联，当前规则并不等同于坐姿识别。

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
