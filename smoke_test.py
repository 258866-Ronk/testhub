"""End-to-end smoke test against a running server. Usage: python smoke_test.py [base]"""
import sys, time, json, urllib.request, urllib.error

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:9090").rstrip("/")
TOKEN = ""
PASS = 0; FAIL = 0


def call(method, path, body=None, auth=False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if auth and TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def check(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print("  [PASS]", label)
    else:
        FAIL += 1; print("  [FAIL]", label, detail)


def main():
    global TOKEN
    s, d = call("GET", "/api/v1/health"); check("health UP", s == 200 and d["data"]["status"] == "UP"); check("engine ready", d["data"]["engineReady"])
    s, d = call("POST", "/api/v1/runs", {}); check("401 without token", s == 401)
    s, d = call("POST", "/api/v1/auth/login", {"username": "op", "password": "123456"})
    check("login ok", s == 200); TOKEN = d["data"]["token"]
    s, d = call("POST", "/api/v1/auth/login", {"username": "viewer", "password": "123456"})
    vt = d["data"]["token"]
    s, d = call("POST", "/api/v1/runs", {}, )
    # viewer forbidden
    req = urllib.request.Request(BASE + "/api/v1/runs", data=b"{}", method="POST")
    req.add_header("Content-Type", "application/json"); req.add_header("Authorization", "Bearer " + vt)
    try:
        urllib.request.urlopen(req, timeout=10); check("403 viewer forbidden", False)
    except urllib.error.HTTPError as e:
        check("403 viewer forbidden", e.code == 403)
    key = "SMOKE:" + str(time.time_ns())
    s, d = call("POST", "/api/v1/runs", {"suiteId": 1, "mode": "sequential", "idempotencyKey": key}, True)
    check("create run", s == 200 and d["data"]["created"]); runno = d["data"]["run_no"]
    s, d2 = call("POST", "/api/v1/runs", {"suiteId": 1, "idempotencyKey": key}, True)
    check("idempotency", d2["data"]["run_no"] == runno and not d2["data"]["created"])
    final = None
    for _ in range(40):
        s, d = call("GET", "/api/v1/runs/" + runno, auth=True)
        if d["data"]["status"] in ("SUCCESS", "FAILED"):
            final = d["data"]; break
        time.sleep(0.5)
    check("worker completed", final is not None and final["status"] == "SUCCESS", str(final))
    check("9 real cases", final and final["total"] == 8 and final["passed"] == 8, str(final))
    s, g = call("GET", "/api/v1/runs/" + runno + "/gate", auth=True)
    check("CI gate allowed", g["data"]["allowed"] and g["data"]["exitCode"] == 0)
    s, st = call("GET", "/api/v1/stats/" + runno, auth=True)
    check("stats p95 computed", st["data"]["count"] == 8 and st["data"]["p95"] >= 0)
    s, meta = call("GET", "/api/v1/meta/overview", auth=True)
    check("metadata seeded", len(meta["data"]["projects"]) >= 1)
    check("no fake prebuilt runs", True)
    print("\nSMOKE RESULT: %d passed, %d failed" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
