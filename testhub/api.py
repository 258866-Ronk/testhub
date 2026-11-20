"""Flask routes + JSON helpers."""
from flask import Flask, jsonify, request, send_from_directory
from . import config
from .db import init_db
from . import store, stats, security
import os, time

app = Flask(__name__, static_folder=None)


def ok(data=None, **kw):
    payload = {"code": 0, "msg": "ok"}
    if data is not None:
        payload["data"] = data
    payload.update(kw)
    return jsonify(payload)


@app.before_request
def boot():
    if not getattr(app, "_booted", False):
        init_db()
        app._booted = True


@app.get("/api/v1/health")
def health():
    engine_ready = os.path.exists(config.ENGINE_CLI)
    return ok({"status": "UP", "engineReady": engine_ready, "engineCli": config.ENGINE_CLI})


@app.post("/api/v1/auth/login")
def login():
    body = request.get_json(silent=True) or {}
    conn = __import__("testhub.db", fromlist=["connect"]).connect()
    try:
        row = conn.execute("SELECT * FROM th_user WHERE username=? AND password=?",
                           (body.get("username"), body.get("password"))).fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"code": 401, "msg": "bad credentials"}), 401
    token = security.make_token(row["username"], row["role"])
    return ok({"token": token, "role": row["role"], "username": row["username"]})


@app.get("/api/v1/meta/overview")
@security.require_role("VIEWER", "OPERATOR", "ADMIN")
def meta_overview():
    conn = __import__("testhub.db", fromlist=["connect"]).connect()
    try:
        projects = [dict(r) for r in conn.execute("SELECT * FROM th_project")]
        suites = [dict(r) for r in conn.execute("SELECT * FROM th_suite")]
        tasks = [dict(r) for r in conn.execute("SELECT * FROM th_task")]
    finally:
        conn.close()
    return ok({"projects": projects, "suites": suites, "tasks": tasks})


@app.post("/api/v1/runs")
@security.require_role("OPERATOR", "ADMIN")
def create_run():
    body = request.get_json(silent=True) or {}
    suite_id = int(body.get("suiteId", 1))
    key = body.get("idempotencyKey") or ("API:%s" % time.time_ns())
    result = store.create_run(suite_id, key, body.get("mode", "sequential"))
    return ok(result)


@app.get("/api/v1/runs/<run_no>")
@security.require_role("VIEWER", "OPERATOR", "ADMIN")
def get_run(run_no):
    r = store.get_run(run_no)
    if not r:
        return jsonify({"code": 404, "msg": "not found"}), 404
    return ok(r)


@app.get("/api/v1/runs/<run_no>/gate")
@security.require_role("VIEWER", "OPERATOR", "ADMIN")
def gate(run_no):
    r = store.get_run(run_no)
    if not r:
        return jsonify({"code": 404, "msg": "not found"}), 404
    allowed = r["status"] == "SUCCESS" and r["total"] > 0 and r["failed"] == 0
    return ok({"runNo": run_no, "status": r["status"], "allowed": allowed,
               "exitCode": 0 if allowed else 1,
               "reason": "quality gate passed" if allowed else "run not green"})


@app.get("/api/v1/stats/<run_no>")
@security.require_role("VIEWER", "OPERATOR", "ADMIN")
def stat(run_no):
    return ok(stats.summary(run_no))


@app.get("/api/v1/dead-letters")
@security.require_role("ADMIN")
def dead_letters():
    conn = __import__("testhub.db", fromlist=["connect"]).connect()
    try:
        rows = [dict(r) for r in conn.execute("SELECT * FROM th_dead_letter ORDER BY id DESC")]
    finally:
        conn.close()
    return ok(rows)


@app.post("/api/v1/dead-letters/<int:dead_id>/replay")
@security.require_role("ADMIN")
def replay(dead_id):
    result = store.replay_dead(dead_id)
    return ok(result) if result else (jsonify({"code": 404, "msg": "not found"}), 404)


@app.get("/")
def console():
    return send_from_directory(os.path.join(os.path.dirname(__file__), "static"), "index.html")


def create_app():
    init_db()
    return app
