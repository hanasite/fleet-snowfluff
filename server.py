#!/usr/bin/env python3
"""
飞行雪绒应援栈 · Flask 本地中转服务器
手机用户通过此中转实时查看 Claude Code 会话。
纯本地使用，无需公网。
"""
import os
import re
import json
import time
import queue
import socket
import webbrowser
import threading
from pathlib import Path
from flask import Flask, render_template, request, Response, jsonify, stream_with_context

# ═══════════════════════════════════════════════
PORT = 19877
CLAUDE_DIR = Path.home() / ".claude" / "projects"
POLL_INTERVAL = 1.0  # JSONL 轮询间隔（秒）

# ═══════════════════════════════════════════════
app = Flask(__name__, template_folder="templates")
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# SSE 客户端队列
sse_clients: list[queue.Queue] = []
sse_lock = threading.Lock()

# ═══════════════════════════════════════════════

def get_local_ip():
    """获取本机局域网 IP"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def list_projects():
    """列出所有项目目录"""
    if not CLAUDE_DIR.exists():
        return []
    projects = []
    for d in sorted(CLAUDE_DIR.iterdir()):
        if d.is_dir() and not d.name.startswith("C--"):
            sessions_dir = d / "sessions"
            if sessions_dir.exists():
                count = len(list(sessions_dir.glob("*.jsonl")))
                projects.append({"name": d.name, "sessions": count})
            else:
                projects.append({"name": d.name, "sessions": 0})
        elif d.is_dir():
            sessions_dir = d / "sessions"
            if sessions_dir.exists():
                count = len(list(sessions_dir.glob("*.jsonl")))
                projects.append({"name": d.name, "sessions": count})
    return sorted(projects, key=lambda x: x["name"])


def list_sessions(project_name):
    """列出项目下的所有会话"""
    sessions_dir = CLAUDE_DIR / project_name / "sessions"
    if not sessions_dir.exists():
        return []
    sessions = []
    for f in sorted(sessions_dir.glob("*.jsonl"), key=os.path.getmtime, reverse=True):
        size = f.stat().st_size
        sessions.append({
            "id": f.stem,
            "size": size,
            "mtime": f.stat().st_mtime,
            "messages": count_messages(f)
        })
    return sessions


def count_messages(filepath):
    """统计 JSONL 文件的消息数"""
    count = 0
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for _ in f:
                count += 1
    except Exception:
        pass
    return count


def read_messages(filepath, limit=100):
    """读取 JSONL 文件的最新消息"""
    messages = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        msg = json.loads(line)
                        messages.append(msg)
                    except json.JSONDecodeError:
                        pass
    except Exception:
        pass
    return messages[-limit:]


def get_latest_session(project_name):
    """获取项目最新的会话文件"""
    sessions_dir = CLAUDE_DIR / project_name / "sessions"
    if not sessions_dir.exists():
        return None
    files = sorted(sessions_dir.glob("*.jsonl"), key=os.path.getmtime, reverse=True)
    return files[0] if files else None


def broadcast_sse(data):
    """向所有 SSE 客户端广播数据"""
    with sse_lock:
        dead = []
        for q in sse_clients:
            try:
                q.put_nowait(data)
            except queue.Full:
                dead.append(q)
        for q in dead:
            sse_clients.remove(q)


def jsonl_watcher():
    """后台线程：轮询最新会话的 JSONL 变化"""
    last_sizes = {}
    while True:
        try:
            projects = list_projects()
            for p in projects:
                latest = get_latest_session(p["name"])
                if latest:
                    key = str(latest)
                    current_size = latest.stat().st_size
                    old_size = last_sizes.get(key, 0)
                    if current_size > old_size:
                        # 有新内容
                        messages = read_messages(latest)
                        broadcast_sse(json.dumps({
                            "type": "messages",
                            "project": p["name"],
                            "session": latest.stem,
                            "messages": messages
                        }))
                        last_sizes[key] = current_size
                    elif current_size < old_size:
                        # 文件被重写（新会话）
                        messages = read_messages(latest)
                        broadcast_sse(json.dumps({
                            "type": "messages",
                            "project": p["name"],
                            "session": latest.stem,
                            "messages": messages
                        }))
                        last_sizes[key] = current_size
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)


# ═══════════════════════════════════════════════

@app.route("/")
def index():
    local_ip = get_local_ip()
    return render_template("index.html", port=PORT, local_ip=local_ip)


@app.route("/api/projects")
def api_projects():
    return jsonify(list_projects())


@app.route("/api/sessions/<project>")
def api_sessions(project):
    return jsonify(list_sessions(project))


@app.route("/api/messages/<project>/<session_id>")
def api_messages(project, session_id):
    filepath = CLAUDE_DIR / project / "sessions" / f"{session_id}.jsonl"
    limit = request.args.get("limit", 100, type=int)
    return jsonify(read_messages(filepath, limit))


@app.route("/api/stream")
def api_stream():
    """SSE 端点：实时推送新消息"""
    def event_stream():
        q = queue.Queue(maxsize=100)
        with sse_lock:
            sse_clients.append(q)
        try:
            # 发送初始心跳
            yield "data: {\"type\":\"connected\"}\n\n"
            while True:
                try:
                    data = q.get(timeout=30)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    yield ": heartbeat\n\n"
        except GeneratorExit:
            pass
        finally:
            with sse_lock:
                if q in sse_clients:
                    sse_clients.remove(q)

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


# ═══════════════════════════════════════════════

if __name__ == "__main__":
    local_ip = get_local_ip()
    print(f"""
╔══════════════════════════════════════╗
║     飞行雪绒应援栈 · Fleet Snowfluff  ║
╠══════════════════════════════════════╣
║  本机:     http://127.0.0.1:{PORT}      ║
║  手机:     http://{local_ip}:{PORT}       ║
║                                      ║
║  手机和电脑需要在同一个 WiFi 下          ║
║  手机浏览器打开上面的地址即可            ║
╚══════════════════════════════════════╝
""")

    # 启动 JSONL 监控线程
    t = threading.Thread(target=jsonl_watcher, daemon=True)
    t.start()

    # 打开浏览器
    threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}")).start()

    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
