"""Configuration. Env vars override defaults. Zero external service required."""
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _env(name, default):
    return os.environ.get(name, default)


DB_PATH = _env("TESTHUB_DB", os.path.join(BASE, "data", "testhub.db"))
SECRET = _env("TESTHUB_SECRET", "testhub-demo-secret-change-me")
# Sister project AutoTest Pro CLI (sibling directory by default)
ENGINE_PYTHON = _env("TESTHUB_ENGINE_PYTHON", "python")
ENGINE_CLI = _env("TESTHUB_ENGINE_CLI", os.path.join(BASE, "..", "py-autotest-pro", "run_demo.py"))
ENGINE_SOURCE = _env("TESTHUB_ENGINE_SOURCE", os.path.join(BASE, "..", "py-autotest-pro"))
WORK_ROOT = _env("TESTHUB_WORK_ROOT", os.path.join(BASE, "data", "runs"))
TIMEOUT_SEC = int(_env("TESTHUB_TIMEOUT", "60"))
MAX_RETRIES = int(_env("TESTHUB_MAX_RETRIES", "3"))
POLL_INTERVAL = float(_env("TESTHUB_POLL", "0.5"))
