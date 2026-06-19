"""
学生任务管理系统 - FastAPI 后端（v2.0 用户系统版）
"""
import os
import sqlite3
import secrets
from datetime import datetime, timedelta
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException, Header, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from passlib.hash import bcrypt

# ── 配置（从环境变量读取，带默认值） ─────────────────────────────
HOST = os.getenv("TASK_APP_HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", os.getenv("TASK_APP_PORT", "8080")))
DB_PATH = os.getenv("TASK_DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "student_tasks.db"))
REMIND_HOURS = int(os.getenv("TASK_REMIND_HOURS", "24"))
FRONTEND_ORIGIN = os.getenv("TASK_FRONTEND_ORIGIN", "*")

app = FastAPI(title="学生任务管理系统", version="2.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
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
    """初始化数据库表，含自动迁移"""
    with get_db() as conn:
        # 创建 users 表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    NOT NULL UNIQUE,
                password_hash TEXT    NOT NULL,
                nickname      TEXT    DEFAULT '',
                created_at    TEXT    DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # 创建 sessions 表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token      TEXT PRIMARY KEY,
                user_id    INTEGER NOT NULL REFERENCES users(id),
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                expires_at TEXT NOT NULL
            )
        """)

        # 检查 tasks 表是否存在及是否有 user_id 列
        cur = conn.execute("PRAGMA table_info(tasks)")
        columns = [row["name"] for row in cur.fetchall()]

        if not columns:
            # tasks 表不存在，直接创建
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL REFERENCES users(id),
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
        elif "user_id" not in columns:
            # 旧表没有 user_id 列，需要迁移
            conn.execute("""
                CREATE TABLE tasks_new (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL DEFAULT 0,
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
            conn.execute("""
                INSERT INTO tasks_new (id, title, description, course_name, task_type,
                                       priority, deadline, status, created_at, updated_at)
                SELECT id, title, description, course_name, task_type,
                       priority, deadline, status, created_at, updated_at
                FROM tasks
            """)
            conn.execute("DROP TABLE tasks")
            conn.execute("ALTER TABLE tasks_new RENAME TO tasks")

        # 学习时长表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS study_logs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL REFERENCES users(id),
                date            TEXT    NOT NULL,
                duration_minutes INTEGER NOT NULL DEFAULT 0,
                notes           TEXT    DEFAULT '',
                created_at      TEXT    DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # 成绩表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS grades (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                task_id     INTEGER REFERENCES tasks(id),
                course_name TEXT    DEFAULT '',
                score       REAL    NOT NULL,
                total_score REAL    DEFAULT 100,
                created_at  TEXT    DEFAULT (datetime('now', 'localtime'))
            )
        """)


init_db()

# 会话有效期（天）
SESSION_DAYS = 7


# ── Pydantic 模型 ─────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    password: str
    nickname: str = ""


class LoginRequest(BaseModel):
    username: str
    password: str


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    course_name: str = ""
    task_type: str = "其他"
    priority: str = "中"
    deadline: str
    status: str = "未开始"

    @field_validator("task_type")
    @classmethod
    def check_type(cls, v):
        if v not in ("作业", "考试", "实验", "其他"):
            raise ValueError(f"无效的任务类型: {v}")
        return v

    @field_validator("priority")
    @classmethod
    def check_priority(cls, v):
        if v not in ("高", "中", "低"):
            raise ValueError(f"无效的优先级: {v}")
        return v

    @field_validator("status")
    @classmethod
    def check_status(cls, v):
        if v not in ("未开始", "进行中", "已完成", "已逾期"):
            raise ValueError(f"无效的状态: {v}")
        return v


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    course_name: str | None = None
    task_type: str | None = None
    priority: str | None = None
    deadline: str | None = None
    status: str | None = None

    @field_validator("task_type")
    @classmethod
    def check_type(cls, v):
        if v is not None and v not in ("作业", "考试", "实验", "其他"):
            raise ValueError(f"无效的任务类型: {v}")
        return v

    @field_validator("priority")
    @classmethod
    def check_priority(cls, v):
        if v is not None and v not in ("高", "中", "低"):
            raise ValueError(f"无效的优先级: {v}")
        return v

    @field_validator("status")
    @classmethod
    def check_status(cls, v):
        if v is not None and v not in ("未开始", "进行中", "已完成", "已逾期"):
            raise ValueError(f"无效的状态: {v}")
        return v


class StudyLogCreate(BaseModel):
    date: str
    duration_minutes: int
    notes: str = ""


class GradeCreate(BaseModel):
    task_id: int | None = None
    course_name: str = ""
    score: float
    total_score: float = 100.0


# ── 辅助函数 ─────────────────────────────────────────────────────
def dict_from_row(row) -> dict | None:
    return dict(row) if row else None


def generate_token() -> str:
    return secrets.token_hex(32)


def clean_expired_sessions():
    """清理过期会话"""
    with get_db() as conn:
        conn.execute(
            "DELETE FROM sessions WHERE expires_at < ?",
            (datetime.now().isoformat(),),
        )


def check_overdue(task: dict) -> dict:
    """检查任务是否逾期，自动更新状态"""
    if task["status"] in ("已完成", "已逾期"):
        return task
    try:
        dl = datetime.fromisoformat(task["deadline"])
        if dl < datetime.now():
            task["status"] = "已逾期"
            with get_db() as conn:
                conn.execute(
                    "UPDATE tasks SET status='已逾期', updated_at=datetime('now','localtime') WHERE id=?",
                    (task["id"],),
                )
    except (ValueError, TypeError):
        pass
    return task


# ── 认证依赖 ─────────────────────────────────────────────────────
def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """从 Authorization header 解析 token，返回当前用户信息"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录，请先登录")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="无效的认证信息")

    clean_expired_sessions()

    with get_db() as conn:
        row = conn.execute(
            """SELECT users.id, users.username, users.nickname, users.created_at
               FROM sessions JOIN users ON sessions.user_id = users.id
               WHERE sessions.token = ? AND sessions.expires_at > ?""",
            (token, datetime.now().isoformat()),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

    return dict_from_row(row)


# ── 认证路由 ─────────────────────────────────────────────────────

@app.post("/api/auth/register")
def register(body: RegisterRequest):
    """用户注册"""
    username = body.username.strip()
    password = body.password.strip()
    nickname = body.nickname.strip()

    if not username or len(username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少需要 2 个字符")
    if not password or len(password) < 4:
        raise HTTPException(status_code=400, detail="密码至少需要 4 个字符")

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username=?", (username,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="用户名已被注册")

        password_hash = bcrypt.hash(password)
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, nickname) VALUES (?, ?, ?)",
            (username, password_hash, nickname or username),
        )
        user_id = cur.lastrowid

    return {"id": user_id, "message": "注册成功，请登录"}


@app.post("/api/auth/login")
def login(body: LoginRequest):
    """用户登录，返回 session token"""
    username = body.username.strip()
    password = body.password.strip()

    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")

    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()

    if not user or not bcrypt.verify(password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    # 生成 token
    token = generate_token()
    expires_at = (datetime.now() + timedelta(days=SESSION_DAYS)).isoformat()

    with get_db() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user["id"], expires_at),
        )

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "nickname": user["nickname"],
        },
        "message": "登录成功",
    }


@app.post("/api/auth/logout")
def logout(authorization: str | None = Header(default=None)):
    """退出登录"""
    if authorization:
        token = authorization.removeprefix("Bearer ").strip()
        with get_db() as conn:
            conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    return {"message": "已退出登录"}


@app.get("/api/auth/me")
def get_me(user: dict = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return {"user": user}


# ── 任务路由 ─────────────────────────────────────────────────────

@app.get("/api/tasks")
def list_tasks(
    user: dict = Depends(get_current_user),
    status: str | None = None,
    course: str | None = None,
    task_type: str | None = None,
    priority: str | None = None,
    search: str | None = None,
):
    """获取当前用户的任务列表（支持筛选和搜索）"""
    query = "SELECT * FROM tasks WHERE user_id=?"
    params = [user["id"]]

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


@app.post("/api/tasks", status_code=201)
def create_task(
    body: TaskCreate,
    user: dict = Depends(get_current_user),
):
    """创建任务"""
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO tasks (user_id, title, description, course_name,
                                  task_type, priority, deadline, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user["id"], body.title, body.description, body.course_name,
             body.task_type, body.priority, body.deadline, body.status),
        )
        new_id = cur.lastrowid
    return {"id": new_id, "message": "任务创建成功"}


@app.get("/api/tasks/calendar")
def calendar_view(
    start_date: str,
    end_date: str,
    user: dict = Depends(get_current_user),
):
    """日历范围查询"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM tasks
               WHERE user_id=? AND date(deadline) BETWEEN date(?) AND date(?)
               ORDER BY deadline ASC""",
            (user["id"], start_date, end_date),
        ).fetchall()
    tasks = [check_overdue(dict_from_row(r)) for r in rows]
    return {"count": len(tasks), "tasks": tasks}


@app.get("/api/reminders")
def get_reminders(user: dict = Depends(get_current_user)):
    """获取提醒"""
    now = datetime.now()
    remind_before = now + timedelta(hours=REMIND_HOURS)

    with get_db() as conn:
        upcoming = conn.execute(
            """SELECT * FROM tasks
               WHERE user_id=? AND status NOT IN ('已完成', '已逾期')
                 AND deadline BETWEEN ? AND ?
               ORDER BY deadline ASC""",
            (user["id"], now.isoformat(), remind_before.isoformat()),
        ).fetchall()

        overdue = conn.execute(
            """SELECT * FROM tasks
               WHERE user_id=? AND status NOT IN ('已完成', '已逾期')
                 AND deadline < ?
               ORDER BY deadline ASC""",
            (user["id"], now.isoformat()),
        ).fetchall()

    for r in overdue:
        check_overdue(dict_from_row(r))

    return {
        "upcoming": [dict_from_row(r) for r in upcoming],
        "overdue": [dict_from_row(r) for r in overdue],
    }


@app.get("/api/stats")
def get_stats(user: dict = Depends(get_current_user)):
    """获取统计数据"""
    with get_db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE user_id=?", (user["id"],)
        ).fetchone()[0]

        by_status = {}
        for row in conn.execute(
            "SELECT status, COUNT(*) as cnt FROM tasks WHERE user_id=? GROUP BY status",
            (user["id"],),
        ).fetchall():
            by_status[row["status"]] = row["cnt"]

        by_type = {}
        for row in conn.execute(
            "SELECT task_type, COUNT(*) as cnt FROM tasks WHERE user_id=? GROUP BY task_type",
            (user["id"],),
        ).fetchall():
            by_type[row["task_type"]] = row["cnt"]

    return {"total": total, "by_status": by_status, "by_type": by_type}


# ── 学习时长 API ──────────────────────────────────────────────────

@app.post("/api/study/log", status_code=201)
def add_study_log(body: StudyLogCreate, user: dict = Depends(get_current_user)):
    """记录学习时长"""
    if body.duration_minutes <= 0 or body.duration_minutes > 1440:
        raise HTTPException(status_code=400, detail="学习时长必须在 1-1440 分钟之间")
    with get_db() as conn:
        # 同一天如果已有记录则累加
        existing = conn.execute(
            "SELECT id, duration_minutes FROM study_logs WHERE user_id=? AND date=?",
            (user["id"], body.date),
        ).fetchone()
        if existing:
            new_dur = existing["duration_minutes"] + body.duration_minutes
            conn.execute(
                "UPDATE study_logs SET duration_minutes=?, notes=? WHERE id=?",
                (new_dur, body.notes, existing["id"]),
            )
            return {"id": existing["id"], "duration_minutes": new_dur, "message": "学习时长已累加"}
        cur = conn.execute(
            "INSERT INTO study_logs (user_id, date, duration_minutes, notes) VALUES (?, ?, ?, ?)",
            (user["id"], body.date, body.duration_minutes, body.notes),
        )
        return {"id": cur.lastrowid, "duration_minutes": body.duration_minutes, "message": "记录成功"}


@app.get("/api/study/logs")
def get_study_logs(
    days: int = 7,
    user: dict = Depends(get_current_user),
):
    """获取最近 N 天的学习时长"""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM study_logs WHERE user_id=? AND date >= ? ORDER BY date ASC",
            (user["id"], cutoff),
        ).fetchall()
        logs = [dict_from_row(r) for r in rows]

        # 总训练值（累计分钟数）
        total_minutes = conn.execute(
            "SELECT COALESCE(SUM(duration_minutes), 0) FROM study_logs WHERE user_id=?",
            (user["id"],),
        ).fetchone()[0]

    return {"logs": logs, "total_minutes": total_minutes, "days": days}


@app.get("/api/study/stats")
def get_study_stats(user: dict = Depends(get_current_user)):
    """学习统计：本周 vs 上周，总训练值等"""
    now = datetime.now()
    this_week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    last_week_start = (now - timedelta(days=now.weekday() + 7)).strftime("%Y-%m-%d")
    last_week_end = (now - timedelta(days=now.weekday() + 1)).strftime("%Y-%m-%d")

    with get_db() as conn:
        this_week = conn.execute(
            "SELECT COALESCE(SUM(duration_minutes), 0) FROM study_logs WHERE user_id=? AND date >= ?",
            (user["id"], this_week_start),
        ).fetchone()[0]
        last_week = conn.execute(
            "SELECT COALESCE(SUM(duration_minutes), 0) FROM study_logs WHERE user_id=? AND date BETWEEN ? AND ?",
            (user["id"], last_week_start, last_week_end),
        ).fetchone()[0]
        total = conn.execute(
            "SELECT COALESCE(SUM(duration_minutes), 0) FROM study_logs WHERE user_id=?",
            (user["id"],),
        ).fetchone()[0]

    return {
        "this_week_minutes": this_week,
        "last_week_minutes": last_week,
        "total_minutes": total,
        "trend": "up" if this_week >= last_week else "down",
    }


# ── 成绩 API ─────────────────────────────────────────────────────

@app.post("/api/grades", status_code=201)
def add_grade(body: GradeCreate, user: dict = Depends(get_current_user)):
    """录入成绩"""
    if body.score < 0 or body.score > body.total_score:
        raise HTTPException(status_code=400, detail="分数超出范围")
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO grades (user_id, task_id, course_name, score, total_score) VALUES (?, ?, ?, ?, ?)",
            (user["id"], body.task_id, body.course_name, body.score, body.total_score),
        )
        return {"id": cur.lastrowid, "message": "成绩录入成功"}


@app.get("/api/grades")
def get_grades(user: dict = Depends(get_current_user)):
    """获取所有成绩"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM grades WHERE user_id=? ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()
    grades = [dict_from_row(r) for r in rows]
    avg = sum(g["score"] for g in grades) / len(grades) if grades else 0
    return {"grades": grades, "count": len(grades), "average": round(avg, 1)}


@app.get("/api/grades/chart")
def get_grades_chart(user: dict = Depends(get_current_user)):
    """获取成绩图表数据"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT course_name, score, total_score, created_at
               FROM grades WHERE user_id=?
               ORDER BY created_at ASC""",
            (user["id"],),
        ).fetchall()
    data = [
        {
            "course": r["course_name"] or "未分类",
            "score": r["score"],
            "total": r["total_score"],
            "percent": round(r["score"] / r["total_score"] * 100, 1),
            "date": r["created_at"][:10],
        }
        for r in rows
    ]
    return {"chart_data": data, "count": len(data)}


# ── 综合任务统计 API ──────────────────────────────────────────────

@app.get("/api/analysis")
def get_analysis(user: dict = Depends(get_current_user)):
    """任务综合分析"""
    with get_db() as conn:
        # 按状态统计
        by_status = {}
        for row in conn.execute(
            "SELECT status, COUNT(*) as cnt FROM tasks WHERE user_id=? GROUP BY status",
            (user["id"],),
        ).fetchall():
            by_status[row["status"]] = row["cnt"]

        # 按课程统计
        by_course = {}
        for row in conn.execute(
            "SELECT course_name, COUNT(*) as cnt FROM tasks WHERE user_id=? AND course_name!='' GROUP BY course_name",
            (user["id"],),
        ).fetchall():
            by_course[row["course_name"]] = row["cnt"]

        # 完成率
        total = sum(by_status.values())
        done = by_status.get("已完成", 0)
        rate = round(done / total * 100, 1) if total > 0 else 0

        # 逾期率
        overdue = by_status.get("已逾期", 0)

        # 学习总时长
        total_study = conn.execute(
            "SELECT COALESCE(SUM(duration_minutes), 0) FROM study_logs WHERE user_id=?",
            (user["id"],),
        ).fetchone()[0]

        # 平均成绩
        avg_row = conn.execute(
            "SELECT COALESCE(AVG(score), 0) as avg_score FROM grades WHERE user_id=?",
            (user["id"],),
        ).fetchone()
        avg_score = round(avg_row[0], 1) if avg_row else 0

        # 成绩趋势（最近10条）
        grade_rows = conn.execute(
            "SELECT score, total_score, created_at FROM grades WHERE user_id=? ORDER BY created_at ASC LIMIT 10",
            (user["id"],),
        ).fetchall()
        grade_trend = [
            {"score": r["score"], "total": r["total_score"], "date": r["created_at"][:10]}
            for r in grade_rows
        ]

    return {
        "by_status": by_status,
        "by_course": by_course,
        "total_tasks": total,
        "completion_rate": rate,
        "overdue_count": overdue,
        "total_study_minutes": total_study,
        "average_score": avg_score,
        "grade_trend": grade_trend,
    }


@app.get("/api/tasks/{task_id}")
def get_task(
    task_id: int,
    user: dict = Depends(get_current_user),
):
    """获取单个任务"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id=? AND user_id=?", (task_id, user["id"])
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    return dict_from_row(row)


@app.put("/api/tasks/{task_id}")
def update_task(
    task_id: int,
    body: TaskUpdate,
    user: dict = Depends(get_current_user),
):
    """更新任务"""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="没有提供需要更新的字段")

    updates["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k}=?" for k in updates.keys())
    values = list(updates.values()) + [task_id, user["id"]]

    with get_db() as conn:
        cur = conn.execute(
            f"UPDATE tasks SET {set_clause} WHERE id=? AND user_id=?", values
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="任务不存在")

    return {"message": "任务更新成功"}


@app.delete("/api/tasks/{task_id}")
def delete_task(
    task_id: int,
    user: dict = Depends(get_current_user),
):
    """删除任务"""
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM tasks WHERE id=? AND user_id=?", (task_id, user["id"])
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="任务不存在")
    return {"message": "任务已删除"}


# ── 静态文件 ─────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

@app.get("/")
async def index():
    return FileResponse("static/index.html")


# ── 启动入口 ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    import webbrowser
    import threading

    url = f"http://{HOST}:{PORT}"

    def open_browser():
        webbrowser.open(url)

    # 延迟 1.5 秒等服务器就绪后自动打开浏览器
    threading.Timer(1.5, open_browser).start()

    print(f"  [OK] 学生任务管理系统 v2.0 启动中...")
    print(f"  本地访问: {url}")
    print(f"  API 文档: {url}/docs")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
