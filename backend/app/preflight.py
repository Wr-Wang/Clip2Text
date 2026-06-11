"""
Clip2Text — 启动预检

在服务启动时检查所有外部依赖是否就绪。
不阻塞启动，仅记录报告供用户参考。
"""
import logging
import subprocess
import sys
from pathlib import Path

from app.config import (
    FFMPEG_PATH, WHISPER_MODEL_NAME,
    DOWNLOADS_DIR, AUDIO_DIR, TRANSCRIPTS_DIR,
    CORRECTIONS_PATH, DATA_DIR,
)

logger = logging.getLogger(__name__)


def _check_whisper_model() -> tuple[bool, str]:
    """检查 Whisper 模型是否已下载"""
    try:
        import whisper
        # whisper 的模型缓存路径
        import whisper._models as _wm
        model_path = _wm._get_available_model_downloads().get(WHISPER_MODEL_NAME)
        if model_path:
            return True, f"模型 {WHISPER_MODEL_NAME} 已就绪"
    except Exception:
        pass

    # 兜底：直接检查 huggingface 缓存目录
    whisper_cache = Path.home() / ".cache" / "whisper"
    if whisper_cache.exists():
        for f in whisper_cache.iterdir():
            if WHISPER_MODEL_NAME in f.name and f.suffix == ".pt":
                return True, f"模型 {WHISPER_MODEL_NAME} 已就绪 ({f.name})"

    return False, f"Whisper 模型 '{WHISPER_MODEL_NAME}' 未下载，首次转录时会自动下载 (~1GB)"


def _check_ffmpeg() -> tuple[bool, str]:
    """检查 ffmpeg 是否可用"""
    try:
        proc = subprocess.run(
            [str(FFMPEG_PATH), "-version"],
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode == 0:
            version = proc.stdout.splitlines()[0] if proc.stdout else "未知版本"
            return True, version
        return False, f"ffmpeg 返回错误码 {proc.returncode}"
    except FileNotFoundError:
        return False, f"ffmpeg 未找到 (查找路径: {FFMPEG_PATH})"
    except Exception as e:
        return False, f"ffmpeg 检查失败: {e}"


def _check_easyocr_models() -> tuple[bool, str]:
    """检查 EasyOCR 模型文件是否存在"""
    model_dir = Path.home() / ".EasyOCR" / "model"
    detection = model_dir / "craft_mlt_25k.pth"
    recognition = model_dir / "zh_sim_g2.pth"

    ok, details = True, []
    if detection.exists():
        details.append(f"CRAFT 检测模型 ({detection.stat().st_size >> 20}MB)")
    else:
        details.append("CRAFT 检测模型 缺失")
        ok = False
    if recognition.exists():
        details.append(f"zh_sim_g2 识别模型 ({recognition.stat().st_size >> 20}MB)")
    else:
        details.append("zh_sim_g2 识别模型 缺失")
        ok = False

    if ok:
        return True, " | ".join(details)
    return False, " | ".join(details) + " — OCR 校对将跳过"


def _check_data_dirs() -> tuple[bool, str]:
    """检查数据目录是否存在且可写"""
    dirs = {
        "下载目录": DOWNLOADS_DIR,
        "音频目录": AUDIO_DIR,
        "文案目录": TRANSCRIPTS_DIR,
        "数据根目录": DATA_DIR,
    }
    ok = True
    details = []
    for name, d in dirs.items():
        try:
            d.mkdir(parents=True, exist_ok=True)
            test_file = d / ".clip2text_write_test"
            test_file.write_text("ok")
            test_file.unlink()
            details.append(f"{name} ✓")
        except Exception as e:
            details.append(f"{name} ✗ ({e})")
            ok = False
    return ok, " | ".join(details)


def _check_correction_file() -> tuple[bool, str]:
    """检查外部修正字典是否存在"""
    if CORRECTIONS_PATH.exists():
        size = CORRECTIONS_PATH.stat().st_size
        return True, f"已加载 ({size} bytes)"
    return False, f"文件不存在 ({CORRECTIONS_PATH})，将使用内置修正字典"


def run_preflight() -> dict:
    """
    执行全部预检，返回 {检查项: (是否通过, 详情)} 字典。
    不抛出异常，所有检查失败均记录为日志。
    """
    checks = {
        "数据目录": _check_data_dirs(),
        "FFmpeg": _check_ffmpeg(),
        "Whisper 模型": _check_whisper_model(),
        "EasyOCR 模型": _check_easyocr_models(),
        "外部修正字典": _check_correction_file(),
    }

    logger.info("=" * 50)
    logger.info("Clip2Text 启动预检报告")
    logger.info("=" * 50)
    all_ok = True
    for name, (ok, detail) in checks.items():
        status = "✅" if ok else "⚠️"
        logger.info(f"  {status} {name}: {detail}")
        if not ok:
            all_ok = False
    logger.info("=" * 50)
    if all_ok:
        logger.info("所有依赖检查通过")
    else:
        logger.info("部分依赖缺失（不影响启动，但对应功能不可用）")
    logger.info("=" * 50)

    return checks
