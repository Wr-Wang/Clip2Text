"""
Clip2Text — 任务 API 路由

处理任务的提交、状态查询和后台异步处理。
"""
import asyncio
import logging
import shutil
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

from app.models.schemas import (
    TaskCreateRequest, TaskCreateResponse, TaskStatusResponse,
    TaskItemResponse, TaskStatus, ItemStatus,
)
from app.services.task_manager import task_manager
from app.services.url_extractor import extract_url
from app.services.downloader import parse_video_info, download_video
from app.services.audio import extract_audio
from app.services.transcriber import transcribe
from zhconv import convert as to_simplified
from app.config import TRANSCRIPTS_DIR, DOWNLOADS_DIR, AUDIO_DIR
from app.utils import safe_filename

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["tasks"])


def _now() -> float:
    """秒级时间戳，用于步骤计时"""
    return time.monotonic()


@router.post("/tasks", response_model=TaskCreateResponse, status_code=201)
async def create_task(request: TaskCreateRequest, background_tasks: BackgroundTasks):
    """
    提交任务：接收多行分享文本，后台异步处理。
    """
    # 去重
    texts = list(dict.fromkeys(t.strip() for t in request.texts if t.strip()))
    if not texts:
        raise HTTPException(status_code=422, detail={
            "code": "EMPTY_TEXTS",
            "message": "没有有效的分享文本",
        })
    if len(texts) > 20:
        raise HTTPException(status_code=422, detail={
            "code": "TOO_MANY_TEXTS",
            "message": "单次最多提交 20 条分享文本",
        })

    task = task_manager.create_task(texts)

    # 后台处理
    background_tasks.add_task(process_task, task.id)

    failed_extract = 0
    # 立即尝试提取 URL，标记前端可见
    for item in task.items:
        url = extract_url(item.raw_text)
        if url:
            task_manager.update_item(task.id, item.id, url=url)
        else:
            task_manager.set_item_progress(
                task.id, item.id,
                status=ItemStatus.FAILED,
                progress=0.0,
                error="未识别到有效链接",
            )
            failed_extract += 1

    task_manager.update_task_status(task.id)

    return TaskCreateResponse(
        task_id=task.id,
        status=task.status,
        item_count=len(texts),
        failed_extract=failed_extract,
        created_at=task.created_at,
    )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """查询任务状态"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail={
            "code": "TASK_NOT_FOUND",
            "message": f"任务 {task_id} 不存在",
        })

    return TaskStatusResponse(
        task_id=task.id,
        status=task.status,
        items=[
            TaskItemResponse(
                id=item.id,
                raw_text=item.raw_text[:200],  # 截取展示
                url=item.url,
                status=item.status,
                progress=round(item.progress, 2),
                video_title=item.video_title,
                transcript=item.transcript[:500] if item.transcript else None,
                error=item.error,
                timing=item.timing,
            )
            for item in task.items
        ],
        total_count=task.total_count,
        completed_count=task.completed_count,
        failed_count=task.failed_count,
        created_at=task.created_at,
    )


# ---------- 批量下载 ----------


@router.get("/tasks/{task_id}/download")
async def batch_download(task_id: str, background_tasks: BackgroundTasks):
    """批量打包下载所有完成的文案"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    completed_items = [item for item in task.items if item.status == ItemStatus.COMPLETED]
    if not completed_items:
        raise HTTPException(status_code=400, detail="没有可下载的文案")

    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp_path = Path(tmp.name)

    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in completed_items:
                txt_path = TRANSCRIPTS_DIR / f"{item.id}.txt"
                if txt_path.exists():
                    zf.write(txt_path, safe_filename(item.video_title or item.id, "_文案.txt"))

                for ext in (".mp4", ".webm", ".mkv"):
                    vid_path = TRANSCRIPTS_DIR / f"{item.id}{ext}"
                    if vid_path.exists():
                        zf.write(vid_path, safe_filename(item.video_title or item.id, f"_视频{ext}"))
                        break

                aud_path = TRANSCRIPTS_DIR / f"{item.id}.wav"
                if aud_path.exists():
                    zf.write(aud_path, safe_filename(item.video_title or item.id, "_音频.wav"))

        tmp.close()

        # 响应发送后清理临时文件
        def _cleanup():
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
        background_tasks.add_task(_cleanup)

        date_str = datetime.now().strftime("%Y%m%d")
        return FileResponse(
            tmp_path,
            media_type="application/zip",
            filename=f"Clip2Text_文案_{date_str}.zip",
        )
    except Exception as e:
        logger.error(f"Batch download error: {e}")
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="打包下载失败")


# ---------- 后台处理 ----------


async def process_item(task_id: str, item_id: str):
    """处理单条链接"""
    item = task_manager.get_item(task_id, item_id)
    if not item:
        return

    url = item.url
    if not url:
        return

    logger.info(f"Processing item {item_id}: {url}")

    # 1. 解析视频信息
    task_manager.set_item_progress(task_id, item_id,
                                   status=ItemStatus.PARSING, progress=0.1)
    t0 = _now()
    info = await parse_video_info(url)
    task_manager.update_item_elapsed(task_id, item_id, "解析视频", _now() - t0)
    if info:
        task_manager.update_item(task_id, item_id,
                                 video_title=info.get("title"),
                                 cover_url=info.get("thumbnail"))
    else:
        task_manager.set_item_progress(task_id, item_id,
                                       status=ItemStatus.FAILED, progress=0.0,
                                       error="视频解析失败")
        return

    # 2. 下载视频
    task_manager.set_item_progress(task_id, item_id,
                                   status=ItemStatus.DOWNLOADING, progress=0.3)
    t0 = _now()
    video_path = await download_video(url)
    task_manager.update_item_elapsed(task_id, item_id, "下载视频", _now() - t0)
    if not video_path:
        task_manager.set_item_progress(task_id, item_id,
                                       status=ItemStatus.FAILED, progress=0.0,
                                       error="视频下载失败")
        return

    # 3. 提取音频
    task_manager.set_item_progress(task_id, item_id,
                                   status=ItemStatus.EXTRACTING_AUDIO, progress=0.5)
    t0 = _now()
    audio_path = await extract_audio(video_path)
    task_manager.update_item_elapsed(task_id, item_id, "提取音频", _now() - t0)
    if not audio_path:
        task_manager.set_item_progress(task_id, item_id,
                                       status=ItemStatus.FAILED, progress=0.0,
                                       error="音频提取失败")
        return

    # 4. 语音识别
    task_manager.set_item_progress(task_id, item_id,
                                   status=ItemStatus.TRANSCRIBING, progress=0.7)
    t0 = _now()
    text = await transcribe(audio_path)
    task_manager.update_item_elapsed(task_id, item_id, "语音识别", _now() - t0)
    if text:
        # 4.5 OCR 画面文字校对
        if video_path:
            try:
                from app.services.ocr_corrector import ocr_correct
                t0 = _now()
                corrected = await ocr_correct(text, video_path)
                task_manager.update_item_elapsed(task_id, item_id, "OCR校对", _now() - t0)
                if corrected != text:
                    logger.info(f"OCR correction applied for item {item_id}")
                    text = corrected
            except Exception as e:
                logger.warning(f"OCR correction failed (non-fatal): {e}")

        # 确保输出为简体中文（双重保障）
        text = to_simplified(text, "zh-cn")

        # 保存文案到文件
        title = (item.video_title or item.id)[:50]
        transcript_path = TRANSCRIPTS_DIR / f"{item.id}.txt"
        transcript_path.write_text(text, encoding="utf-8")

        # 将音频和视频移至 transcripts 目录（消除源目录累积）
        audio_target = TRANSCRIPTS_DIR / f"{item.id}.wav"
        if audio_path.exists() and not audio_target.exists():
            shutil.move(str(audio_path), str(audio_target))

        video_target = TRANSCRIPTS_DIR / f"{item.id}{video_path.suffix}"
        if video_path.exists() and not video_target.exists():
            shutil.move(str(video_path), str(video_target))

        task_manager.set_item_progress(task_id, item_id,
                                       status=ItemStatus.COMPLETED,
                                       progress=1.0,
                                       transcript=text)
    else:
        task_manager.set_item_progress(task_id, item_id,
                                       status=ItemStatus.FAILED, progress=0.0,
                                       error="未检测到语音或识别失败")


async def process_task(task_id: str):
    """后台处理整个任务"""
    task = task_manager.get_task(task_id)
    if not task:
        return

    logger.info(f"Starting task {task_id} with {len(task.items)} items")

    # 逐个处理（Promise 风格，彼此独立）
    for item in task.items:
        if item.url:  # 仅处理成功提取到 URL 的项
            await process_item(task_id, item.id)

    logger.info(f"Task {task_id} completed")
