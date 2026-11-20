from testhub import store


def test_idempotency():
    a = store.create_run(1, "TEST-IDEM-1", "sequential")
    b = store.create_run(1, "TEST-IDEM-1", "sequential")
    assert a["run_no"] == b["run_no"]
    assert b["created"] is False
