import os
import sys

sys.path.append(os.getcwd())

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

def test_healthcheck_get():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_healthcheck_post_not_allowed():
    response = client.post("/health")
    assert response.status_code == 405
