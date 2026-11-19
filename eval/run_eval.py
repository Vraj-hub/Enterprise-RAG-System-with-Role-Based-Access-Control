"""Retrieval evaluation. Run from the project root:  python -m eval.run_eval
Add your own questions to eval/questions.json (expect_doc / forbidden_doc / expect_none).
Measures retrieval hit rate, unauthorized-retrieval rate (must be 0) and latency. It does not call the LLM."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import retrieval
from app.db import db

cases = json.loads((Path(__file__).parent / "questions.json").read_text())
with db() as conn:
    users = {r["username"]: dict(r) for r in conn.execute("SELECT * FROM users")}
hits_ok = leaks = total_expect = 0; lat = []
for c in cases:
    t = time.perf_counter(); res = retrieval.hybrid_search(c["q"], users[c["user"]]); lat.append((time.perf_counter() - t) * 1000)
    names = [h["filename"] for h in res]; status = "ok"
    if "expect_doc" in c:
        total_expect += 1
        if c["expect_doc"] in names: hits_ok += 1
        else: status = "MISS"
    if c.get("forbidden_doc") in names: leaks += 1; status = "LEAK"
    if c.get("expect_none") and names: status = "UNEXPECTED_HIT"
    print(f"{status:15} {c['user']:8} {c['q'][:40]:40} -> {names[:3]}")
lat.sort()
print(f"\nretrieval hit rate : {hits_ok}/{total_expect}\nunauthorized leaks : {leaks} (must be 0)\nlatency median     : {lat[len(lat)//2]:.0f} ms")
sys.exit(1 if leaks else 0)
