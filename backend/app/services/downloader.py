"""
Clip2Text — 视频下载服务

使用 yt-dlp 解析链接并下载视频。
"""
import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Optional

from app.config import DOWNLOADS_DIR
from app.services.retry import retry_async

logger = logging.getLogger(__name__)

# 网络错误类异常：值得重试
_RETRYABLE_EXCEPTIONS = (asyncio.TimeoutError, OSError, ConnectionError)


async def parse_video_info(url: str) -> Optional[dict]:
    """
    解析视频链接，获取视频元信息（标题、封面等）。

    网络超时等偶发性错误会自动重试一次。

    Args:
        url: 视频链接

    Returns:
        视频信息字典，包含 title, thumbnail 等；失败返回 None
    """
    cmd = [
        "python", "-m", "yt_dlp",
        "--dump-json",
        "--no-download",
        url,
    ]

    async def _do_parse():
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

        if proc.returncode != 0:
            err = stderr.decode(errors="ignore")[:200]
            raise IOError(f"yt-dlp parse failed (code {proc.returncode}): {err}")

        data = json.loads(stdout.decode(errors="ignore"))
        return {
            "title": data.get("title", ""),
            "thumbnail": data.get("thumbnail"),
            "duration": data.get("duration"),
            "extractor": data.get("extractor", ""),
        }

    try:
        return await retry_async(
            lambda: _do_parse(),
            max_retries=3,
            retry_delay=5.0,
            exceptions=_RETRYABLE_EXCEPTIONS,
        )
    except Exception as e:
        err_msg = str(e)[:200]
        logger.error(f"yt-dlp parse error (all retries exhausted): {err_msg}")
        return None


async def download_video(url: str, output_dir: Optional[Path] = None) -> Optional[Path]:
    """
    下载视频到本地。

    网络超时等偶发性错误会自动重试一次。

    Args:
        url: 视频链接
        output_dir: 输出目录，默认使用 DOWNLOADS_DIR

    Returns:
        下载视频的文件路径，失败返回 None
    """
    out_dir = output_dir or DOWNLOADS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    output_template = str(out_dir / "%(id)s.%(ext)s")

    cmd = [
        "python", "-m", "yt_dlp",
        "-f", "best[ext=mp4]/best",
        "-o", output_template,
        "--no-playlist",
        "--no-warnings",
        url,
    ]

    async def _do_download():
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

        if proc.returncode != 0:
            err = stderr.decode(errors="ignore")[:300]
            raise IOError(f"yt-dlp download failed (code {proc.returncode}): {err}")

        out_text = stdout.decode(errors="ignore")
        id_match = re.search(r"\[download\] Destination: (.+)", out_text)
        if id_match:
            path = Path(id_match.group(1).strip())
            if path.exists():
                return path

        # 兜底：找最新匹配后缀的文件
        candidates = sorted(
            [f for f in out_dir.iterdir() if f.is_file() and f.suffix in (".mp4", ".webm", ".mkv")],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return candidates[0]

        raise IOError("下载完成但未找到输出文件")

    try:
        return await retry_async(
            lambda: _do_download(),
            max_retries=2,
            retry_delay=5.0,
            exceptions=_RETRYABLE_EXCEPTIONS,
        )
    except Exception as e:
        logger.error(f"yt-dlp download error (all retries exhausted): {e}")
        return None
