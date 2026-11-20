"""Background worker + cron scheduler, both daemon threads."""
import threading, time, datetime
from . import config
from . import store, engine


def _process_one(msg):
    run = store.get_run_by_id(msg["run_id"])
    mode = run["mode"] if run else "sequential"
    run_no = run["run_no"] if run else "?"
    try:
        stats = engine.run_engine(run_no, mode)
        store.finish_success(msg["id"], msg["run_id"], stats)
    except Exception as exc:
        store.finish_fault(msg["id"], msg["run_id"], str(exc), config.MAX_RETRIES)


def worker_loop(stop):
    while not stop.is_set():
        try:
            msg = store.claim_outbox()
        except Exception as exc:
            # tolerate transient sqlite startup races
            if "no such table" in str(exc):
                stop.wait(config.POLL_INTERVAL)
                continue
            raise
        if msg:
            _process_one(msg)
        else:
            stop.wait(config.POLL_INTERVAL)


def _cron_due(expr, minute):
    """Supports: '' (never), 'HH:MM' daily, '*/N' every N minutes."""
    if not expr:
        return False
    if expr.startswith("*/"):
        try:
            return minute % int(expr[2:]) == 0
        except ValueError:
            return False
    if ":" in expr:
        return datetime.datetime.now().strftime("%H:%M") == expr
    return False


def cron_loop(stop):
    last_fire = -1
    while not stop.is_set():
        minute = int(time.time() // 60)
        if minute != last_fire:
            last_fire = minute
            tasks = store.enabled_tasks()
            for t in tasks:
                if _cron_due(t["cron"], minute):
                    key = "CRON:%d:%d" % (t["id"], minute)
                    store.create_run(t["suite_id"], key, "sequential")
        stop.wait(1)


class WorkerPool:
    def __init__(self, with_cron=True):
        self.stop = threading.Event()
        self.with_cron = with_cron
        self.threads = []

    def start(self):
        w = threading.Thread(target=worker_loop, args=(self.stop,), daemon=True)
        w.start(); self.threads.append(w)
        if self.with_cron:
            c = threading.Thread(target=cron_loop, args=(self.stop,), daemon=True)
            c.start(); self.threads.append(c)

    def shutdown(self):
        self.stop.set()
