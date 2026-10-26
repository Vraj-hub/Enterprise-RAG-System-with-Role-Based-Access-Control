import os
import sys
import tempfile
from pathlib import Path

# Must be set BEFORE the app is imported
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="rag_test_")
os.environ["EMBEDDER"] = "hash"
os.environ["OLLAMA_URL"] = "http://127.0.0.1:9"  # unreachable on purpose -> extractive fallback
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    import seed
    from app.main import app

    seed.main()
    return TestClient(app)


def login(client, username, password):
    r = client.post("/api/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def tokens(client):
    return {
        "admin": login(client, "admin", "Admin@12345"),
        "eng_mgr": login(client, "eng_mgr", "Manager@12345"),
        "eng_emp": login(client, "eng_emp", "Employee@12345"),
        "hr_emp": login(client, "hr_emp", "Employee@12345"),
        "hr_mgr": login(client, "hr_mgr", "Manager@12345"),
    }
