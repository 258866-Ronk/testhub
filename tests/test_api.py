import pytest
from testhub.api import app
from testhub.db import init_db

@pytest.fixture
def client():
    init_db()
    app.config["TESTING"] = True
    return app.test_client()


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.get_json()["data"]["status"] == "UP"


def test_rbac(client):
    r = client.post("/api/v1/runs", json={})
    assert r.status_code == 401
    tok = client.post("/api/v1/auth/login",
                      json={"username": "viewer", "password": "123456"}).get_json()["data"]["token"]
    r = client.post("/api/v1/runs", json={}, headers={"Authorization": "Bearer " + tok})
    assert r.status_code == 403
