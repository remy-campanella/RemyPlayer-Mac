# RemyPlayer 0.1.0

Python + PySide6 开发的 macOS 本地音乐播放器。需求与架构见 [PROMPT.0.0.0.md](PROMPT.0.0.0.md)，本版规则与限制见 [CHANGELOG.md](CHANGELOG.md)。

## 安装 0.1.0

打开 `dist/RemyPlayer-0.1.0-macos-arm64.dmg`，先退出旧版本，再将 RemyPlayer 拖入 Applications，复制完成后推出镜像。支持 Apple Silicon Mac，macOS 14 或更新版本；本包为本地临时签名，尚未进行 Developer ID 签名或 Apple 公证。

复现发布构建：先运行 `.venv/bin/python scripts/build_app.py --no-install`，再运行 `.venv/bin/python scripts/build_dmg.py`。后者验证应用版本和签名、创建并校验镜像、挂载后检查安装内容，并生成 SHA-256 校验文件。

## 启动

在项目根目录执行：

```sh
source .venv/bin/activate
python run.py
```

当前环境已安装项目，也可以执行 `remyplayer` 或 `python -m remyplayer`。无需激活环境的方式为 `.venv/bin/python run.py`。

选择音乐文件夹后自动扫描，双击曲目或点击“播放此列表”开始播放。左侧按文件夹、作者、专辑浏览；搜索框筛选当前列表。浏览和搜索不改变正在播放的队列。

- ⌘O 选择音乐库；⌘R 重新扫描；⌘F 搜索；⌘Q 退出。
- 空格播放／暂停；← 后退 10 秒，→ 前进 10 秒，超过边界时停在开头／结尾。搜索框输入时保留文字编辑按键；曲目列表中回车播放选中项。
- 点击搜索框外的标题、空白区域或控件即可结束输入占用，恢复播放快捷键。
- 播放中默认输出设备发生变化（包括耳机断开）时先暂停，再更新输出设备，需手动恢复播放；不会自动开始外放。
- 关闭窗口后通过菜单栏继续操作，可选后台保留 Dock 图标。
- 菜单栏“显示主窗口”恢复窗口和 Dock；“退出 RemyPlayer”结束后台进程。
- 后台保留 Dock 时，点击 Dock 图标或从 Finder 重新打开应用会恢复主窗口。主窗口显示时始终保留 Dock，“后台保留 Dock”设置仅控制窗口关闭后的行为。
- 系统菜单栏不可用时，关闭窗口会退出，避免隐藏后无法找回。

macOS 使用原生音乐符号作为菜单栏入口，点击后选择“显示主窗口”即可恢复。首次启动将图标放在右侧，并记住之后调整的位置。关闭窗口时会检查入口是否被刘海遮挡；入口不可用或后台丢失时，自动恢复窗口和 Dock，不会留下无法找回的隐藏播放器。

Dock 图标由 AppKit 直接加载完整 `.icns`，启动与恢复使用同一来源，保留高分辨率及 Retina 图像；不通过 Qt 的运行时应用图标转换。

## 初版行为

- 只读递归扫描、标签读取、SQLite 增量索引、取消扫描和问题明细。
- 文件夹列表只包含直接拥有的曲目；作者按 artist 标签分组；同名专辑合并。
- 文件名按数字段自然排序，数值相同时前导零更多的在前（`01 < 1`）；中文按拼音排序，多音字使用 pypinyin 默认读音。
- 不循环：单曲一次；单曲循环：重复当前曲目；顺序播放：列表末尾停止；循环播放：列表循环；随机播放：一轮内不重复。
- 保存音乐库位置、音量、播放模式、Dock 偏好和窗口尺寸。启动时加载索引并重新扫描，不自动播放。

扫描候选格式：MP3、FLAC、M4A、AAC、OGG、Opus、WAV、AIFF、WMA。扩展名不保证标签和解码支持，实际取决于编码及当前 Qt 后端；失败会报告。集成测试使用生成的静音 PCM WAV，其他格式仍需真实曲库验证。

设置与索引使用 `QStandardPaths.AppDataLocation` 对应的应用数据目录，不写入音乐文件夹。`--data-dir` 可指定独立目录。暂不扫描符号链接，不保证无缝切歌，不恢复上次播放队列与时间进度，也不实时监听目录变化；可手动重新扫描。

## 环境

当前开发环境：Python 3.14.6、PySide6 6.12.0。该 PySide6 wheel 要求 macOS 14 或更新版本；独立应用还受到 Python 与本机构建环境的限制，不承诺兼容较旧 macOS。

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e .
.venv/bin/python -m pip check
```

`pyproject.toml` 声明版本、入口和依赖；`requirements.in` 声明直接依赖范围；`requirements.txt` 锁定运行依赖。Mutagen 读取标签，pypinyin 提供拼音，PyObjC Cocoa 处理 macOS 集成。SQLite 和 unittest 使用标准库。

更新依赖后，在干净环境验证并重新生成快照；排除本机 editable 项目和构建工具，不将本机路径写入快照。

## 检查

```sh
.venv/bin/python scripts/check_environment.py
.venv/bin/python scripts/run_checks.py
.venv/bin/python scripts/check_desktop.py
```

`run_checks.py` 设有 45 秒超时，覆盖排序、分类、只读扫描、缓存、取消、队列和 Qt 集成。音频测试只播放静音 WAV；没有输出设备时跳过三项真实播放测试，需在能访问音频设备的环境补测。

`check_desktop.py` 会发送与 Dock 点击相同的 reopen AppleEvent，再通过原生菜单恢复窗口，并等待后台检查和延迟激活完成后确认 Dock 状态，需要真实 macOS 桌面。

独立应用也可用 `dist/RemyPlayer.app/Contents/MacOS/run --check-desktop --data-dir /tmp/remyplayer-desktop-check` 验证，检查会通过原生菜单动作恢复窗口，而不是直接调用窗口的显示方法。

无窗口检查及截图：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python run.py --smoke-test --data-dir /tmp/remyplayer-check --screenshot /tmp/remyplayer.png
```

可添加 `--library /path/to/music`，扫描完成后截图。测试请使用独立设置目录。

## 界面主题

当前默认使用与图标呼应的黑金主题。样式资源独立于界面业务代码：

- `src/remyplayer/resources/themes/base.qss`：控件样式、布局装饰及交互状态，使用颜色变量。
- `src/remyplayer/resources/themes/black_gold.json`：主题名称、明暗模式与全部颜色。
- 同目录下的 SVG 模板：下拉箭头与勾选标记，运行时按主题颜色生成到临时目录。
- `src/remyplayer/ui/theme.py`：加载、校验、QPalette 与 QSS 生成。

以后可复制主题 JSON，以新的文件名和相同的 `id` 保存并调整颜色；调用 `MainWindow.apply_theme("主题id")` 即可同步切换界面、原生调色板和播放曲目高亮。当前尚未添加主题选择控件，后续可将此接口接入设置并保存偏好。

主题文件会随 Python 包和独立 `.app` 一起分发；生成的小图标写入临时目录，不修改安装包。

## 打包

```sh
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python scripts/build_app.py --no-install
```

使用 PySide6 官方部署工具与 Nuitka，配置见 `pysidedeploy.spec`。构建依赖独立保存在 `requirements-build.in` / `requirements-build.txt`。输出目录为 `dist/`，中间目录为 `deployment/`，均不提交 Git。

Python 3.14 在当前 Nuitka 中仍为实验支持，升级工具链需重新验证打包。本地构建采用临时签名，尚未进行 Developer ID 签名和 Apple 公证。
