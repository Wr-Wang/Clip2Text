"""
Clip2Text — 任务状态管理器

管理 Task 和 TaskItem 的创建、更新和查询。
所有状态保存在内存中（MVP 级别），重启后丢失。
"""
import uuid
from datetime import datetime
from typing import Optional

from app.models.schemas import (
    Task, TaskItem, TaskStatus, ItemStatus,
)


class TaskManager:
    """任务状态管理器（内存存储）"""

    def __init__(self):
        self._tasks: dict[str, Task] = {}

    # ---------- Task CRUD ----------

    def create_task(self, texts: list[str]) -> Task:
        """创建新任务"""
        task_id = self._gen_id()
        now = datetime.now()

        items = []
        for text in texts:
            items.append(TaskItem(
                id=self._gen_id(),
                task_id=task_id,
                raw_text=text,
                status=ItemStatus.PENDING,
                created_at=now,
                updated_at=now,
            ))

        task = Task(
            id=task_id,
            status=TaskStatus.PENDING,
            items=items,
            total_count=len(items),
            created_at=now,
        )
        self._tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self._tasks.get(task_id)

    def update_task_status(self, task_id: str):
        """更新整体任务状态（根据子项状态计算）"""
        task = self._tasks.get(task_id)
        if not task:
            return

        statuses = [item.status for item in task.items]
        completed = sum(1 for s in statuses if s == ItemStatus.COMPLETED)
        failed = sum(1 for s in statuses if s == ItemStatus.FAILED)
        total = len(statuses)

        task.completed_count = completed
        task.failed_count = failed

        if completed + failed == total:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
        elif any(s in (ItemStatus.PENDING, ItemStatus.EXTRACTING_URL,
                       ItemStatus.PARSING, ItemStatus.DOWNLOADING,
                       ItemStatus.EXTRACTING_AUDIO, ItemStatus.TRANSCRIBING)
                 for s in statuses):
            task.status = TaskStatus.RUNNING
        else:
            task.status = TaskStatus.FAILED

    # ---------- Item CRUD ----------

    def get_item(self, task_id: str, item_id: str) -> Optional[TaskItem]:
        """获取任务中的单个处理项"""
        task = self._tasks.get(task_id)
        if not task:
            return None
        for item in task.items:
            if item.id == item_id:
                return item
        return None

    def update_item(self, task_id: str, item_id: str, **updates) -> Optional[TaskItem]:
        """更新处理项字段"""
        item = self.get_item(task_id, item_id)
        if not item:
            return None

        for key, value in updates.items():
            if hasattr(item, key):
                setattr(item, key, value)

        item.updated_at = datetime.now()
        self.update_task_status(task_id)
        return item

    def set_item_progress(self, task_id: str, item_id: str, status: ItemStatus,
                          progress: float, **extra) -> Optional[TaskItem]:
        """快捷方法：更新状态和进度"""
        return self.update_item(
            task_id, item_id,
            status=status,
            progress=progress,
            **extra,
        )

    def update_item_elapsed(self, task_id: str, item_id: str, step_name: str, elapsed: float) -> Optional[TaskItem]:
        """
        记录某步骤耗时（秒）到 item.timing 字典中。

        Args:
            task_id: 任务 ID
            item_id: 处理项 ID
            step_name: 步骤名称，如 "解析视频", "下载视频", "语音识别"
            elapsed: 该步骤耗时秒数
        """
        item = self.get_item(task_id, item_id)
        if not item:
            return None
        item.timing[step_name] = round(elapsed, 1)
        item.updated_at = datetime.now()
        return item

    # ---------- 清理 ----------

    def clear(self):
        """清空所有任务"""
        self._tasks.clear()

    # ---------- 辅助 ----------

    @staticmethod
    def _gen_id() -> str:
        return uuid.uuid4().hex[:12]


# 全局单例
task_manager = TaskManager()
