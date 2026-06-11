"""
Clip2Text — 配置管理
"""
import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/

# 数据目录
DATA_DIR = BASE_DIR.parent / "data"
DOWNLOADS_DIR = DATA_DIR / "downloads"
AUDIO_DIR = DATA_DIR / "audio"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"

# Whisper 配置
WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "base")  # tiny/base/small/medium
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")       # cpu / cuda

# FFmpeg 路径
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except (ImportError, RuntimeError):
    FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")

# 服务配置
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

# 文件清理
CLEANUP_AFTER_HOURS = int(os.getenv("CLEANUP_AFTER_HOURS", "24"))

# 外部修正字典路径（用户可编辑此文件添加自定义修正规则）
CORRECTIONS_PATH = DATA_DIR / "corrections.json"

# 确保数据目录存在
for d in [DOWNLOADS_DIR, AUDIO_DIR, TRANSCRIPTS_DIR, DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)
