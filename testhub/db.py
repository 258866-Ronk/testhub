"""SQLite schema + connection. Idempotent bootstrap."""
import os, sqlite3
from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS th_project (
  id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS th_suite (
  id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, code TEXT NOT NULL,
  name TEXT NOT NULL, testcase_dir TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS th_task (
  id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, suite_id INTEGER NOT NULL,
  name TEXT NOT NULL, cron TEXT DEFAULT '', enabled INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS th_run (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_no TEXT UNIQUE NOT NULL,
  suite_id INTEGER NOT NULL,
  idempotency_key TEXT UNIQUE NOT NULL,
  status TEXT NOT NULL,               -- PENDING/RUNNING/SUCCESS/FAILED
  mode TEXT NOT NULL DEFAULT 'sequential',
  attempt INTEGER NOT NULL DEFAULT 0,
  total INTEGER DEFAULT 0, passed INTEGER DEFAULT 0, failed INTEGER DEFAULT 0,
  pass_rate REAL DEFAULT 0, duration_ms INTEGER DEFAULT 0,
  error TEXT DEFAULT '',
  created_at TEXT NOT NULL, finished_at TEXT);
CREATE TABLE IF NOT EXISTS th_run_case (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL, name TEXT NOT NULL, passed INTEGER NOT NULL,
  status_code INTEGER NOT NULL, response_time_ms INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS th_outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  status TEXT NOT NULL,               -- NEW/PROCESSING/DONE/DEAD
  available_at REAL NOT NULL,
  attempt INTEGER NOT NULL DEFAULT 0,
  last_error TEXT DEFAULT '',
  created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS th_dead_letter (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL, error TEXT DEFAULT '', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS th_user (
  id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL, role TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_outbox_status ON th_outbox(status, available_at);
CREATE INDEX IF NOT EXISTS idx_case_run ON th_run_case(run_id);
"""

SEED = """
INSERT OR IGNORE INTO th_user(username,password,role) VALUES
 ('viewer','123456','VIEWER'),('op','123456','OPERATOR'),('admin','123456','ADMIN');
INSERT OR IGNORE INTO th_project(code,name) VALUES ('DEMO','演示项目');
INSERT OR IGNORE INTO th_suite(project_id,code,name,testcase_dir) VALUES
 (1,'API_SMOKE','接口冒烟套件','testcases');
INSERT OR IGNORE INTO th_task(project_id,suite_id,name,cron,enabled) VALUES
 (1,1,'接口冒烟定时任务','',1);
"""


def connect():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def init_db():
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.executescript(SEED)
        conn.commit()
    finally:
        conn.close()
