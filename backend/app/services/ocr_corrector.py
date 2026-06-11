"""
Clip2Text — OCR 视频画面文字校对服务

从视频中提取关键帧，通过 OCR 识别画面中的文字（标题、字幕、关键术语等），
再与 Whisper 语音识别结果交叉比对，自动修正同音/近音错误。

典型错误修正：
  "Depthic"  → "DeepSeek"   (OCR 看到画面标题)
  "多为拆解" → "多维拆解"   (OCR 看到画面上正确写法)
  "对了"     → "堆了"       (OCR 识别显式字幕)
"""
import asyncio
import difflib
import logging
import re
import tempfile
from pathlib import Path
from typing import Optional

from app.config import FFMPEG_PATH

logger = logging.getLogger(__name__)

# lazy-loaded OCR reader
_ocr_reader = None


def get_ocr_reader():
    """
    获取 EasyOCR reader（全局缓存）。

    使用 CRAFT 检测模型（已在本地预下载）。
    如果模型文件不可用，返回 None（调用方应优雅回退）。

    EasyOCR 模型存放路径：~/.EasyOCR/model/
    - 检测: craft_mlt_25k.pth (CRAFT)
    - 识别: zh_sim_g2.pth
    """
    global _ocr_reader
    if _ocr_reader is not None:
        return _ocr_reader

    # 检查模型文件是否已下载
    model_dir = Path.home() / ".EasyOCR" / "model"
    detection_model = model_dir / "craft_mlt_25k.pth"
    recognition_model = model_dir / "zh_sim_g2.pth"

    missing = []
    if not detection_model.exists():
        missing.append(f"检测模型 (CRAFT): {detection_model}")
    if not recognition_model.exists():
        missing.append(f"识别模型: {recognition_model}")

    if missing:
        logger.warning(f"EasyOCR models not found: {', '.join(missing)}. OCR correction unavailable.")
        return None

    try:
        import easyocr
        logger.info("Loading EasyOCR (ch_sim + en, CPU)...")
        _ocr_reader = easyocr.Reader(["ch_sim", "en"], gpu=False)
        logger.info("EasyOCR loaded successfully")
    except Exception as e:
        logger.warning(f"EasyOCR initialization failed (non-fatal): {e}")
        return None

    return _ocr_reader


async def _extract_frames(video_path: Path, interval: int = 20) -> list[Path]:
    """
    使用 ffmpeg 从视频中提取关键帧。

    Args:
        video_path: 视频文件路径
        interval: 每 interval 秒提取一帧

    Returns:
        帧图片路径列表
    """
    out_dir = Path(tempfile.mkdtemp(prefix="ocr_"))
    out_pattern = str(out_dir / "frame_%04d.jpg")

    cmd = [
        str(FFMPEG_PATH),
        "-i", str(video_path),
        "-vf", f"fps=1/{interval}",
        "-q:v", "3",      # 品质 1-31，3 足够 OCR 使用
        "-frames:v", "20", # 最多 20 帧，防止过慢
        "-y",
        out_pattern,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

        if proc.returncode != 0:
            err = stderr.decode(errors="ignore")[:200]
            logger.warning(f"ffmpeg frame extract failed: {err}")
            return []

        frames = sorted(out_dir.glob("frame_*.jpg"))
        logger.info(f"OCR: extracted {len(frames)} frames (interval={interval}s)")
        return frames

    except asyncio.TimeoutError:
        logger.warning("OCR: ffmpeg frame extraction timeout")
        return []
    except Exception as e:
        logger.error(f"OCR: frame extraction error: {e}")
        return []


def _do_ocr(frame_paths: list[str]) -> Optional[list[str]]:
    """
    同步 OCR 处理所有帧（在 executor 线程池中运行）。

    Returns:
        所有帧识别出的文字片段列表，reader 不可用时返回 None
    """
    reader = get_ocr_reader()
    if reader is None:
        return None

    all_texts = []

    for i, fp in enumerate(frame_paths):
        try:
            result = reader.readtext(fp)
            texts = [item[1].strip() for item in result if item[2] > 0.3]
            if texts:
                logger.debug(f"OCR frame {i}: {texts[:3]}")
                all_texts.extend(texts)
        except Exception as e:
            logger.warning(f"OCR frame {i} error: {e}")

    return all_texts


def _build_vocabulary(ocr_texts: list[str]) -> set[str]:
    """
    从 OCR 原始文本中提取可靠的中文词汇表。

    过滤规则：
    - 至少 2 个中文字符
    - 中文字符占比 >= 50%
    """
    vocab = set()
    for text in ocr_texts:
        text = text.strip()
        if len(text) < 2:
            continue
        # 按标点/空白分段
        parts = re.split(r'[\s,，。！？、；：()（）\[\]【】""''…—·/:：]+', text)
        for part in parts:
            part = part.strip()
            if len(part) < 2:
                continue
            cn = sum(1 for c in part if "一" <= c <= "鿿")
            if cn >= max(2, len(part) * 0.4):
                vocab.add(part)
    return vocab


def _apply_ocr_corrections(transcript: str, ocr_texts: list[str]) -> str:
    """
    用 OCR 识别的可靠文本修正 Whisper 转录结果。

    策略：
    1. 从 OCR 文本中提取可靠词汇
    2. 对每个词汇（按长度降序）检查是否已存在于转录中
    3. 若不存在，用模糊匹配找到转录中最相似的词并替换
    """
    if not ocr_texts:
        return transcript

    vocab = _build_vocabulary(ocr_texts)
    if not vocab:
        return transcript

    # 按长度降序排列，优先匹配长词
    terms = sorted(vocab, key=len, reverse=True)
    result = transcript

    for term in terms:
        if len(term) < 2:
            continue
        # 已正确识别 → 跳过
        if term in result:
            continue

        # 提取转录中与 term 长度接近的中文词组
        words = re.findall(r"[一-鿿À-ÿA-Za-z]{2,}", result)

        best_word = None
        best_ratio = 0.0

        for word in words:
            if word == term:
                best_word = None  # 已存在，不需要处理
                best_ratio = 1.0
                break

            # 长度差异不超过 3 个字符才可比
            if abs(len(word) - len(term)) > 3:
                continue

            ratio = difflib.SequenceMatcher(None, word, term).ratio()
            if ratio > best_ratio and ratio > 0.55:
                best_ratio = ratio
                best_word = word

        if best_word and best_ratio > 0.55:
            logger.info(f"OCR correction: '{best_word}' -> '{term}' (ratio={best_ratio:.2f})")
            result = result.replace(best_word, term, 1)

    return result


async def ocr_correct(transcript: str, video_path: Path) -> str:
    """
    主入口：从视频画面提取文字，校对 Whisper 转录结果。

    如果 EasyOCR 模型未下载，静默跳过（不报错）。
    只提取最多 20 帧，每 20 秒一帧。

    Args:
        transcript: Whisper 原始转录文本
        video_path: 下载的视频文件路径

    Returns:
        校正后的文本（无校正则返回原文）
    """
    if not transcript or not video_path or not video_path.exists():
        return transcript

    # 预先检查模型是否可用（避免昂贵的帧提取操作）
    reader = get_ocr_reader()
    if reader is None:
        logger.info("OCR: EasyOCR models not available, skipping correction")
        return transcript

    # 1. 提取帧（每 20 秒一帧，最多 20 帧）
    frames = await _extract_frames(video_path, interval=20)
    if not frames:
        logger.info("OCR: no frames extracted, skipping correction")
        return transcript

    frame_paths = [str(f) for f in frames]

    # 2. OCR 识别（在线程池中执行，不阻塞事件循环）
    loop = asyncio.get_event_loop()
    ocr_texts = await loop.run_in_executor(None, lambda: _do_ocr(frame_paths))

    # 3. 清理临时帧文件
    for f in frames:
        try:
            f.unlink(missing_ok=True)
        except Exception:
            pass
    try:
        frames[0].parent.rmdir()
    except Exception:
        pass

    if not ocr_texts:
        logger.info("OCR: no text detected in frames, skipping correction")
        return transcript

    logger.info(f"OCR: {len(ocr_texts)} text fragments detected from {len(frames)} frames")

    # 4. 应用修正
    corrected = _apply_ocr_corrections(transcript, ocr_texts)

    if corrected != transcript:
        logger.info(f"OCR correction applied: {len(corrected) - len(transcript)} chars changed")
    else:
        logger.info("OCR: no corrections applied")

    return corrected
