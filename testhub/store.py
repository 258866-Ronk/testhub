"""All SQL lives here. Outbox is written in the SAME transaction as the run."""
import time
from datetime import datetime
from .db import connect


def now():
    return datetime.now().isoformat(timespec="seconds")


def create_run(suite_id, idempotency_key, mode):
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT run_no,status FROM th_run WHERE idempotency_key=?",
                                (idempotency_key,)).fetchone()
        if existing:
            conn.rollback()
            return {"run_no": existing["run_no"], "status": existing["status"], "created": False}
        seq = conn.execute("SELECT COUNT(*)+1 AS n FROM th_run").fetchone()["n"]
        run_no = "RUN-" + datetime.now().strftime("%Y%m%d%H%M%S") + "-%04d" % seq
        cur = conn.execute(
            "INSERT INTO th_run(run_no,suite_id,idempotency_key,status,mode,created_at) "
            "VALUES(?,?,?,'PENDING',?,?)",
            (run_no, suite_id, idempotency_key, mode, now()))
        run_id = cur.lastrowid
        conn.execute(
            "INSERT INTO th_outbox(run_id,status,available_at,created_at) VALUES(?,'NEW',?,?)",
            (run_id, time.time(), now()))
        conn.commit()
        return {"run_no": run_no, "status": "PENDING", "created": True, "run_id": run_id}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def claim_outbox():
    """Atomic CAS claim: only one worker gets a NEW message."""
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM th_outbox WHERE status='NEW' AND available_at<=? "
            "ORDER BY id LIMIT 1", (time.time(),)).fetchone()
        if not row:
            conn.rollback()
            return None
        upd = conn.execute("UPDATE th_outbox SET status='PROCESSING' WHERE id=? AND status='NEW'",
                           (row["id"],))
        if upd.rowcount != 1:
            conn.rollback()
            return None
        # second CAS on run state: only PENDING -> RUNNING
        conn.execute("UPDATE th_run SET status='RUNNING', attempt=attempt+1 "
                     "WHERE id=? AND status='PENDING'", (row["run_id"],))
        conn.commit()
        return dict(row)
    finally:
        conn.close()


def finish_success(outbox_id, run_id, stats):
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE th_outbox SET status='DONE' WHERE id=?", (outbox_id,))
        conn.execute(
            "UPDATE th_run SET status='SUCCESS', total=?, passed=?, failed=?, pass_rate=?, "
            "duration_ms=?, finished_at=?, error='' WHERE id=? AND status='RUNNING'",
            (stats["total"], stats["passed"], stats["failed"], stats["pass_rate"],
             stats["duration_ms"], now(), run_id))
        conn.execute("DELETE FROM th_run_case WHERE run_id=?", (run_id,))
        conn.executemany(
            "INSERT INTO th_run_case(run_id,name,passed,status_code,response_time_ms) VALUES(?,?,?,?,?)",
            [(run_id, c["name"], 1 if c["passed"] else 0, c["statusCode"], c["responseTimeMs"])
             for c in stats["cases"]])
        conn.commit()
    finally:
        conn.close()


def finish_fault(outbox_id, run_id, err, max_retries):
    """Distinguish PLATFORM fault from business FAIL. Faults retry with backoff, then dead-letter."""
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT attempt FROM th_outbox WHERE id=?", (outbox_id,)).fetchone()
        attempt = (row["attempt"] if row else 0) + 1
        if attempt <= max_retries:
            delay = min(2 ** attempt, 30)
            conn.execute("UPDATE th_outbox SET status='NEW', attempt=?, available_at=?, last_error=? "
                         "WHERE id=?", (attempt, time.time() + delay, err[:300], outbox_id))
            conn.execute("UPDATE th_run SET status='PENDING', error=? WHERE id=? AND status='RUNNING'",
                         (err[:300], run_id))
        else:
            conn.execute("UPDATE th_outbox SET status='DEAD', attempt=?, last_error=? WHERE id=?",
                         (attempt, err[:300], outbox_id))
            conn.execute("INSERT INTO th_dead_letter(run_id,error,created_at) VALUES(?,?,?)",
                         (run_id, err[:300], now()))
            conn.execute("UPDATE th_run SET status='FAILED', error=?, finished_at=? WHERE id=?",
                         (err[:300], now(), run_id))
        conn.commit()
        return attempt
    finally:
        conn.close()


def get_run(run_no):
    conn = connect()
    try:
        r = conn.execute("SELECT * FROM th_run WHERE run_no=?", (run_no,)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def replay_dead(dead_id):
    """Replay creates a BRAND NEW run, never mutates history."""
    conn = connect()
    try:
        dead = conn.execute("SELECT * FROM th_dead_letter WHERE id=?", (dead_id,)).fetchone()
        if not dead:
            return None
        old = conn.execute("SELECT suite_id,mode FROM th_run WHERE id=?", (dead["run_id"],)).fetchone()
        return create_run(old["suite_id"], "REPLAY:%s:%d" % (dead_id, time.time_ns()), old["mode"])
    finally:
        conn.close()


def case_latencies(run_no):
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT c.response_time_ms FROM th_run_case c JOIN th_run r ON r.id=c.run_id "
            "WHERE r.run_no=?", (run_no,)).fetchall()
        return [r["response_time_ms"] for r in rows]
    finally:
        conn.close()


def get_run_by_id(run_id):
    conn = connect()
    try:
        r = conn.execute("SELECT * FROM th_run WHERE id=?", (run_id,)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def enabled_tasks():
    conn = connect()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM th_task WHERE enabled=1").fetchall()]
    finally:
        conn.close()
