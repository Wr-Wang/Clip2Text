# Clip2Text — 抖音分享文本语音文案提取工具

粘贴抖音分享文本，自动提取语音文案的本地化 Web 工具。

## 快速开始

```bash
# 1. 安装依赖
cd backend
pip install -r requirements.txt

# 2. 启动服务
python -m uvicorn app.main:app --reload

# 3. 打开浏览器访问
# http://127.0.0.1:8000
```

## 使用流程

1. 在抖音 App 打开视频 → 点分享 → 选"复制链接"
2. 粘贴整段分享文本到页面文本框
3. 系统自动识别视频链接，点击"开始提取"
4. 等待处理完成，下载文案、视频或音频

## 功能特性

- 🆓 **免费开源** — 无需付费，代码完全开放
- 🔒 **本地运行** — 数据保存在本地，无需上传到第三方
- 📦 **批量处理** — 一次粘贴多条分享文本，后台逐个处理
- 🔗 **智能提取** — 自动从分享文本中提取抖音视频链接
- 📥 **全文件下载** — 文案(.txt)、视频(.mp4)、音频(.wav)均可下载

## 技术栈

| 层 | 技术 |
|---|------|
| 后端 | Python 3.11+ / FastAPI |
| 视频下载 | yt-dlp |
| 音频处理 | ffmpeg (via imageio-ffmpeg) |
| 语音识别 | openai-whisper (base) |
| 前端 | Jinja2 / Bootstrap 5 |
| 任务队列 | FastAPI BackgroundTasks |

## 项目结构

```
ai-asr/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py             # 配置管理
│   │   ├── routers/
│   │   │   ├── tasks.py          # 任务 API
│   │   │   └── files.py          # 文件下载 API
│   │   ├── services/
│   │   │   ├── url_extractor.py  # 分享文本 URL 提取
│   │   │   ├── downloader.py     # 视频下载
│   │   │   ├── audio.py          # 音频提取
│   │   │   ├── transcriber.py    # 语音识别
│   │   │   └── task_manager.py   # 任务状态管理
│   │   ├── models/
│   │   │   └── schemas.py        # Pydantic 数据模型
│   │   └── templates/
│   │       ├── base.html         # 基础布局
│   │       ├── index.html        # 首页
│   │       └── task_detail.html  # 任务详情页
│   └── requirements.txt
├── data/                         # 运行时数据
│   ├── downloads/                # 视频临时存储
│   ├── audio/                    # 音频临时存储
│   └── transcripts/              # 最终文案输出
└── docs/PRD.md                   # 需求文档
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/tasks` | 提交任务（接受 texts 数组） |
| GET | `/api/tasks/{id}` | 查询任务状态 |
| GET | `/api/files/{tid}/{iid}/transcript` | 下载文案 |
| GET | `/api/files/{tid}/{iid}/video` | 下载视频 |
| GET | `/api/files/{tid}/{iid}/audio` | 下载音频 |
| GET | `/api/tasks/{id}/download` | 批量打包下载 |
| GET | `/api/health` | 健康检查 |

## 注意事项

- **Whisper 模型**：首次启动会自动下载 base 模型（~1GB）
- **处理速度**：CPU 模式下，1 分钟音频约需 30-60 秒处理
- **网络要求**：需要访问抖音 CDN 下载视频
- **Cookie 支持**：某些限制内容需要传入 Cookie（通过环境变量）
