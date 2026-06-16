"""
学生任务管理系统 - Flask 后端（适配 PythonAnywhere 部署）
"""
import os
import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager

from flask import Flask, request, jsonify, send_from_directory

# ── 配置（从环境变量读取，带默认值） ─────────────────────────────
HOST = os.getenv("TASK_APP_HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", os.getenv("TASK_APP_PORT", "8080")))
DB_PATH = os.getenv("TASK_DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "student_tasks.db"))
REMIND_HOURS = int(os.getenv("TASK_REMIND_HOURS", "24"))

app = Flask(__name__, static_folder="static", static_url_path="")

# CORS — 允许任意来源访问
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


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


# ── 辅助函数 ─────────────────────────────────────────────────────
def dict_from_row(row) -> dict:
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


# ── 验证函数 ─────────────────────────────────────────────────────
VALID_STATUSES = {"未开始", "进行中", "已完成", "已逾期"}
VALID_PRIORITIES = {"高", "中", "低"}
VALID_TYPES = {"作业", "考试", "实验", "其他"}


def validate_task(data, is_update=False):
    """验证任务数据，返回 (错误信息, 清理后的数据)"""
    errors = []

    if not is_update:
        if not data.get("title", "").strip():
            errors.append("任务标题不能为空")
        if not data.get("deadline", "").strip():
            errors.append("截止时间不能为空")
    else:
        if "title" in data and not data.get("title", "").strip():
            errors.append("任务标题不能为空")

    if data.get("status") and data["status"] not in VALID_STATUSES:
        errors.append(f"无效的状态: {data['status']}")
    if data.get("priority") and data["priority"] not in VALID_PRIORITIES:
        errors.append(f"无效的优先级: {data['priority']}")
    if data.get("task_type") and data["task_type"] not in VALID_TYPES:
        errors.append(f"无效的任务类型: {data['task_type']}")

    if errors:
        return "; ".join(errors), None

    # 清理数据
    cleaned = {}
    for field in ["title", "description", "course_name", "task_type", "priority", "deadline", "status"]:
        if field in data:
            val = data[field]
            if isinstance(val, str):
                val = val.strip()
            cleaned[field] = val
    return None, cleaned


# ── 首页 ─────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ── API 路由 ─────────────────────────────────────────────────────

@app.route("/api/tasks", methods=["GET", "POST", "OPTIONS"])
def tasks_list():
    if request.method == "OPTIONS":
        return jsonify({"ok": True})

    if request.method == "GET":
        status = request.args.get("status")
        course = request.args.get("course")
        task_type = request.args.get("task_type")
        priority = request.args.get("priority")
        search = request.args.get("search")

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
        return jsonify({"count": len(tasks), "tasks": tasks})

    if request.method == "POST":
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"detail": "请求体不能为空"}), 400

        error, cleaned = validate_task(data)
        if error:
            return jsonify({"detail": error}), 400

        cleaned.setdefault("description", "")
        cleaned.setdefault("course_name", "")
        cleaned.setdefault("task_type", "其他")
        cleaned.setdefault("priority", "中")
        cleaned.setdefault("status", "未开始")

        with get_db() as conn:
            cur = conn.execute(
                """INSERT INTO tasks (title, description, course_name, task_type,
                                      priority, deadline, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (cleaned["title"], cleaned["description"], cleaned["course_name"],
                 cleaned["task_type"], cleaned["priority"], cleaned["deadline"], cleaned["status"]),
            )
            new_id = cur.lastrowid
        return jsonify({"id": new_id, "message": "任务创建成功"}), 201


@app.route("/api/tasks/calendar", methods=["GET"])
def calendar_view():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    if not start_date or not end_date:
        return jsonify({"detail": "缺少 start_date 或 end_date 参数"}), 400

    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM tasks
               WHERE date(deadline) BETWEEN date(?) AND date(?)
               ORDER BY deadline ASC""",
            (start_date, end_date),
        ).fetchall()
    tasks = [check_overdue(dict_from_row(r)) for r in rows]
    return jsonify({"count": len(tasks), "tasks": tasks})


@app.route("/api/reminders", methods=["GET"])
def get_reminders():
    now = datetime.now()
    remind_before = now + timedelta(hours=REMIND_HOURS)

    with get_db() as conn:
        upcoming = conn.execute(
            """SELECT * FROM tasks
               WHERE status NOT IN ('已完成', '已逾期')
                 AND deadline BETWEEN ? AND ?
               ORDER BY deadline ASC""",
            (now.isoformat(), remind_before.isoformat()),
        ).fetchall()

        overdue = conn.execute(
            """SELECT * FROM tasks
               WHERE status NOT IN ('已完成', '已逾期')
                 AND deadline < ?
               ORDER BY deadline ASC""",
            (now.isoformat(),),
        ).fetchall()

    for r in overdue:
        check_overdue(dict_from_row(r))

    return jsonify({
        "upcoming": [dict_from_row(r) for r in upcoming],
        "overdue": [dict_from_row(r) for r in overdue],
    })


@app.route("/api/tasks/<int:task_id>", methods=["GET", "PUT", "DELETE", "OPTIONS"])
def task_detail(task_id):
    if request.method == "OPTIONS":
        return jsonify({"ok": True})

    if request.method == "GET":
        with get_db() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            return jsonify({"detail": "任务不存在"}), 404
        return jsonify(dict_from_row(row))

    if request.method == "PUT":
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"detail": "请求体不能为空"}), 400

        error, cleaned = validate_task(data, is_update=True)
        if error:
            return jsonify({"detail": error}), 400

        if not cleaned:
            return jsonify({"detail": "没有提供需要更新的字段"}), 400

        cleaned["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k}=?" for k in cleaned.keys())
        values = list(cleaned.values()) + [task_id]

        with get_db() as conn:
            conn.execute(f"UPDATE tasks SET {set_clause} WHERE id=?", values)

        return jsonify({"message": "任务更新成功"})

    if request.method == "DELETE":
        with get_db() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            if cur.rowcount == 0:
                return jsonify({"detail": "任务不存在"}), 404
        return jsonify({"message": "任务已删除"})


@app.route("/api/stats", methods=["GET"])
def get_stats():
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

    return jsonify({"total": total, "by_status": by_status, "by_type": by_type})


# ── 启动入口 ─────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"  学生任务管理系统 启动中...")
    print(f"  本地访问: http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=False)
