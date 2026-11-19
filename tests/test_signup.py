"""Self-service sign-up must never be a way around role/department access control."""

PW = "Passw0rd!"


def signup(client, username, email, **extra):
    return client.post("/api/signup", json={"username": username, "email": email, "password": PW, **extra})


def test_config_reports_signup_mode_and_google_off(client):
    r = client.get("/api/auth/config").json()
    assert r["signup"] == "open" and r["google"] is False


def test_signup_ignores_attempts_to_choose_role_or_department(client):
    r = signup(client, "sneaky_user", "sneaky@example.com", role="admin", department="hr")
    assert r.status_code == 201 and r.json()["status"] == "active"
    headers = {"Authorization": "Bearer " + r.json()["access_token"]}
    me = client.get("/api/me", headers=headers).json()
    assert me["role"] == "employee" and me["department"] == "general"


def test_new_account_sees_only_company_wide_documents(client):
    r = signup(client, "fresh_user", "fresh@example.com")
    headers = {"Authorization": "Bearer " + r.json()["access_token"]}
    names = {d["filename"] for d in client.get("/api/documents", headers=headers).json()}
    assert "hr_salary_bands.txt" not in names and "engineering_runbook.txt" not in names and "acquisition_plan.txt" not in names
    assert "company_handbook.txt" in names


def test_duplicate_email_or_lookalike_username_rejected(client):
    assert signup(client, "dup_one", "dup@example.com").status_code == 201
    assert signup(client, "dup_two", "DUP@example.com").status_code == 409
    assert signup(client, "DUP_ONE", "other@example.com").status_code == 409
    assert signup(client, "ADMIN", "fake-admin@example.com").status_code == 409


def test_validation_messages_are_plain_strings(client):
    for body in ({"username": "ab", "email": "a@b.com"}, {"username": "valid_name", "email": "nope"}, {"username": "valid_name", "email": "a@b.com", "password": "x"}):
        r = client.post("/api/signup", json={"password": PW, **body})
        assert r.status_code == 422 and isinstance(r.json()["detail"], str)


def test_login_works_with_email_or_username(client):
    signup(client, "mail_login", "Mail.Login@example.com")
    for ident in ("mail_login", "mail.login@EXAMPLE.com"):
        assert client.post("/api/login", json={"username": ident, "password": PW}).status_code == 200


def test_admin_user_list_includes_email(client, tokens):
    users = client.get("/api/admin/users", headers=tokens["admin"]).json()
    assert any(u.get("email") == "mail.login@example.com" for u in users)


def test_google_routes_404_when_not_configured(client):
    assert client.get("/api/auth/google/login", follow_redirects=False).status_code == 404
