# Clip2Text — 分享链接语音文案提取工具

## 产品需求文档 (PRD)

**版本**：v0.3 | **日期**：2026-06-10 | **状态**：已实现

---

## 目录

1. [项目背景](#1-项目背景)
2. [产品定位](#2-产品定位)
3. [用户故事](#3-用户故事)
4. [功能需求](#4-功能需求)
5. [非功能需求](#5-非功能需求)
6. [约束与限制](#6-约束与限制)
7. [系统架构](#7-系统架构)
8. [数据模型设计](#8-数据模型设计)
9. [API 接口设计](#9-api-接口设计)
10. [前端页面设计](#10-前端页面设计)
11. [错误处理策略](#11-错误处理策略)
12. [数据流图](#12-数据流图)
13. [项目目录结构](#13-项目目录结构)
14. [验收状态](#14-验收状态)

---

## 1. 项目背景

短视频平台上有大量口语化、有价值的信息内容（知识分享、行业分析、产品评测等），但这些内容以视频形式存在，难以直接进行文字检索、引用和二次加工。用户需要一种工具，能够将视频中的语音内容自动转化为文字，方便存档、检索和复用。

目前市场上缺乏面向普通用户的、免费的、开源的视频语音转文字工具。大多数在线工具需要付费、限制次数，或需要将视频上传到第三方服务器，存在隐私风险。

Clip2Text 定位为本地运行的轻量 Web 服务：用户粘贴任意分享链接，自动下载视频、识别语音、输出文案。

---

## 2. 产品定位

| 项目 | 内容 |
|------|------|
| **产品名称** | Clip2Text |
| **一句话描述** | 粘贴链接，即得文案 — 本地运行的语音文案提取工具 |
| **产品口号** | 粘贴链接，即得文案 |

### 目标用户群

- **内容创作者** — 需要整理短视频素材中的口播内容
- **行业研究者** — 收集短视频平台上的行业动态信息
- **文案策划** — 从短视频中获取灵感和素材
- **普通用户** — 收藏有价值的视频内容，方便后续查阅

### 核心价值主张

| 价值 | 说明 |
|------|------|
| 🆓 **免费开源** | 无需付费，代码完全开放 |
| 🔒 **本地运行** | 数据保存在本地，无需上传到第三方 |
| 📦 **批量处理** | 一次粘贴多条分享文本，后台逐个处理 |
| 🔗 **通用提取** | 不限平台，自动识别任意 http/https 链接 |
| 📥 **全文件下载** | 文案(.txt)、视频(.mp4)、音频(.wav)均可下载 |

---

## 3. 用户故事

### 3.1 核心场景

| ID | 角色 | 故事 | 优先级 |
|----|------|------|--------|
| US-01 | 普通用户 | 我想从 App 复制分享文本（含标题、作者、链接和乱码），直接粘贴进来就能提取文案 | P0 |
| US-02 | 内容创作者 | 我想一次粘贴多条分享文本，批量提取文案 | P0 |
| US-03 | 普通用户 | 我想在浏览器中实时看到处理进度 | P0 |
| US-04 | 普通用户 | 处理完成后，我想在线预览文案内容 | P0 |
| US-05 | 普通用户 | 我想将文案下载为 .txt 文件 | P0 |
| US-06 | 内容创作者 | 我想一次打包下载所有文案 | P1 |
| US-11 | 普通用户 | 我想下载原始视频文件和提取的音频文件 | P1 |

### 3.2 异常场景

| ID | 角色 | 故事 | 优先级 |
|----|------|------|--------|
| US-07 | 普通用户 | 如果我粘贴的内容中不包含链接，希望明确提示"未识别到链接" | P0 |
| US-08 | 普通用户 | 如果视频没有语音，希望提示"未检测到语音" | P1 |
| US-09 | 普通用户 | 如果网络超时或下载失败，希望提示错误原因 | P0 |
| US-10 | 普通用户 | 如果视频太长（>30分钟），希望提示可能耗时较长 | P2 |

---

## 4. 功能需求

### 4.1 模块列表

| 编号 | 模块名称 | 描述 | US 关联 | 优先级 |
|------|---------|------|---------|--------|
| FR-01 | 分享文本输入 | 多行文本框粘贴分享文本，实时预览识别结果 | US-01 | P0 ✅ |
| FR-02 | 任务提交 | 创建处理任务，返回唯一 task_id | US-01 | P0 ✅ |
| FR-03 | 通用链接提取 | 自动识别任意 http/https URL，不限平台 | US-01, US-07 | P0 ✅ |
| FR-04 | 链接解析 | 用 yt-dlp 解析链接，获取视频元信息 | FR-03 下游 | P0 ✅ |
| FR-05 | 视频下载 | 下载视频文件到本地 | FR-04 下游 | P0 ✅ |
| FR-06 | 音频提取 | ffmpeg 提取音频（16kHz, mono, WAV） | FR-05 下游 | P0 ✅ |
| FR-07 | 语音识别 | Whisper 模型将音频转为文字 | FR-06 下游 | P0 ✅ |
| FR-08 | 错误修正 | 常见同音/近音错误自动修正 + 繁转简 | FR-07 下游 | P0 ✅ |
| FR-09 | 进度查询 | 轮询查询每个链接的处理状态 | US-03 | P0 ✅ |
| FR-10 | 文案预览 | 处理完成的文字在页面中展示 | US-04 | P0 ✅ |
| FR-11 | 单条下载 | 单个文案下载为 .txt | US-05 | P0 ✅ |
| FR-12 | 中间文件下载 | 视频、音频文件独立下载 | US-11 | P1 ✅ |
| FR-13 | 批量打包 | 全部文案打包为 .zip 下载 | US-06 | P1 ✅ |
| FR-14 | OCR 画面校对 | 从视频帧提取文字，交叉校正常见同音错误 | FR-07 下游 | P2 ✅ |
| FR-15 | 错误处理 | 链接无效、网络错误、识别失败等友好提示 | US-07, US-09 | P0 ✅ |

### 4.2 功能依赖关系

```
FR-01 (分享文本输入) ─→ FR-02 (任务提交)
                             │
                             ▼
                          FR-03 (通用链接提取)
                             │
                        ┌────┴────┐
                        ▼         ▼
                   提取成功    提取失败 → 标记错误
                        │
                        ▼
                     FR-04 (链接解析)
                        │
                        ▼
                     FR-05 (视频下载)
                        │
                        ▼
                     FR-06 (音频提取)
                        │
                        ▼
                     FR-07 (语音识别)
                        │
                        ├──→ FR-08 (错误修正 + 繁转简)
                        │
                        ├──→ FR-14 (OCR 画面校对)
                        │
                        ▼
                     FR-10 (文案预览) ─→ FR-11 (单条下载)
                                              │
                                              ▼
                                          FR-12 (中间文件下载)
                                              │
                                              ▼
                                          FR-13 (批量打包)

FR-09 (进度查询) ←──────────────────── 全程轮询 ────────────────────
```

### 4.3 链接提取策略

前端和后端实现相同的匹配策略（双端一致）：

1. **完整 http/https URL**（不限域名，不限平台）
   - 正则：`https?://[a-zA-Z0-9][-a-zA-Z0-9.]*[a-zA-Z0-9](?:/[^\s"'<>,，。！？；：)]*)?`
   - 覆盖抖音 `v.douyin.com`、B站 `bilibili.com`、YouTube `youtube.com` 等任意链接
   - 提取后去除尾部 `/`
2. **短编码模式**（`xxx:/`，排除常见协议名）
   - 匹配 `[a-zA-Z0-9_-]{3,16}:/`，拼为 `https://v.douyin.com/{code}/`
   - 黑名单过滤 `http/https/ftp/sftp/file/ws/wss/rtmp/rtsp/mms`
3. 以上均失败 → `None`

> **设计原则**：不限定平台，提取完整的 http/https URL 优先。短编码模式仅作为 Douyin 特有格式的后备。

### 4.4 语音纠错能力

Whisper 对中文语音识别存在系统性同音/近音错误，Clip2Text 内置多层纠错：

**第一层：常见错误修正字典**（`transcriber.py`）
- 专有名词：`Depthic→DeepSeek`, `G P T→GPT` 等
- 同音字：`比竟→毕竟`, `识比→势必`, `息统→系统` 等
- 多字短语：`多为拆解→多维拆解`, `命令识提问→指令式提问` 等
- 上下文敏感：`于自我批判→与自我批判`, `场景力→场景里`

**第二层：繁简转换**（`zhconv`）
- 输出始终为简体中文

**第三层：OCR 画面文字校对**（`ocr_corrector.py`）
- 每 20 秒提取一帧（最多 20 帧）
- EasyOCR（CRAFT 检测 + zh_sim_g2 识别）
- 模糊匹配替换（difflib ratio > 0.55）
- 模型缺失时静默跳过，不报错

---

## 5. 非功能需求

| 编号 | 类型 | 需求描述 | 状态 |
|------|------|---------|------|
| NFR-01 | 性能 | 单条链接 5 分钟内处理完成（CPU, 短视频） | ✅ 已验证 |
| NFR-02 | 可靠性 | 一条链接处理失败不影响其他链接 | ✅ 已验证 |
| NFR-03 | 可用性 | Web 页面响应 < 2s（不含后端处理） | ✅ 已验证 |
| NFR-04 | 兼容性 | Chrome, Edge, Firefox 最新版可用 | ✅ 已验证 |
| NFR-05 | 安全性 | 临时文件不暴露公网，仅通过 task_id 访问 | ✅ 已验证 |
| NFR-06 | 可维护性 | 核心 Pipeline 模块独立解耦 | ✅ 已验证 |
| NFR-07 | 代码质量 | 无硬编码平台域名，通用链接提取 | ✅ 已实现 |

---

## 6. 约束与限制

- **处理速度**：CPU 模式下，Whisper base 模型处理 1 分钟音频约需 30-60 秒
- **网络依赖**：需要访问视频 CDN 下载（取决于目标平台网络环境）
- **存储空间**：单个视频文件通常 10-50MB
- **平台反爬**：yt-dlp 依赖社区维护的 extractor，部分平台可能需要 cookie
- **语言限制**：Whisper 对中文普通话效果较好，方言和英文混合场景准确率可能下降
- **单次提交**：上限 20 条分享文本
- **OCR 依赖**：EasyOCR 首次需要下载模型（~100MB），模型缺失时静默跳过
- **耗时操作**：EasyOCR 初始化耗时较长（约 10-20 秒），仅在首次处理含视频文件的任务时触发

---

## 7. 系统架构

### 7.1 整体架构图

```
┌──────────────────────────────────────────────────────────┐
│                       用户浏览器                          │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ 首页 (输入)   │  │ 进度页 (轮询) │  │ 结果页 (预览)   │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬────────┘  │
└─────────┼─────────────────┼──────────────────┼────────────┘
          │ POST /tasks     │ GET /tasks/{id}  │ GET /files
          ▼                 ▼                  ▼
┌──────────────────────────────────────────────────────────┐
│                   FastAPI Web 服务                        │
│                                                           │
│  ┌───────────┐  ┌──────────────────────────────────────┐ │
│  │ 路由层     │  │        后台任务管道                    │ │
│  │ tasks.py  │▶│  ┌──────────┐ ┌──────┐ ┌──────────┐ │ │
│  │ files.py  │  │  │download  │ │audio │ │transcri  │ │ │
│  └───────────┘  │  │er.py     │ │.py   │ │ber.py    │ │ │
│                 │  └────┬─────┘ └──┬───┘ └────┬─────┘ │ │
│                 │       │          │          │       │ │
│                 │       ▼          ▼          ▼       │ │
│                 │  ┌──────────────────────────────┐   │ │
│                 │  │   Task Manager               │   │ │
│                 │  │   (内存 dict + 文件系统)      │   │ │
│                 │  └──────────────────────────────┘   │ │
│                 │       │          │          │       │ │
│                 │       ▼          ▼          ▼       │ │
│                 │  ┌──────────┐ ┌──────────┐         │ │
│                 │  │ocr_corr  │ │ zhconv   │         │ │
│                 │  │ector.py  │ │ 繁转简    │         │ │
│                 │  └──────────┘ └──────────┘         │ │
│                 └──────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────┐
│               外部依赖                         │
│  ┌───────────┐  ┌──────────┐  ┌────────────┐  │
│  │ yt-dlp    │  │ ffmpeg   │  │ Whisper    │  │
│  │ (视频下载) │  │ (音频提取)│  │ (语音识别) │  │
│  └───────────┘  └──────────┘  └────────────┘  │
│  ┌───────────┐  ┌──────────┐                  │
│  │ EasyOCR   │  │ zhconv   │                  │
│  │ (画面校对) │  │ (繁转简)  │                  │
│  └───────────┘  └──────────┘                  │
└───────────────────────────────────────────────┘
```

### 7.2 技术栈

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| **后端框架** | Python 3.14+ / FastAPI | 异步友好，天然适合 IO 密集型任务 |
| **异步任务** | BackgroundTasks (FastAPI 内置) | MVP 不引入 Celery/Redis |
| **视频下载** | yt-dlp | 内置多平台 extractor |
| **音频处理** | ffmpeg (via imageio-ffmpeg) | 行业标准，提取 + 重采样 |
| **语音识别** | openai-whisper (base) | 本地运行，中文尚可 |
| **OCR 校正** | EasyOCR (CRAFT) | 视频帧文字提取，交叉校对 |
| **文本纠错** | zhconv + 自定义修正字典 | 繁转简 + 同音词修正 |
| **前端** | Jinja2 / Bootstrap 5 | 服务端渲染，无构建工具链 |
| **任务状态** | 内存 dict + 文件系统 | MVP 级别，重启后丢失 |

### 7.3 暂不引入的技术

- ❌ 用户登录 / 鉴权系统
- ❌ 数据库持久化（文件系统足够 MVP）
- ❌ 历史记录管理
- ❌ 批量导出格式转换（仅输出纯文本）
- ❌ GPU 加速（CPU 推理优先）
- ❌ 多说话人区分（diarization）
- ❌ Docker 容器化（但结构已预留）

---

## 8. 数据模型设计

### 8.1 Task（任务）

```python
class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class Task:
    id: str                    # UUID (12 hex chars)
    status: TaskStatus
    created_at: datetime
    completed_at: datetime | None
    items: list[TaskItem]
    total_count: int
    completed_count: int
    failed_count: int
```

### 8.2 TaskItem（单条链接处理项）

```python
class ItemStatus(str, Enum):
    PENDING = "pending"
    EXTRACTING_URL = "extracting_url"
    PARSING = "parsing"
    DOWNLOADING = "downloading"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskItem:
    id: str                    # UUID (12 hex chars)
    task_id: str
    raw_text: str              # 原始分享文本
    url: str | None            # 提取出的链接
    status: ItemStatus
    progress: float            # 0.0 ~ 1.0
    video_title: str | None
    cover_url: str | None
    transcript: str | None     # 识别结果（纯文本）
    error: str | None
    created_at: datetime
    updated_at: datetime
```

---

## 9. API 接口设计

### 9.1 提交任务

```
POST /api/tasks
Content-Type: application/json

Request:
{
  "texts": [
    "0.02 复制打开抖音，看看【胡说老木丶的作品】DeepSeek最强提示词... https://v.douyin.com/YY4lbvaPHsU/ K@W.md OKJ:/ :2pm 11/01",
    "https://www.bilibili.com/video/BV1GJ411m789"
  ]
}

Response 201:
{
  "task_id": "a1b2c3d4e5f6",
  "status": "pending",
  "item_count": 2,
  "failed_extract": 0,
  "created_at": "2026-06-10T10:00:00Z"
}
```

### 9.2 查询任务状态

```
GET /api/tasks/{task_id}

Response 200:
{
  "task_id": "a1b2c3d4e5f6",
  "status": "running",
  "items": [
    {
      "id": "item-uuid-1",
      "raw_text": "0.02 复制打开抖音...",
      "url": "https://v.douyin.com/YY4lbvaPHsU/",
      "status": "transcribing",
      "progress": 0.7,
      "video_title": "DeepSeek最强提示词",
      "error": null
    },
    {
      "id": "item-uuid-2",
      "raw_text": "https://www.bilibili.com/video/BV1GJ411m789",
      "url": "https://www.bilibili.com/video/BV1GJ411m789",
      "status": "completed",
      "progress": 1.0,
      "video_title": "B站视频标题",
      "transcript": "今天我们来聊聊...",
      "error": null
    }
  ],
  "total_count": 2,
  "completed_count": 1,
  "failed_count": 0,
  "created_at": "2026-06-10T10:00:00Z"
}
```

### 9.3 下载文件（文案 / 视频 / 音频）

```
GET /api/files/{task_id}/{item_id}/transcript   → txt
GET /api/files/{task_id}/{item_id}/video        → mp4/webm/mkv
GET /api/files/{task_id}/{item_id}/audio        → wav
```

### 9.4 批量打包下载

```
GET /api/tasks/{task_id}/download → zip

响应头: Content-Disposition: attachment; filename="Clip2Text_文案_20260610.zip"
响应头: Content-Type: application/zip

临时 zip 文件在响应发送后由 BackgroundTasks 自动清理。
```

### 9.5 健康检查

```
GET /api/health

Response 200:
{
  "name": "Clip2Text",
  "status": "ok",
  "version": "0.3.0",
  "slogan": "粘贴链接，即得文案"
}
```

---

## 10. 前端页面设计

### 10.1 页面路由

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | 首页 | 分享文本输入 + 实时链接预览 |
| `/tasks/{task_id}` | 任务进度/结果页 | 进度轮询 + 结果预览 + 下载 |

### 10.2 首页

**布局**：单栏居中（col-lg-8）

- 标题：📋 粘贴分享链接
- 文本框：多行 textarea，实时触发 URL 提取预览
- 预览区：每行显示 ✅ 识别成功（含链接） / ⚠️ 未识别到链接
- 提交按钮：🔗 开始提取，仅存在有效链接时可用
- 使用说明：四步引导

**交互逻辑**：
- `input` 事件 → `extractUrls()` → 更新预览区和计数
- 未识别行标记 ⚠️，不参与提交
- 提交后跳转到 `/tasks/{task_id}`

### 10.3 任务进度/结果页

**布局**：卡片列表

- 顶部：任务状态 Badge（处理中/已完成/部分失败）+ 进度计数
- 每个链接一个卡片，展示：
  - 原始文本摘要（60 字截断）
  - 提取的链接（蓝色小字）
  - 视频标题（若有）
  - 进度条 + 状态标签
  - 错误信息（红色 alert）
  - 文案预览（200 字截断，滚动）
  - 完成后的下载按钮：📥 文案.txt / 🎬 视频.mp4 / 🎵 音频.wav
- 底部：📦 全部打包下载按钮（全部完成后显示）

**轮询**：每 3 秒 GET `/api/tasks/{task_id}`，全部完成/失败后停止。

---

## 11. 错误处理策略

### 11.1 错误分类

| 错误类型 | 示例 | 前端表现 | 后端处理 |
|---------|------|---------|---------|
| 输入校验 | 空内容、超出 20 条 | Alert 弹窗提示 | 返回 422 |
| URL 提取失败 | 文本无链接 | 该行 ⚠️ 标记，不提交 | 标记 FAILED |
| 链接解析失败 | 链接过期、无法访问 | 卡片 ❌ 显示原因 | 继续处理其他 |
| 下载失败 | 网络超时、文件不存在 | 卡片 ❌ 显示原因 | 继续处理其他 |
| 识别失败 | 音频无声 | 卡片 ❌ 显示原因 | 继续处理其他 |
| OCR 失败 | 模型缺失 | 静默跳过（不阻塞） | 日志记录 warning |

### 11.2 文件清理

- 临时 zip 文件 → BackgroundTasks 响应完成后删除
- 视频/音频源文件 → 处理后 `shutil.move` 到 transcripts 目录（非 copy，不累积）
- 数据目录 → 目前手动清理，后续可加定时任务

---

## 12. 数据流图

### 12.1 提交流程

```
用户粘贴分享文本（每行一条）
  → 前端实时解析每行的 URL
  → 展示识别结果（提取到的链接 / 未识别行）
  → 用户确认后提交
  → POST /api/tasks (发送 texts 数组)
  → 后端对每条 text 执行 URL 提取
     → 提取成功 → 创建 TaskItem（含 url）
     → 提取失败 → 标记 FAILED + error
  → 创建 Task (status: pending)
  → 返回 task_id → 前端跳转到 /tasks/{task_id}
  → 后台异步处理:
     → 对每个成功提取的 URL:
        1. yt-dlp 解析链接 → 获取标题和元信息
        2. 下载视频文件
        3. ffmpeg 提取音频
        4. Whisper 语音识别
        5. 修正字典纠错
        6. 繁转简
        7. OCR 画面文字校对（若模型可用）
        8. 保存文案/视频/音频到 transcripts 目录
        9. 标记 COMPLETED / FAILED
```

### 12.2 URL 提取逻辑

```
输入: 任意分享文本（字符串）
输出: 提取到的 URL | None

策略（按优先级）:
  1. 正则匹配 https?://... 任意 http/https URL ← 不限平台
  2. 短编码模式 [a-zA-Z0-9_-]{3,16}:/ → v.douyin.com/xxx
  3. 以上均失败 → None
```

### 12.3 进度查询流程

```
前端 /tasks/{task_id} 页面加载
  → GET /api/tasks/{task_id}
  → 渲染当前状态
  → 如果还有未完成: setTimeout(3000) 继续轮询
  → 如果全部完成: 停止轮询，显示下载按钮
```

---

## 13. 项目目录结构

```
Clip2Text/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI 入口 + 页面路由
│   │   ├── config.py               # 配置管理
│   │   ├── utils.py                # 工具函数 (safe_filename)
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── tasks.py            # 任务 API + 批量下载
│   │   │   └── files.py            # 文件下载 API
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── url_extractor.py    # 通用链接提取（不限平台）
│   │   │   ├── downloader.py       # yt-dlp 解析 + 下载
│   │   │   ├── audio.py            # ffmpeg 音频提取
│   │   │   ├── transcriber.py      # Whisper 语音识别 + 纠错
│   │   │   ├── ocr_corrector.py    # EasyOCR 视频帧文字校对
│   │   │   └── task_manager.py     # 任务状态管理（内存）
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── schemas.py          # Pydantic 数据模型
│   │   └── templates/
│   │       ├── base.html           # 基础布局
│   │       ├── index.html          # 首页（输入）
│   │       └── task_detail.html    # 任务详情页
│   └── requirements.txt
├── data/                           # 运行时数据
│   ├── downloads/                  # 视频临时
│   ├── audio/                      # 音频临时
│   └── transcripts/                # 最终文案 + 视频 + 音频
├── docs/
│   └── PRD.md                      # 本需求文档
└── README.md
```

---

## 14. 验收状态

### 已完成（v0.3）

#### 核心 Pipeline
- [x] 通用链接提取（不限平台，双端正则一致）
- [x] yt-dlp 链接解析 + 视频下载
- [x] ffmpeg 音频提取（16kHz mono WAV）
- [x] Whisper 语音识别（base 模型，CPU）
- [x] 常见错误修正字典（~30 组同音/近音词）
- [x] 繁简自动转换（zhconv）
- [x] OCR 画面文字校对（EasyOCR CRAFT，模型缺失时静默跳过）

#### API
- [x] `POST /api/tasks` — 提交任务
- [x] `GET /api/tasks/{id}` — 查询状态
- [x] `GET /api/files/{tid}/{iid}/transcript` — 下载文案
- [x] `GET /api/files/{tid}/{iid}/video` — 下载视频
- [x] `GET /api/files/{tid}/{iid}/audio` — 下载音频
- [x] `GET /api/tasks/{id}/download` — 批量打包（自动清理临时文件）
- [x] `GET /api/health` — 健康检查

#### 前端
- [x] 首页：多行输入 + 实时 URL 预览 + 提交
- [x] 任务页：3 秒轮询 + 进度条 + 文案预览 + 下载按钮
- [x] 错误状态视觉反馈（⚠️ / ❌ / 🚫）
- [x] 批量打包按钮（任务完成后显示）

#### 代码质量
- [x] 无硬编码平台域名（通用链接匹配）
- [x] 重复函数消除（safe_filename → utils.py）
- [x] 临时文件响应后清理
- [x] 视频/音频文件 copy2 → move，消除目录累积
- [x] downloader 精确文件匹配（按修改时间排序）
- [x] 未用导入清理

### 未完成（后续版本）

- [ ] Docker 容器化
- [ ] 数据库持久化（当前内存重启丢失）
- [ ] 历史记录管理
- [ ] GPU 加速推理
- [ ] SRT/JSON 等导出格式
- [ ] 多说话人区分（diarization）
- [ ] 定时文件清理
- [ ] 移动端适配优化
