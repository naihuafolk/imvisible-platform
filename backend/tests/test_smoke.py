"""
Backend smoke test (CI + local): import + auth (hash/JWT) + register/login/me/projects
ใช้ฐานข้อมูล sqlite ชั่วคราว จึงไม่ต้องมี Postgres
รัน (จากโฟลเดอร์ backend):  python tests/test_smoke.py
"""
import os
import sys
import tempfile
import time

# ต้องตั้ง env ก่อน import app (settings อ่าน env ตอน import)
_DB = os.path.join(tempfile.gettempdir(), f"rp_test_{int(time.time())}.db")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///" + _DB.replace("\\", "/"))
os.environ.setdefault("JWT_SECRET", "test-secret")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient   # noqa: E402
from app.main import app                    # noqa: E402
from app.auth import security               # noqa: E402
import app.worker.tasks as _tasks           # noqa: E402

# ไม่พึ่ง Redis ในเทสต์: ให้ .delay() คืน task ปลอม (endpoint ที่อ่าน task.id ทำงานได้)
_tasks.analyze_project.delay = lambda *a, **k: type("T", (), {"id": "test"})()


def run():
    # 1) hash รหัสผ่าน
    h = security.hash_password("secret123")
    assert security.verify_password("secret123", h), "verify ที่ถูกต้องต้องผ่าน"
    assert not security.verify_password("wrong", h), "รหัสผิดต้องไม่ผ่าน"

    # 2) JWT roundtrip
    tok = security.create_token(1, "a@b.com")
    p = security.decode_token(tok)
    assert p["sub"] == "1" and p["email"] == "a@b.com"

    # 3) end-to-end auth + projects (sqlite จริง)
    with TestClient(app) as c:
        assert c.get("/health").json()["status"] == "ok"
        email = f"u{int(time.time()*1000)}@test.com"
        r = c.post("/api/auth/register", json={"email": email, "password": "secret123", "name": "U", "accept_terms": True})
        assert r.status_code == 200, r.text
        token = r.json()["token"]
        assert token
        hdr = {"Authorization": "Bearer " + token}

        me = c.get("/api/auth/me", headers=hdr)
        assert me.status_code == 200 and me.json()["email"] == email

        assert c.post("/api/auth/login", json={"email": email, "password": "secret123"}).status_code == 200
        assert c.post("/api/auth/login", json={"email": email, "password": "nope"}).status_code == 401

        cp = c.post("/api/projects", json={"name": "P1", "domain": "p1.com"}, headers=hdr)
        assert cp.status_code == 200, cp.text
        lp = c.get("/api/projects", headers=hdr)
        assert lp.status_code == 200 and len(lp.json()["projects"]) >= 1
        assert c.get("/api/projects").status_code == 401  # ไม่มี token ต้องถูกปฏิเสธ

    print("BACKEND SMOKE OK — auth + JWT + register/login/me/projects (sqlite) ผ่าน")


if __name__ == "__main__":
    run()
