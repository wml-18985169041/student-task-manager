"""
学生任务管理系统 - FastAPI 后端
"""
import os
import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional

# ── 配置（从环境变量读取，带默认值） ─────────────────────────────
HOST = os.getenv("TASK_APP_HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", os.getenv("TASK_APP_PORT", "8080")))
DB_PATH = os.getenv("TASK_DB_PATH", "student_tasks.db")
REMIND_HOURS = int(os.getenv("TASK_REMIND_HOURS", "24"))

app = FastAPI(title="学生任务管理系统", version="1.0.0")

# CORS — 允许任意来源访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 数据库 ───────────────────────────────────────────────────────
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL,
                description TEXT    DEFAULT '',
                course_name TEXT    DEFAULT '',
                task_type   TEXT    DEFAULT '其他',
                priority    TEXT    DEFAULT '中',
                deadline    TEXT    NOT NULL,
                status      TEXT    DEFAULT '未开始',
                created_at  TEXT    DEFAULT (datetime('now', 'localtime')),
                updated_at  TEXT    DEFAULT (datetime('now', 'localtime'))
            )
        """)


init_db()


# ── Pydantic 模型 ────────────────────────────────────────────────
class TaskCreate(BaseModel):
    title: str
    description: str = ""
    course_name: str = ""
    task_type: str = "其他"       # 作业 / 考试 / 实验 / 其他
    priority: str = "中"          # 高 / 中 / 低
    deadline: str                 # ISO 格式: "2026-06-20T15:00"
    status: str = "未开始"        # 未开始 / 进行中 / 已完成 / 已逾期


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    course_name: Optional[str] = None
    task_type: Optional[str] = None
    priority: Optional[str] = None
    deadline: Optional[str] = None
    status: Optional[str] = None


# ── 辅助函数 ─────────────────────────────────────────────────────
def dict_from_row(row) -> dict:
    """把 sqlite3.Row 转为普通 dict"""
    return dict(row) if row else None


def check_overdue(task: dict) -> dict:
    """检查任务是否逾期，自动更新状态"""
    if task["status"] in ("已完成", "已逾期"):
        return task
    try:
        dl = datetime.fromisoformat(task["deadline"])
        if dl < datetime.now() and task["status"] != "已完成":
            task["status"] = "已逾期"
            with get_db() as conn:
                conn.execute(
                    "UPDATE tasks SET status='已逾期', updated_at=datetime('now','localtime') WHERE id=?",
                    (task["id"],),
                )
    except (ValueError, TypeError):
        pass
    return task


# ── API 路由 ─────────────────────────────────────────────────────

@app.get("/api/tasks")
def list_tasks(
    status: Optional[str] = Query(None, description="按状态筛选"),
    course: Optional[str] = Query(None, description="按课程名称筛选"),
    task_type: Optional[str] = Query(None, description="按任务类型筛选"),
    priority: Optional[str] = Query(None, description="按优先级筛选"),
    search: Optional[str] = Query(None, description="标题/描述模糊搜索"),
):
    """获取任务列表，支持多条件筛选"""
    query = "SELECT * FROM tasks WHERE 1=1"
    params = []

    if status:
        query += " AND status=?"
        params.append(status)
    if course:
        query += " AND course_name=?"
        params.append(course)
    if task_type:
        query += " AND task_type=?"
        params.append(task_type)
    if priority:
        query += " AND priority=?"
        params.append(priority)
    if search:
        query += " AND (title LIKE ? OR description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY deadline ASC"

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    tasks = [check_overdue(dict_from_row(r)) for r in rows]
    return {"count": len(tasks), "tasks": tasks}


@app.get("/api/tasks/calendar")
def calendar_view(
    start_date: str = Query(..., description="起始日期 ISO 格式: 2026-06-01"),
    end_date: str = Query(..., description="结束日期 ISO 格式: 2026-06-30"),
):
    """按日期范围查询任务（日历视图用）"""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM tasks
            WHERE date(deadline) BETWEEN date(?) AND date(?)
            ORDER BY deadline ASC
            """,
            (start_date, end_date),
        ).fetchall()
    tasks = [check_overdue(dict_from_row(r)) for r in rows]
    return {"count": len(tasks), "tasks": tasks}


@app.get("/api/reminders")
def get_reminders():
    """获取即将到期和已逾期的提醒任务"""
    now = datetime.now()
    remind_before = now + timedelta(hours=REMIND_HOURS)

    with get_db() as conn:
        # 临近截止（24小时内，未完成）
        upcoming = conn.execute(
            """
            SELECT * FROM tasks
            WHERE status NOT IN ('已完成', '已逾期')
              AND deadline BETWEEN ? AND ?
            ORDER BY deadline ASC
            """,
            (now.isoformat(), remind_before.isoformat()),
        ).fetchall()

        # 已逾期（未完成）
        overdue = conn.execute(
            """
            SELECT * FROM tasks
            WHERE status NOT IN ('已完成', '已逾期')
              AND deadline < ?
            ORDER BY deadline ASC
            """,
            (now.isoformat(),),
        ).fetchall()

    # 自动标记逾期
    for r in overdue:
        check_overdue(dict_from_row(r))

    return {
        "upcoming": [dict_from_row(r) for r in upcoming],
        "overdue": [dict_from_row(r) for r in overdue],
    }


@app.get("/api/tasks/{task_id}")
def get_task(task_id: int):
    """获取单个任务"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    return dict_from_row(row)


@app.post("/api/tasks", status_code=201)
def create_task(task: TaskCreate):
    """创建新任务"""
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO tasks (title, description, course_name, task_type,
                               priority, deadline, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (task.title, task.description, task.course_name, task.task_type,
             task.priority, task.deadline, task.status),
        )
        new_id = cur.lastrowid
    return {"id": new_id, "message": "任务创建成功"}


@app.put("/api/tasks/{task_id}")
def update_task(task_id: int, task: TaskUpdate):
    """更新任务"""
    updates = task.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="没有提供需要更新的字段")

    updates["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k}=?" for k in updates.keys())
    values = list(updates.values()) + [task_id]

    with get_db() as conn:
        conn.execute(f"UPDATE tasks SET {set_clause} WHERE id=?", values)

    return {"message": "任务更新成功"}


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int):
    """删除任务"""
    with get_db() as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="任务不存在")
    return {"message": "任务已删除"}


@app.get("/api/stats")
def get_stats():
    """获取统计概览"""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        by_status = {}
        for row in conn.execute(
            "SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status"
        ).fetchall():
            by_status[row["status"]] = row["cnt"]
        by_type = {}
        for row in conn.execute(
            "SELECT task_type, COUNT(*) as cnt FROM tasks GROUP BY task_type"
        ).fetchall():
            by_type[row["task_type"]] = row["cnt"]

    return {"total": total, "by_status": by_status, "by_type": by_type}


# ── 静态文件服务（前端 HTML） ────────────────────────────────────
# 必须放在最后，避免覆盖 API 路由
app.mount("/", StaticFiles(directory="static", html=True), name="static")


# ── 启动入口 ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print(f"  学生任务管理系统 启动中...")
    print(f"  本地访问: http://{HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)
