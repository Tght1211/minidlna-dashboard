# 家庭媒体库 · minidlna-dashboard

> 给 macOS 上的 **minidlna** 套一个赛博朋克 + Netflix 风的 Web 仪表盘。
> 替代 minidlna 那个写死在二进制里的简陋状态页（端口 8200），独立运行在 **8201** 端口。

[![License: MIT](https://img.shields.io/badge/License-MIT-00e6c3.svg)](LICENSE)
![Platform](https://img.shields.io/badge/platform-macOS-ff2d7d)
![Python](https://img.shields.io/badge/python-3.10%2B-00e6c3)

---

## 是什么

- 一个 **零侵入** 的 minidlna 配套 Web UI。原 8200 端口的 DLNA/UPnP 协议完全不动，仪表盘自跑 8201。
- 直接读 minidlna 的 SQLite 索引 (`~/.cache/minidlna/files.db`)，**只读、不写**，永远跟最新扫描结果对齐。
- 浏览器里看到的就是你 LAN 上 DLNA 客户端能看到的同一份目录，外加：**Netflix 风海报轮播、网易云风音乐播放器、照片 lightbox、自动同步**。

## 特性

- **首页（Netflix 风）**：随机视频自动轮播的 hero 海报（2560px 高清 + Ken Burns 推拉），标题是"X 年前的回忆"自动算出来；下面是横向滚动行（最近视频 / 最近照片 / 最近音频），鼠标移上去出箭头按钮。
- **媒体库浏览**：`全部 / 视频 / 照片 / 音乐` 四个 tab 在头部导航直达。按媒体目录下的"日期文件夹"分组，无限滚动分页（每页 60 项 + IntersectionObserver 触底加载）。
- **音乐播放器**：网易云风格，黑胶旋转封面（基于歌名 hash 自动配色）、自定义进度条、大号播放按钮。
- **照片大图**：全屏 lightbox，左右切换 / Esc 关 / 点图放大 / 下载原图，骨架按已知分辨率预留布局空间，切图不抖。
- **视频播放**：浏览器内 HTML5 `<video>`，stage 按视频实际比例渲染不留黑边；同时弹窗里有 DLNA 直链按钮可复制给投影仪等局域网客户端。
- **赛博朋克 HUD**：扫描线蒙层、`SYSTEM ONLINE` 脉冲点、实时时钟、面板角落 `clip-path` 切角、青/品红双霓虹色板。
- **设置页**：GUI 增删媒体目录、查看 minidlna 日志、一键重启服务、批量预生成视频缩略图。
- **自动同步**：30 秒轮询每个 media_dir 的顶层条目（不递归，避免 launchd 下的 TCC / fd 坑），检测到变化防抖 30 秒后给 minidlna `SIGHUP` 触发增量重扫。
- **缩略图**：ffmpeg 按需生成（卡片 320px / hero 2560px 两级缓存），并发限制 3 个 ffmpeg 进程避免外置盘抖动。
- **静态资源版本号**：每次仪表盘重启自动 bump CSS/JS 版本号，浏览器无需手动硬刷。

## 页面布局

```
┌────────────────────────────────────────────────────────────────────┐
│ ◢ 家庭媒体库  v1·NODE/100   ● SYSTEM ONLINE   00:00:00  [首页] 视频 ...│
├────────────────────────────────────────────────────────────────────┤
│ ┌─                                                             ─┐  │
│ │                                                                │  │
│ │              [HERO 海报 · 自动轮播 · Ken Burns]                │  │
│ │                                                                │  │
│ │  ▸ 回忆                                                        │  │
│ │  1 年前的回忆                                                  │  │
│ │  VID_xxx · 0:00:06 · 3840x2160 · 57 MB                         │  │
│ │  [▶ 播放]  [浏览全部视频]              ─ ─ ━ ─ ─ ─ ─ ─ ─ ─    │  │
│ └─                                                             ─┘  │
│                                                                    │
│  ┌─ 音频 ─┐ ┌─ 视频 ─┐ ┌─ 图片 ─┐ ┌─ 总大小 ─┐                  │
│  │ 179   │ │ 1476  │ │ 2843  │ │ 535.2 GB │                       │
│  └───────┘ └───────┘ └───────┘ └──────────┘                       │
│                                                                    │
│  最近视频  [全部 →]                                                │
│  ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐  ‹ ›                                    │
│  └──┘ └──┘ └──┘ └──┘ └──┘                                          │
│                                                                    │
│  最近照片  [全部 →]                                                │
│  ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐                                          │
│  └──┘ └──┘ └──┘ └──┘ └──┘                                          │
│                                                                    │
│  最近音频  [全部 →]                                                │
│  ♪ ...                                                             │
└────────────────────────────────────────────────────────────────────┘
  NODE://MINIDLNA-DASHBOARD  /  PORT 8201  /  UPLINK 192.168.x.x      ◉
```

## 系统要求

**目前仅支持 macOS**（Apple Silicon 和 Intel 都行）。

| 依赖 | 用途 |
|---|---|
| macOS 12+ | 主机系统 |
| [Homebrew](https://brew.sh) | 装 minidlna / ffmpeg |
| `minidlna` | 真正干 DLNA 协议的事 |
| `ffmpeg` | 视频缩略图抽帧 |
| Python 3.10+ | Flask + 标准库 |

为什么不是跨平台？详见 [架构](#架构) 章节——很多决策（kqueue / TCC / launchd / lsof）是 macOS 特有的，硬上 Linux/Windows 会拖累 macOS 上的体验，所以决定先专心做好 Mac。

## 快速开始

### 1. 装好依赖

```bash
brew install minidlna ffmpeg python@3.12
```

### 2. 配 minidlna

编辑 `~/.config/minidlna/minidlna.conf`，最小例子：

```conf
# DLNA 客户端（投影仪 / 小爱 / 电视）上显示的名字
friendly_name=家庭媒体库

# 监听网卡，跟着你家 Wi-Fi 的那张
network_interface=en0

# DLNA 端口
port=8200

# 数据/日志目录
db_dir=/Users/<你的用户名>/.cache/minidlna
log_dir=/opt/homebrew/var/log

# 媒体目录。前缀 A=音频 V=视频 P=图片，可组合；省略前缀就是全部
media_dir=A,/Users/<你的用户名>/Music/cyberpunk-player
media_dir=PV,/Volumes/external-drive/photos-and-videos

# 关闭原生 inotify——macOS 上是 kqueue 实现，大目录会爆 fd
# 反正本仪表盘有自己的轮询器，你不损失自动重扫
inotify=no
```

启动 minidlna：

```bash
brew services start minidlna
```

### 3. 装仪表盘并自启动

```bash
git clone https://github.com/Tght1211/minidlna-dashboard.git
cd minidlna-dashboard
./scripts/install.sh
```

`install.sh` 做了这些事：

- 建 Python venv (`.venv/`)
- 装 `flask`
- 写一份 launchd plist 到 `~/Library/LaunchAgents/local.minidlna-dashboard.plist`
- `launchctl bootstrap` 装载，开机自启
- 立即启动一次

走完命令行会打印访问地址：

```
✓ Installed and started: local.minidlna-dashboard
  Logs: /Users/<你>/.cache/minidlna-dashboard/logs/
  URL:  http://192.168.x.x:8201/
```

### 4. 日常使用

- **首页**：[`http://<IP>:8201/`](http://localhost:8201/)
- **视频 / 照片 / 音乐**：头部分类导航直达
- **设置**：`/settings`

LAN 上其他设备（手机、平板、投影仪）访问同一个 URL 都能用。

### 5. 交互速查

- Hero 海报：12 秒一切，点底部进度条 / 键盘 ← → / 鼠标拖动均可手动切换，鼠标移上去暂停自动轮播
- 卡片：hover 放大并显示 ▶；点击打开对应播放器
- 横向行：鼠标移上去左右出箭头按钮，平滑滚动
- 弹窗：Esc 关闭，照片 lightbox 支持 ← → 翻页、点击图片切换缩放

## 常用命令

```bash
# 重启仪表盘
launchctl kickstart -k gui/$(id -u)/local.minidlna-dashboard

# 看仪表盘日志
tail -f ~/.cache/minidlna-dashboard/logs/stdout.log

# 重启 minidlna
brew services restart minidlna

# 手动触发一次 minidlna 全库重扫（在仪表盘"立即扫描"按钮的等效命令）
pkill -HUP minidlnad

# 卸载仪表盘
./scripts/uninstall.sh
```

## 项目结构

```
minidlna-dashboard/
├── app.py                # Flask 入口 + 所有路由
├── lib/
│   ├── db.py             # 只读 files.db，提供 counts/recent/folders/search 等查询
│   ├── status.py         # pgrep/lsof/df 衍生的运行时状态（HTTP 抓不到，见架构）
│   ├── config.py         # minidlna.conf 解析/写入
│   ├── thumbs.py         # ffmpeg 缩略图（按需生成 + 并发限制 3 + 磁盘缓存）
│   └── watcher.py        # 自实现轮询监听器（不依赖 watchdog）
├── templates/
│   ├── base.html         # 头部 HUD + 时钟 + 扫描线蒙层 + footer
│   ├── index.html        # 概览页 + hero banner + 横向滚动行
│   ├── browse.html       # 媒体库 + tabs + 无限滚动
│   └── settings.html     # 配置管理
├── static/
│   ├── main.css          # 赛博朋克色板 / clip-path 切角 / Netflix 卡片
│   └── main.js           # 卡片点击委派 / 音乐播放器 / 照片 lightbox / 时钟
├── scripts/
│   ├── install.sh        # venv + plist + launchctl bootstrap
│   ├── uninstall.sh
│   └── run.sh            # launchd 启动入口
└── requirements.txt
```

## 架构

几个非显然的决策，写下来给自己看也给路过的人看：

### 为什么不直接抓 minidlna 自己的 HTTP 状态页？

minidlna 的 `network_interface=en0` 让它**只接受 en0 上的连接**。但是从本机用 `127.0.0.1` 或本机 LAN IP 访问，macOS 路由会走 `lo0`，被 minidlna 直接 reset。所以我们绕开 HTTP 抓取，改用：

- `pgrep -f minidlnad` + `ps` 拿 pid / uptime
- `lsof -iTCP:8200 -sTCP:ESTABLISHED` 拿连接中的 DLNA 客户端 IP
- `lsof -p <pid>` 看 minidlna 是否还在读 media_dir（推断 scan_in_progress）
- `shutil.disk_usage()` 拿磁盘
- 一切媒体元数据直接读 `files.db`

### 为什么自写轮询器而不是 watchdog？

两个 macOS 陷阱：

1. **minidlna 的 `inotify=yes` 在 macOS 上是 kqueue 实现**，但它给每个目录都开一个 fd。Insta360 / Android 之类的备份目录树有几千层，直接 EMFILE 崩。
2. **launchd 启动的进程在 TCC 沙箱下**有独立身份，调 FSEvents 访问 `/Volumes/...` 时 `FSEventStreamCreate` 会无限挂起。watchdog 的 `PollingObserver` 也死锁在初始 `DirectorySnapshot`。

最终用的是 30 行 `os.scandir` 轮询每个 media_dir 的**顶层**（不递归），每 30 秒一次，检测到顶层有增删改就防抖 30 秒后 `SIGHUP` minidlna，让它自己做深度扫描。用户的常见动作（拖一个新文件夹进 media_dir）30~60 秒内就能进库。

### 为什么不直接用 minidlna 的 URL 当播放源？

`http://<lan-ip>:8200/MediaItems/<id>.ext` 是给 LAN 上其他设备用的（投影仪/小爱）。**本机浏览器**因为路由走 lo0，被 minidlna 拒。所以仪表盘自己挂了 `/stream/<id>` 端点，用 `send_file(path, conditional=True)` 直接磁盘流式输出（带 Range / seek 支持），浏览器里照样能放。

DLNA 直链仍然给投影仪用——弹窗里有"复制 DLNA 直链"按钮。

## 已知限制

- **HEVC/H.265 视频在 Chromium 系浏览器（Chrome / Edge / Cursor 内置）放不出来**。原因是这些浏览器不内置 HEVC 解码器。解决办法：用 Safari 打开本仪表盘，或者把 Insta360 这类源 HEVC 文件批量转 H.264 后放进 media_dir。本项目不带在线转码，纯靠原始文件。
- **仅 macOS**。Linux 上的 minidlna 用 inotify 没事，但仪表盘里依赖 `lsof` / `pgrep` / `brew services` 的部分需要适配——欢迎 PR。Windows 暂无计划。
- **`network_interface` 必须配置正确**。否则 minidlna 起不来或者 DLNA 客户端发现不到。仪表盘自己不动这个配置。

## 开发

```bash
# 不走 launchd，本地前台跑（看 stdout 方便调试）
./scripts/run.sh

# 或更简单地：
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

代码风格：

- Python 模块都很短（lib/*.py 各 ~100 行内），可以一眼读完。
- 前端没用框架，模板 + 一份 vanilla JS + 一份 CSS，所有交互通过 `data-*` 委派事件实现。
- 没有数据库迁移、没有 ORM——minidlna 的 SQLite 就是真源，仪表盘只读。

## 致谢

- [MiniDLNA](https://sourceforge.net/projects/minidlna/) — 真正干活的那位
- [Flask](https://flask.palletsprojects.com/) — 后端
- 整个项目用 [Claude Code](https://claude.com/claude-code) 跟我边聊边写完的，包括这个 README。

## 协议

[MIT](LICENSE)
