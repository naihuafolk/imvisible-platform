"""
Backend tests (CI) — ครอบคลุม endpoint ใหม่ของชั้น commercial + functional:
โควตาแพ็กเกจ · usage/plans · credentials (per-tenant) · Stripe webhook (ลายเซ็นจริง) ·
legal + consent · AEO score / SEO audit · schedule · approve

ใช้ sqlite ชั่วคราว + stub .delay (ไม่ต้องมี Redis) + stub connector ที่ยิงเน็ต
รัน (จาก backend):  python tests/test_commercial.py
"""
import asyncio
import json
import os
import sys
import tempfile
import time

_DB = os.path.join(tempfile.gettempdir(), f"rp_comm_{int(time.time())}.db")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///" + _DB.replace("\\", "/"))
os.environ.setdefault("JWT_SECRET", "test-secret-please-32bytes-long-xxxx")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_123")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_x")
os.environ.setdefault("STRIPE_PRICE_PRO", "price_pro_1")
os.environ.setdefault("RATE_LIMIT_PER_MIN", "500")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient   # noqa: E402
import app.db.session as db                 # noqa: E402
import app.worker.tasks as tasks            # noqa: E402
import app.connectors.publish as publish    # noqa: E402
from app.connectors import billing          # noqa: E402


class _FakeTask:                             # ให้ endpoint ที่อ่าน task.id ทำงานได้โดยไม่ต้องมี Redis
    id = "test-task"


def _fake_delay(*a, **k):
    return _FakeTask()


for _name in ("analyze_project", "produce_for_project", "approve_article", "optimize_article",
              "distribute_article", "measure_rank", "sample_citations_for_project"):
    getattr(tasks, _name).delay = _fake_delay


async def _noop_indexnow(url):
    return {"ok": True}


publish.indexnow_submit = _noop_indexnow

from app.main import app                     # noqa: E402
from app.db.models import Article            # noqa: E402


async def _add_article(project_id, **kw):
    async with db.session() as s:
        a = Article(project_id=project_id, **kw)
        s.add(a)
        await s.commit()
        await s.refresh(a)
        return a.id


def run():
    asyncio.run(db.create_all())
    with TestClient(app) as c:
        # --- register requires consent (PDPA) ---
        assert c.post("/api/auth/register", json={"email": "a@t.com", "password": "secret123"}).status_code == 422
        reg = c.post("/api/auth/register", json={"email": "a@t.com", "password": "secret123", "name": "A", "accept_terms": True})
        assert reg.status_code == 200, reg.text
        h = {"Authorization": "Bearer " + reg.json()["token"]}

        # --- plans + usage + quota (free = 1 project) ---
        assert [p["key"] for p in c.get("/api/plans").json()["plans"]] == ["free", "pro", "business"]
        u = c.get("/api/usage", headers=h).json()
        assert u["plan"] == "free" and u["projects"]["limit"] == 1
        pid = c.post("/api/projects", headers=h, json={"domain": "abc.com"}).json()["id"]
        assert c.post("/api/projects", headers=h, json={"domain": "b.com"}).status_code == 402

        # --- legal pages ---
        assert c.get("/legal/terms").status_code == 200
        assert "PDPA" in c.get("/legal/privacy").text

        # --- per-tenant credentials: set + honest source + no secret leak + ownership ---
        r = c.put("/api/projects/%d/credentials" % pid, headers=h, json={"kind": "dataforseo", "fields": {"login": "L", "password": "P"}})
        assert r.status_code == 200 and r.json()["status"]["dataforseo"]["source"] == "project"
        assert "L" not in r.text and "P" not in r.text
        assert c.put("/api/projects/%d/credentials" % pid, headers=h, json={"kind": "evil", "fields": {}}).status_code == 422
        h2 = {"Authorization": "Bearer " + c.post("/api/auth/register", json={"email": "z@t.com", "password": "secret123", "accept_terms": True}).json()["token"]}
        assert c.get("/api/projects/%d/credentials" % pid, headers=h2).status_code == 404

        # --- Stripe webhook: valid signature upgrades; bad signature rejected ---
        body = json.dumps({"type": "checkout.session.completed", "data": {"object": {
            "client_reference_id": "1", "customer": "cus_1", "subscription": "sub_1",
            "metadata": {"plan": "pro", "user_id": "1"}}}}).encode()
        sig = billing.sign_payload(body, int(time.time()))
        assert c.post("/api/billing/webhook", content=body, headers={"stripe-signature": sig}).status_code == 200
        assert c.get("/api/usage", headers=h).json()["plan"] == "pro"
        assert c.post("/api/billing/webhook", content=body, headers={"stripe-signature": "t=1,v1=bad"}).status_code == 400

        # --- AEO score + SEO audit (real numbers from DB) ---
        good = ("<p>AEO คือการปรับให้ AI อ้างอิง เน้นคำตอบตรง เหมาะธุรกิจไทยปี 2026 วัดผลได้จริงมากและคุ้มค่า</p>"
                "<h2>คำถามที่พบบ่อย</h2><h3>นานไหม</h3><p>4-8 สัปดาห์</p><ul><li>a</li></ul>" + "<p>" + ("ลึก " * 90) + "</p>")
        aid = asyncio.run(_add_article(pid, title="AEO คืออะไร", slug="aeo-1", html=good,
                                       schema_json='{"@type":"FAQPage"}', description="คู่มือ",
                                       cover_url="x", cluster="AEO", status="published", url="https://abc.com/a/1", words=1200))
        pj = c.get("/api/projects/%d/aeo" % pid, headers=h).json()
        assert pj["count"] == 1 and pj["avg_score"] is not None
        art = c.get("/api/articles/%d/aeo" % aid, headers=h).json()
        assert len(art["factors"]) == 14
        audit = c.get("/api/projects/%d/seo-audit" % pid, headers=h).json()
        assert audit["articles"] == 1 and audit["schema_coverage"] == 100

        # --- schedule a draft (endpoint sets scheduled + validates time) ---
        did = asyncio.run(_add_article(pid, title="ตั้งเวลา", slug="s-1", html="<p>x</p>", status="draft", words=700))
        assert c.put("/api/articles/%d/schedule" % did, headers=h, json={"at": "2026-08-01T09:00"}).status_code == 200
        assert c.put("/api/articles/%d/schedule" % did, headers=h, json={"at": "bad"}).status_code == 422

        # --- drafts list + approve endpoint (queues) ---
        drafts = c.get("/api/projects/%d/drafts" % pid, headers=h).json()["drafts"]
        assert c.post("/api/articles/%d/approve" % did, headers=h).json()["queued"] is True

        # --- usage endpoint unauthorized ---
        assert c.get("/api/usage").status_code in (401, 403)

    print("BACKEND COMMERCIAL TESTS OK — quotas + billing + creds + legal + aeo + schedule")


if __name__ == "__main__":
    run()
