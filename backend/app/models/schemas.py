"""
Clip2Text — Pydantic 数据模型
"""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ItemStatus(str, Enum):
    """单条链接处理状态"""
    PENDING = "pending"
    EXTRACTING_URL = "extracting_url"       # 从分享文本提取 URL 中
    PARSING = "parsing"                     # 解析视频信息中
    DOWNLOADING = "downloading"             # 下载视频中
    EXTRACTING_AUDIO = "extracting_audio"   # 提取音频中
    TRANSCRIBING = "transcribing"           # 语音识别中
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(str, Enum):
    """整体任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskItem(BaseModel):
    """单条链接处理项"""
    id: str
    task_id: str
    raw_text: str                           # 原始分享文本
    url: Optional[str] = None               # 提取出的视频链接
    status: ItemStatus = ItemStatus.PENDING
    progress: float = 0.0                   # 0.0 ~ 1.0
    video_title: Optional[str] = None       # 视频标题
    cover_url: Optional[str] = None         # 视频封面 URL
    transcript: Optional[str] = None        # 识别结果（纯文本）
    error: Optional[str] = None             # 错误信息
    timing: dict[str, float] = {}           # 各步骤耗时（秒），如 {"parsing": 3.2, "downloading": 8.5}
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class Task(BaseModel):
    """任务"""
    id: str
    status: TaskStatus = TaskStatus.PENDING
    items: list[TaskItem] = []
    total_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


# ------ API 请求/响应模型 ------


class TaskCreateRequest(BaseModel):
    """提交任务请求"""
    texts: list[str] = Field(..., min_length=1, max_length=20)


class TaskCreateResponse(BaseModel):
    """提交任务响应"""
    task_id: str
    status: TaskStatus
    item_count: int
    failed_extract: int = 0
    created_at: datetime


class TaskItemResponse(BaseModel):
    """单条处理项响应"""
    id: str
    raw_text: str
    url: Optional[str] = None
    status: ItemStatus
    progress: float
    video_title: Optional[str] = None
    transcript: Optional[str] = None
    error: Optional[str] = None
    timing: dict[str, float] = {}


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    status: TaskStatus
    items: list[TaskItemResponse]
    total_count: int
    completed_count: int
    failed_count: int
    created_at: datetime


class ErrorResponse(BaseModel):
    """错误响应"""
    error: dict
