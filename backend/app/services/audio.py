"""
Clip2Text — 音频提取服务

使用 ffmpeg 从视频文件中提取音频（16kHz mono WAV）。
"""
import asyncio
import logging
from pathlib import Path
from typing import Optional

from app.config import FFMPEG_PATH, AUDIO_DIR

logger = logging.getLogger(__name__)


async def extract_audio(video_path: Path, output_dir: Optional[Path] = None) -> Optional[Path]:
    """
    从视频中提取音频。

    Args:
        video_path: 视频文件路径
        output_dir: 输出目录，默认使用 AUDIO_DIR

    Returns:
        提取的音频文件路径（.wav），失败返回 None
    """
    out_dir = output_dir or AUDIO_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    audio_path = out_dir / f"{video_path.stem}.wav"

    cmd = [
        str(FFMPEG_PATH),
        "-y",
        "-i", str(video_path),
        "-vn",                      # 不处理视频
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(audio_path),
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

        if proc.returncode != 0:
            err_msg = stderr.decode(errors='ignore')[:300]
            logger.warning(f"ffmpeg extract failed: {err_msg}")
            return None

        if audio_path.exists() and audio_path.stat().st_size > 0:
            logger.info(f"Audio extracted: {audio_path} ({audio_path.stat().st_size} bytes)")
            return audio_path

        return None

    except asyncio.TimeoutError:
        logger.warning(f"ffmpeg extract timeout: {video_path}")
        return None
    except Exception as e:
        logger.error(f"ffmpeg extract error: {e}")
        return None
