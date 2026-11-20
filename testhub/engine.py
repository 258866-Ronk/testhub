"""Real engine: run AutoTest Pro CLI in an isolated work dir, parse report.json."""
import os, json, socket, shutil, subprocess, time
from . import config


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def run_engine(run_no, mode):
    """Returns stats dict. Raises RuntimeError on PLATFORM fault (retryable)."""
    if not os.path.exists(config.ENGINE_CLI):
        raise RuntimeError("engine CLI not found: " + config.ENGINE_CLI)
    work = os.path.join(config.WORK_ROOT, run_no)
    os.makedirs(work, exist_ok=True)
    # configuration snapshot: copy testcases + environments
    for folder in ("testcases", "environments"):
        src = os.path.join(config.ENGINE_SOURCE, folder)
        if os.path.isdir(src):
            dest = os.path.join(work, folder)
            if os.path.isdir(dest):
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
    snapshot = {"runNo": run_no, "mode": mode, "engineCli": config.ENGINE_CLI,
                "sourceRoot": config.ENGINE_SOURCE, "capturedAt": time.strftime("%Y-%m-%d %H:%M:%S")}
    with open(os.path.join(work, "config-snapshot.json"), "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, ensure_ascii=False, indent=2)

    port = _free_port()
    report_path = os.path.join(work, "report.json")
    # invoke the CLI module directly so ALL args (--port/--report-json/--out) are parsed.
    cli_root = os.path.dirname(config.ENGINE_CLI) if config.ENGINE_CLI.endswith("run_demo.py") else config.ENGINE_SOURCE
    cmd = [config.ENGINE_PYTHON, "-m", "autotest.cli", "--mode", mode, "--root",
           os.path.join(cli_root, "testcases"), "--env", os.path.join(cli_root, "environments", "default.yaml"),
           "--port", str(port), "--report-json", report_path, "--out", os.path.join(work, "reports")]
    with open(os.path.join(work, "command.txt"), "w", encoding="utf-8") as fh:
        fh.write(" ".join(cmd))
    log_path = os.path.join(work, "engine.log")
    started = time.perf_counter()
    with open(log_path, "w", encoding="utf-8") as log:
        try:
            proc = subprocess.Popen(cmd, cwd=config.ENGINE_SOURCE, stdout=log,
                                    stderr=subprocess.STDOUT)
            proc.wait(timeout=config.TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise RuntimeError("engine timeout after %ds" % config.TIMEOUT_SEC)
    duration_ms = int((time.perf_counter() - started) * 1000)
    if not os.path.exists(report_path):
        raise RuntimeError("engine produced no report.json (rc=%s)" %
                           (proc.returncode if 'proc' in dir() else '?'))
    with open(report_path, "r", encoding="utf-8") as fh:
        report = json.load(fh)
    if "total" not in report or report["total"] == 0:
        raise RuntimeError("invalid report: total=0")
    return {"total": report["total"], "passed": report["passed"],
            "failed": report["failed"], "pass_rate": report["passRate"],
            "duration_ms": duration_ms, "cases": report["cases"]}
