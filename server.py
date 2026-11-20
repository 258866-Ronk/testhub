"""Start TestHub API + worker. Usage: python server.py [--no-cron] [--port 9090]"""
import sys, os
from testhub.api import app
from testhub.worker import WorkerPool
from testhub.db import init_db

if __name__ == "__main__":
    no_cron = "--no-cron" in sys.argv
    port = 9090
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    init_db()  # create tables BEFORE worker threads start
    pool = WorkerPool(with_cron=not no_cron)
    pool.start()
    print("TestHub listening on http://127.0.0.1:%d (cron=%s)" % (port, not no_cron), flush=True)
    try:
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True)
    finally:
        pool.shutdown()
