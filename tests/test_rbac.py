import jwt

from app.config import JWT_ALGORITHM


def ask(client, headers, q):
    r = client.post("/api/query", json={"question": q}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def sources(resp):
    return {s["filename"] for s in resp["sources"]}


# ---------- the core guarantee: restricted content is never retrieved ----------
def test_employee_cannot_see_salary_or_acquisition(client, tokens):
    r = ask(client, tokens["eng_emp"], "What is the salary band for a Senior Engineer?")
    assert "hr_salary_bands.txt" not in sources(r)
    assert "lakh" not in r["answer"]
    r = ask(client, tokens["eng_emp"], "How much will NovaStack acquisition cost?")
    assert "acquisition_plan.txt" not in sources(r)
    assert "120 crore" not in r["answer"]


def test_hr_manager_sees_salary_but_not_acquisition(client, tokens):
    r = ask(client, tokens["hr_mgr"], "What is the salary band for a Senior Engineer?")
    assert "hr_salary_bands.txt" in sources(r)
    r = ask(client, tokens["hr_mgr"], "How much will NovaStack acquisition cost?")
    assert "acquisition_plan.txt" not in sources(r)


def test_hr_employee_blocked_from_confidential_even_in_own_department(client, tokens):
    r = ask(client, tokens["hr_emp"], "What is the salary band for a Senior Engineer?")
    assert "hr_salary_bands.txt" not in sources(r)


def test_cross_department_internal_doc_blocked(client, tokens):
    r = ask(client, tokens["hr_emp"], "When do production deployments happen?")
    assert "engineering_runbook.txt" not in sources(r)
    r = ask(client, tokens["eng_emp"], "When do production deployments happen?")
    assert "engineering_runbook.txt" in sources(r)


def test_admin_sees_everything(client, tokens):
    r = ask(client, tokens["admin"], "How much will NovaStack acquisition cost?")
    assert "acquisition_plan.txt" in sources(r)


def test_public_doc_visible_to_all(client, tokens):
    for who in ("eng_emp", "hr_emp", "hr_mgr"):
        r = ask(client, tokens[who], "How many days of annual leave do employees get?")
        assert "company_handbook.txt" in sources(r)


# ---------- authentication ----------
def test_no_token_rejected(client):
    assert client.post("/api/query", json={"question": "hello there"}).status_code == 401


def test_forged_token_rejected(client):
    forged = jwt.encode({"sub": "1", "exp": 9999999999}, "wrong-secret-wrong-secret-wrong-secret-0123456789", algorithm=JWT_ALGORITHM)
    r = client.get("/api/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_expired_token_rejected(client):
    from app.config import JWT_SECRET

    expired = jwt.encode({"sub": "1", "exp": 1}, JWT_SECRET, algorithm=JWT_ALGORITHM)
    assert client.get("/api/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_wrong_password(client):
    assert client.post("/api/login", json={"username": "admin", "password": "nope"}).status_code == 401


# ---------- authorization on endpoints ----------
def test_employee_cannot_upload(client, tokens):
    r = client.post(
        "/api/documents", headers=tokens["eng_emp"],
        files={"file": ("x.txt", b"hello world content here")},
        data={"department": "engineering", "sensitivity": "internal"},
    )
    assert r.status_code == 403


def test_manager_cannot_upload_other_department_or_restricted(client, tokens):
    f = {"file": ("x.txt", b"some text for the document")}
    r = client.post("/api/documents", headers=tokens["eng_mgr"], files=f, data={"department": "hr", "sensitivity": "internal"})
    assert r.status_code == 403
    r = client.post("/api/documents", headers=tokens["eng_mgr"], files=f, data={"department": "engineering", "sensitivity": "restricted"})
    assert r.status_code == 403


def test_manager_upload_then_employee_can_query_it(client, tokens):
    r = client.post(
        "/api/documents", headers=tokens["eng_mgr"],
        files={"file": ("vpn_guide.txt", b"The VPN gateway address is vpn.example.internal. Use port 4443 for the secure tunnel.")},
        data={"department": "engineering", "sensitivity": "internal", "allowed_roles": "employee,manager,admin"},
    )
    assert r.status_code == 201, r.text
    res = ask(client, tokens["eng_emp"], "What port does the VPN secure tunnel use?")
    assert "vpn_guide.txt" in sources(res)
    res = ask(client, tokens["hr_emp"], "What port does the VPN secure tunnel use?")
    assert "vpn_guide.txt" not in sources(res)


def test_embedding_failure_returns_service_unavailable(client, tokens, monkeypatch):
    from app import vectorstore

    def fail_indexing(*args, **kwargs):
        raise RuntimeError("Ollama embeddings failed")

    monkeypatch.setattr(vectorstore, "add_chunks", fail_indexing)
    r = client.post(
        "/api/documents", headers=tokens["eng_mgr"],
        files={"file": ("embedding_failure.txt", b"Valid document content for indexing.")},
        data={"department": "engineering", "sensitivity": "internal"},
    )
    assert r.status_code == 503
    assert "Ollama embeddings failed" in r.json()["detail"]


def test_bad_extension_rejected(client, tokens):
    r = client.post("/api/documents", headers=tokens["admin"], files={"file": ("evil.exe", b"MZ....")},
                    data={"department": "all", "sensitivity": "public"})
    assert r.status_code == 400


def test_non_admin_cannot_view_audit_or_users(client, tokens):
    assert client.get("/api/admin/audit", headers=tokens["eng_mgr"]).status_code == 403
    assert client.get("/api/admin/users", headers=tokens["eng_emp"]).status_code == 403


def test_document_list_is_filtered(client, tokens):
    names = {d["filename"] for d in client.get("/api/documents", headers=tokens["eng_emp"]).json()}
    assert "company_handbook.txt" in names and "engineering_runbook.txt" in names
    assert "hr_salary_bands.txt" not in names and "acquisition_plan.txt" not in names


# ---------- immediate effect of role changes + audit ----------
def test_demotion_takes_effect_immediately_and_audit_records_blocks(client, tokens):
    r = client.post("/api/admin/users", headers=tokens["admin"],
                    json={"username": "temp_mgr", "password": "TempPass123", "role": "manager", "department": "hr"})
    assert r.status_code == 201
    uid = r.json()["id"]
    h = {"Authorization": "Bearer " + client.post("/api/login", json={"username": "temp_mgr", "password": "TempPass123"}).json()["access_token"]}
    assert "hr_salary_bands.txt" in sources(ask(client, h, "What is the salary band for a Senior Engineer?"))
    client.patch(f"/api/admin/users/{uid}", headers=tokens["admin"], json={"role": "employee"})
    # same token, now an employee -> must lose access without logging in again
    assert "hr_salary_bands.txt" not in sources(ask(client, h, "What is the salary band for a Senior Engineer?"))

    logs = client.get("/api/admin/audit?limit=500", headers=tokens["admin"]).json()
    blocked = [l for l in logs if l["username"] == "temp_mgr" and l["action"] == "query"]
    assert blocked and blocked[0]["blocked_candidates"] >= 1  # newest first: the post-demotion query


def test_login_throttle(client):
    codes = [client.post("/api/login", json={"username": "hr_emp", "password": "bad"}).status_code for _ in range(7)]
    assert codes[-1] == 429
