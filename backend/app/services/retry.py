"""
Clip2Text — 重试工具

提供异步重试语义，用于网络操作等偶发性失败场景。
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


async def retry_async(coro_factory, max_retries=1, retry_delay=2.0, exceptions=(Exception,)):
    """
    异步重试包装器：对 coro_factory 返回的协程执行重试。

    Args:
        coro_factory: 无参数可调用对象，每次调用返回一个新协程
        max_retries: 最大重试次数（不含首次尝试）
        retry_delay: 重试间隔秒数
        exceptions: 需要重试的异常类型元组

    Returns:
        协程的返回值

    Raises:
        最后一次尝试的异常（重试耗尽后）
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except exceptions as e:
            last_exc = e
            if attempt < max_retries:
                logger.warning(
                    "操作失败 (尝试 %d/%d): %s. %s 秒后重试...",
                    attempt + 1, max_retries + 1, e, retry_delay,
                )
                await asyncio.sleep(retry_delay)
            else:
                logger.error("操作失败 (%d 次尝试均失败): %s", max_retries + 1, e)

    raise last_exc
