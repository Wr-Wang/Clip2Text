"""
Clip2Text — 工具函数
"""
from pathlib import Path


def safe_filename(title: str | None, suffix: str) -> str:
    """生成安全的文件名"""
    safe = "".join(c for c in (title or "文案") if c.isalnum() or c in " _-")
    return f"{safe[:50]}{suffix}"
