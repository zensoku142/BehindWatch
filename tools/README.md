# 红外摄像头小验证

`probe_ir_camera.ps1` 是独立诊断工具，不接入 BehindWatch 的监测流程，不安装依赖。
使用 Windows 自带的 **Windows PowerShell 5.1（powershell.exe）**，不能用 PowerShell 7（pwsh）。

在项目根目录只枚举图像源，不启动采集：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\probe_ir_camera.ps1
```

采集红外 10 秒，输出帧数后释放设备：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\probe_ir_camera.ps1 -Capture -Seconds 10
```

默认优先选择仅含红外的设备组。可使用 `-InfraredIndex N` 选择枚举结果中的其他红外源。
脚本只创建红外读取器，不创建 RGB 读取器或音频流，不显示、保存或上传图像。
采集期间请观察实际指示灯；仅凭红外 API 成功不能判断 RGB 模块是否断电。
退出码 0 表示枚举成功或采集检查通过，1 表示失败；无连续帧不会被报告为成功。

## 本机实测（2026-09-16）

- 联想 83D4，Windows 11，Integrated IR Camera。
- WinRT 可枚举独立红外组和 Lenovo RGB/IR 联合组。
- 独立红外组：L8 / Gray8，640×360，设备报告 15 fps。
- 10 秒收到 148 个不同时间戳的红外位图，轮询观察速率约 14.8 fps；正常停止并释放设备。
- 工具受限沙箱内曾出现启动成功但没有帧；在沙箱外运行同一脚本后通过。没有更改系统摄像头权限。

## 自动复验与日志

验证脚本现在每秒在内存中抽样灰度像素，输出最小值、最大值、均值和相邻抽样变化；同时检查超过 2 秒的断帧。
灰度范围至少为 8 仅是排除完全空白的粗略检查，不代表图像足以识别人脸，也不能把像素变化等同于人员移动。

2026-09-16 已执行并读取以下日志（保存在 Git 忽略的 `work/` 目录）：

| 运行 | 结果 | 日志 |
| --- | --- | --- |
| 持续采集 20 秒 | 295 帧，14.7 fps，最大间隔 0.146 秒，退出码 0 | `work/ir-probe/capture-20s.log` |
| 释放后重开 10 秒 | 148 帧，14.8 fps，最大间隔 0.147 秒，退出码 0 | `work/ir-probe/reopen-10s.log` |

两次均正常停止并释放采集对象，第二次可重新出帧。抽样像素显示明暗交替：部分样本最大灰度仅约 5～11，另一些约 150～165；后续须处理这类低亮度帧，不能直接声称现有模型可用。

当前只实现红外访问和基本像素信号验证；**尚未实现红外触发 RGB 摄像头**。`core/vision.py` 仍然在监测启动时打开普通摄像头并持续读取。
尚未验证清晰度、身后人员识别、遮挡、Windows Hello 同时使用、功耗或物理指示灯。
脚本没有配置传感器低帧率；减少轮询次数不等于降低摄像头硬件功耗。
下一步应先验证红外画面能否稳定检测额外人员，再评估红外值守、RGB 按需确认的方案。


## 模型进程内存对照

`profile_runtime.py` 加载现有模型，对 5 张 640×480 空白帧执行推理，输出 Windows 工作集、私有提交量和峰值工作集（MiB），不打开摄像头。请先运行 `launch.cmd` 初始化依赖与模型，再退出应用以减少干扰。

```powershell
.\.venv\Scripts\python.exe tools/profile_runtime.py --with-ui
.\.venv\Scripts\python.exe tools/profile_runtime.py
.\.venv\Scripts\python.exe tools/profile_runtime.py --threads-2
```

首组模拟旧版子进程的界面导入开销；第二组仅加载检测模块。这里只测隔离进程，不代表整个应用或真实画面的长期峰值。空白帧也不能用来衡量检测准确率。
