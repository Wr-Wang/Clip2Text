"""
Clip2Text — 文件下载 API 路由

提供文案、视频、音频文件的下载。
"""
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.models.schemas import ItemStatus
from app.services.task_manager import task_manager
from app.config import TRANSCRIPTS_DIR
from app.utils import safe_filename

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/files", tags=["files"])


def _get_item_or_404(task_id: str, item_id: str):
    """获取任务项，不存在则 404"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    item = task_manager.get_item(task_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="任务项不存在")
    if item.status != ItemStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="任务项尚未完成")
    return item


@router.get("/{task_id}/{item_id}/transcript")
async def download_transcript(task_id: str, item_id: str):
    """下载文案 .txt 文件"""
    item = _get_item_or_404(task_id, item_id)
    filepath = TRANSCRIPTS_DIR / f"{item.id}.txt"
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="文案文件不存在")
    return FileResponse(
        filepath,
        media_type="text/plain; charset=utf-8",
        filename=safe_filename(item.video_title or item.id, "_文案.txt"),
    )


@router.get("/{task_id}/{item_id}/video")
async def download_video(task_id: str, item_id: str):
    """下载原始视频文件"""
    item = _get_item_or_404(task_id, item_id)
    for ext in (".mp4", ".webm", ".mkv"):
        filepath = TRANSCRIPTS_DIR / f"{item.id}{ext}"
        if filepath.exists():
            return FileResponse(
                filepath,
                media_type=f"video/{ext[1:]}",
                filename=safe_filename(item.video_title or item.id, f"_视频{ext}"),
            )
    raise HTTPException(status_code=404, detail="视频文件不存在")


@router.get("/{task_id}/{item_id}/audio")
async def download_audio(task_id: str, item_id: str):
    """下载提取的音频文件"""
    item = _get_item_or_404(task_id, item_id)
    filepath = TRANSCRIPTS_DIR / f"{item.id}.wav"
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="音频文件不存在")
    return FileResponse(
        filepath,
        media_type="audio/wav",
        filename=safe_filename(item.video_title or item.id, "_音频.wav"),
    )


