"""
Clip2Text — 语音识别服务

使用本地 Whisper 模型将音频转为文字。
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

import whisper
from zhconv import convert as to_simplified

from app.config import WHISPER_MODEL_NAME, WHISPER_DEVICE, CORRECTIONS_PATH

logger = logging.getLogger(__name__)

# 全局单例模型（避免重复加载）
_model = None

# ---------- 内置修正字典（作为外部文件缺失时的兜底） ----------

_BUILTIN_CORRECTIONS = {
    # 专有名词
    "Depthic": "DeepSeek",
    "deepseek": "DeepSeek",
    "深度求索": "DeepSeek",
    "G P T": "GPT",
    "g p t": "GPT",
    "Chat G P T": "ChatGPT",
    # 常见同音/近音错误
    "识比": "势必",
    "比竟": "毕竟",
    "达升": "提升",
    "水转": "水准",
    "水準": "水准",
    "原比": "原本",
    "息统": "系统",
    "告识": "告诉",
    "调识": "调试",
    "主调": "逐条",
    "诊异": "缜密",
    "诊弥": "缜密",
    "平停无奇": "平平无奇",
    "平停": "平平",
    "层经": "曾经",
    "超见": "常见",
    # 多字短语
    "多为拆解": "多维拆解",
    "多维拆": "多维拆解",
    "识别式提问": "指令式提问",
    "指令式的提问": "指令式提问",
    "命令识提问": "指令式提问",
    "命令式提问": "指令式提问",
    "围度": "维度",
    "简难题": "解难题",
    "简难": "解难",
    "领与": "领域",
    "关建": "关键",
    # 上下文敏感
    "于自我批判": "与自我批判",
    "场景力": "场景里",
}

# ---------- 修正字典加载（优先外部文件，内置字典兜底） ----------


def _load_corrections() -> dict[str, str]:
    """
    从外部 JSON 文件加载修正字典。
    文件不存在或格式错误时回退到内置字典。
    外部文件支持按分类组织，加载时展开为扁平的 {错误→修正} 映射。
    """
    if not CORRECTIONS_PATH.exists():
        logger.info(f"外部修正字典不存在 ({CORRECTIONS_PATH})，使用内置字典")
        return dict(_BUILTIN_CORRECTIONS)

    try:
        raw = json.loads(CORRECTIONS_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("根对象不是 JSON 对象")

        corrections = {}
        categories = 0
        for key, value in raw.items():
            # 跳过注释字段（以下划线开头）
            if key.startswith("_"):
                continue
            if isinstance(value, dict):
                categories += 1
                for wrong, correct in value.items():
                    if wrong.startswith("_"):
                        continue
                    if isinstance(wrong, str) and isinstance(correct, str) and wrong.strip():
                        corrections[wrong] = correct
            elif isinstance(value, str) and key.strip():
                corrections[key] = value

        if not corrections:
            logger.warning(f"外部修正字典为空 ({CORRECTIONS_PATH})，使用内置字典")
            return dict(_BUILTIN_CORRECTIONS)

        logger.info(f"已加载外部修正字典: {categories} 个分类, {len(corrections)} 条规则")
        return corrections

    except Exception as e:
        logger.warning(f"外部修正字典加载失败: {e}，使用内置字典")
        return dict(_BUILTIN_CORRECTIONS)


# 模块级缓存：修正字典（首次调用时惰性加载）
_CORRECTIONS_CACHE: Optional[dict[str, str]] = None


def _get_corrections() -> dict[str, str]:
    """获取修正字典（惰性加载，全局缓存）"""
    global _CORRECTIONS_CACHE
    if _CORRECTIONS_CACHE is None:
        _CORRECTIONS_CACHE = _load_corrections()
    return _CORRECTIONS_CACHE


def reload_corrections():
    """
    重新加载修正字典（不重启服务）。
    编辑 data/corrections.json 后调用此函数即可使新规则生效。
    用法: from app.services.transcriber import reload_corrections; reload_corrections()
    """
    global _CORRECTIONS_CACHE
    _CORRECTIONS_CACHE = _load_corrections()


def _apply_corrections(text: str) -> str:
    """修正常见 Whisper 识别错误（使用当前加载的外部或内置字典）"""
    corrections = _get_corrections()
    for wrong, correct in corrections.items():
        text = text.replace(wrong, correct)
    return text


def _add_punctuation(text: str) -> str:
    """
    保守补充中文标点。

    - 不插入额外逗号（Whisper 自己输出的逗号已足够）
    - 确保段落正常结尾
    - 清理多余空格
    """
    text = text.strip()
    if not text:
        return text

    # 确保结尾有句号（仅当完全没有结尾标点时）
    if text[-1] not in "。！？.!?":
        text += "。"

    return text


def get_model():
    """获取或加载 Whisper 模型（惰性加载，全局缓存）"""
    global _model
    if _model is None:
        logger.info(f"Loading Whisper model: {WHISPER_MODEL_NAME} (device={WHISPER_DEVICE})")
        _model = whisper.load_model(WHISPER_MODEL_NAME, device=WHISPER_DEVICE)
        logger.info(f"Whisper model loaded: {WHISPER_MODEL_NAME}")
    return _model


async def transcribe(audio_path: Path) -> Optional[str]:
    """
    将音频文件转为文字。

    Whisper 的 transcribe 是同步阻塞操作，使用 run_in_executor
    在线程池中执行以防止阻塞事件循环。

    Args:
        audio_path: 音频文件路径（.wav）

    Returns:
        识别文本，失败返回 None
    """
    if not audio_path.exists():
        logger.error(f"Audio file not found: {audio_path}")
        return None

    if audio_path.stat().st_size == 0:
        logger.error(f"Audio file is empty: {audio_path}")
        return None

    try:
        model = get_model()

        # 鼓励 Whisper 输出标点，但不过度干预
        initial_prompt = "以下是普通话的句子，请使用标点符号分隔。"

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: model.transcribe(
                str(audio_path),
                language="zh",
                task="transcribe",
                fp16=False,
                initial_prompt=initial_prompt,
            )
        )

        # 从 segments 拼接文本，利用时间戳停顿（>1.0s）加句号
        segments = result.get("segments", [])
        if segments:
            text_parts = []
            prev_end = 0.0
            gap_threshold = 1.0  # 秒 - 停顿超过 1 秒才认为是句子边界

            for seg in segments:
                seg_text = seg.get("text", "").strip()
                if not seg_text:
                    continue

                seg_start = seg.get("start", 0)
                gap = seg_start - prev_end

                if text_parts and gap > gap_threshold:
                    last = text_parts[-1].rstrip("，,")
                    if last and last[-1] not in "。！？.!?":
                        text_parts[-1] = last + "。"

                text_parts.append(seg_text)
                prev_end = seg.get("end", 0)

            text = "".join(text_parts).strip()
        else:
            text = result.get("text", "").strip()

        if not text:
            logger.info("No speech detected in audio")
            return None

        # 修正常见识别错误（使用外部或内置修正字典）
        text = _apply_corrections(text)

        # 保守补充结尾标点
        text = _add_punctuation(text)

        # 繁转简（输出始终为简体中文）
        text = to_simplified(text, "zh-cn")

        logger.info(f"Transcription complete: {len(text)} chars")
        return text

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return None
