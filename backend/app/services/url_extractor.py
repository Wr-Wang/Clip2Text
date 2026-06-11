"""
Clip2Text — 通用链接提取引擎

从用户粘贴的分享文本中自动提取视频/文章链接。
不限定域名，支持任意平台链接。
"""
import re
from typing import Optional

# 短编码前缀黑名单（排除常见协议名称误匹配）
_SHORT_CODE_BLACKLIST = frozenset({
    'http', 'https', 'ftp', 'sftp', 'file', 'ws', 'wss',
    'rtmp', 'rtsp', 'mms', 'ldap', 'ldaps',
})


def extract_url(text: str) -> Optional[str]:
    """
    从分享文本中提取视频链接。

    提取策略（按优先级）：
    1. 完整 http/https URL（不限域名）
    2. 纯短编码模式 xxx:/ （不限平台）

    Args:
        text: 分享文本（用户粘贴的整段内容）

    Returns:
        提取到的 URL，未找到返回 None
    """
    if not text or not text.strip():
        return None

    # 策略 1：完整 HTTP(s) URL（不限域名，不限平台）
    m = re.search(r'https?://[a-zA-Z0-9][-a-zA-Z0-9.]*[a-zA-Z0-9](?:/[^\s"\'<>，、，。！？；：)]*)?', text)
    if m:
        url = m.group(0).rstrip('/')
        return url

    # 策略 2：短编码模式 xxx:/
    m = re.search(r'([a-zA-Z0-9_-]{3,16}):/', text)
    if m and m.group(1).lower() not in _SHORT_CODE_BLACKLIST:
        code = m.group(1)
        return f"https://v.douyin.com/{code}/"

    return None


def extract_urls_batch(texts: list[str]) -> list[tuple[str, Optional[str]]]:
    """
    批量提取 URL，返回 [(原始文本, 提取的 URL 或 None), ...]

    Args:
        texts: 多行分享文本列表

    Returns:
        (raw_text, url_or_None) 元组列表
    """
    return [(t, extract_url(t)) for t in texts]
