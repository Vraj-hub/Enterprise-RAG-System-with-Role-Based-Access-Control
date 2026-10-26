"""Create demo users and load the sample documents.  Run:  python seed.py"""
from pathlib import Path

from app import ingest
from app.db import db, init_db
from app.security import hash_password

USERS = [
    ("admin",    "Admin@12345",   "admin",    "it"),
    ("eng_mgr",  "Manager@12345", "manager",  "engineering"),
    ("eng_emp",  "Employee@12345", "employee", "engineering"),
    ("hr_mgr",   "Manager@12345", "manager",  "hr"),
    ("hr_emp",   "Employee@12345", "employee", "hr"),
]

# filename, department, sensitivity, allowed roles
DOCS = [
    ("company_handbook.txt",   "all",         "public",       ["employee", "manager", "admin"]),
    ("engineering_runbook.txt", "engineering", "internal",     ["employee", "manager", "admin"]),
    ("hr_salary_bands.txt",    "hr",          "confidential", ["manager", "admin"]),
    ("acquisition_plan.txt",   "all",         "restricted",   ["admin"]),
]


def main():
    init_db()
    with db() as conn:
        for u, p, role, dept in USERS:
            if not conn.execute("SELECT 1 FROM users WHERE username=?", (u,)).fetchone():
                conn.execute(
                    "INSERT INTO users (username, password_hash, role, department) VALUES (?,?,?,?)",
                    (u, hash_password(p), role, dept),
                )
        admin = dict(conn.execute("SELECT * FROM users WHERE username='admin'").fetchone())
        existing = {r["filename"] for r in conn.execute("SELECT filename FROM documents")}
    for fname, dept, sens, roles in DOCS:
        if fname in existing:
            continue
        data = (Path(__file__).parent / "sample_docs" / fname).read_bytes()
        ingest.ingest_document(filename=fname, data=data, owner=admin, department=dept, sensitivity=sens, allowed_roles=roles)
        print("ingested", fname)
    print("Demo users:")
    for u, p, role, dept in USERS:
        print(f"  {u:9} / {p:15} ({role}, {dept})")


if __name__ == "__main__":
    main()
