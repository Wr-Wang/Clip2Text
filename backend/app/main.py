"""
Clip2Text — FastAPI 应用入口
"""
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader
import uvicorn

from app.config import HOST, PORT

app = FastAPI(
    title="Clip2Text",
    description="粘贴链接，即得文案 — 分享链接语音文案提取工具",
    version="0.3.0",
)

# 启动预检：检查所有外部依赖
from app.preflight import run_preflight
run_preflight()

# 手动管理 Jinja2 环境，绕过 Starlette 缓存兼容性问题
_template_dir = Path(__file__).resolve().parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_template_dir)), auto_reload=True)
_jinja_env.cache = {}


def render(template_name: str, **context) -> str:
    """渲染 Jinja2 模板"""
    template = _jinja_env.get_template(template_name)
    return template.render(**context)


# ---------- 注册路由 ----------

from app.routers import tasks, files
app.include_router(tasks.router)
app.include_router(files.router)


# ---------- 健康检查 ----------


@app.get("/api/health")
async def health():
    return {"name": "Clip2Text", "status": "ok", "version": "0.3.0", "slogan": "粘贴链接，即得文案"}


# ---------- 页面路由 ----------


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页"""
    html = render("index.html", request=request)
    return HTMLResponse(html)


@app.get("/tasks/{task_id}", response_class=HTMLResponse)
async def task_page(request: Request, task_id: str):
    """任务详情页"""
    from app.services.task_manager import task_manager
    task = task_manager.get_task(task_id)
    if not task:
        return HTMLResponse("任务不存在", status_code=404)
    html = render("task_detail.html", request=request, task_id=task_id)
    return HTMLResponse(html)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
