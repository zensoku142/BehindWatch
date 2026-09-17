# 项目结构

```text
BehindWatch/
├── app.py                 # Qt 主程序入口
├── bootstrap.py           # 源码运行环境检查
├── launch.cmd, setup.ps1  # 源码版依赖与模型初始化
├── core/                  # 摄像头、监测规则、人脸、窗口保护、偏好和新闻
├── ui/                    # Qt 控件、主题与翻译
├── updater/               # Release 检查、校验下载和独立安装器入口
├── models/                # 本地模型；下载生成，不提交二进制
├── scripts/               # 模型下载与发布构建
├── packaging/             # PyInstaller 与 Inno Setup 配置
├── tests/                 # 单元测试和 Qt 行为测试
├── docs/                  # 开发文档
└── .github/workflows/     # Windows 发布流水线
```

源码版运行 `launch.cmd`，使用项目 `.venv`。安装版由 PyInstaller 打包为 onedir，内置固定模型；Inno Setup 安装到当前用户目录，不要求用户安装 Python。用户偏好和已注册人脸仍存放在 `%LOCALAPPDATA%\BehindWatch`，覆盖安装不会删除。

发布使用 `python scripts/build_release.py --version X.Y.Z`。`--stage onedir` 和 `--stage installer` 可以分别构建。正式发布需按仓库版本规范准备版本号、`vX.Y.Z` Tag 和对应发布说明。打包产物输出到 `dist/`，安装器与 `SHA256SUMS.txt` 输出到 `dist-installer/`。

安装版从固定 GitHub 仓库读取正式 Release，只有包含匹配安装器和校验文件时才允许自动安装。下载后校验 SHA-256；独立更新器等待主程序退出，再静默覆盖安装。源码版保留打开 Release 页面手动下载的入口。

## 提交边界

| 类别 | 处理方式 |
| --- | --- |
| app.py、bootstrap.py、core/、ui/、updater/ | 提交运行源码；根目录旧模块已迁入对应包 |
| scripts/、packaging/、.github/workflows/ | 提交构建、安装和发布配置 |
| tests/、docs/、tools/、release-notes/ | 提交测试、使用/开发文档、诊断工具和版本说明 |
| assets/、LICENSE-*.txt、THIRD_PARTY_NOTICES.md | 提交图标及第三方归属和许可证 |
| requirements*.txt、setup.ps1、launch.cmd、AGENTS.md、版本规范 | 提交依赖、启动入口和协作规范 |
| models/ | 仅提交 .gitkeep；模型由固定地址下载并校验，随安装包分发 |
| .venv/、.runtime/、build/、dist/、dist-installer/ | 本机依赖、缓存和构建产物，忽略；安装器作为 Release 附件上传 |
| work/、design-qa.md | 本机截图、实验和历史验收记录，忽略，不作为当前版本验收依据 |
| 用户偏好、人脸模板、录像、日志、转储、.env、私钥 | 不提交；实际用户数据位于 LOCALAPPDATA，证书由本机保管 |

正式文档插图可以放在 docs/ 下提交；不要用全局 PNG/JPG 忽略规则阻止文档资源。提交前执行 `git diff --check` 和 `git diff --cached --stat`，核对新增文件，不能仅依赖 .gitignore 排除敏感信息。

## 发布检查

1. 在稳定工作区跑完整测试，核对版本说明与实现。
2. 执行 `scripts/build_release.py --version 0.1.0`，Inno Setup 不在标准路径时传 `--iscc`。
3. 运行打包程序 `--smoke-test`（加载模型和设置界面，不开启真实摄像头）；在独立目录测试首次安装、覆盖安装及安装后自检。
4. 按版本规范提交并推送分支；可先手动运行 release 工作流（release_tag=vX.Y.Z）在干净 Windows 环境验证，手动运行不会发布。
5. 验证通过后创建并推送未使用的 vX.Y.Z Tag。Tag 流水线再次验证并发布，随后核对 Release 正文、安装器、SHA256SUMS.txt 和 Tag 指向。

当前源码的更新页显示“开发版本”；安装包版本来自构建时的 version.txt，不能通过手改源码伪装已安装版本。
