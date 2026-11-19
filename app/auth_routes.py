"""Self-service sign-up (email + password) and Google sign-in.

Safety rules baked in:
  * Sign-up can NEVER choose a role or department: every new account is an `employee` in SIGNUP_DEPARTMENT
    (default "general"), which only sees company-wide documents. An admin promotes/moves people later.
  * SIGNUP_MODE=approval (default) creates the account inactive; an admin activates it on the Users page.
  * Local sign-ups have an UNVERIFIED email. If that email later signs in with Google, the account's password is
    reset, so someone who pre-registered another person's email cannot keep access ("pre-hijacking").
  * Google uses the server-side authorization-code flow: no Google script runs in the browser, so the strict
    Content-Security-Policy is unchanged. The JWT is handed to the page through a one-time code, never in a URL.
"""
import hmac
import re
import secrets
import sqlite3
import time
from collections import defaultdict
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from . import audit
from .config import (
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_ENABLED, GOOGLE_REDIRECT_URI,
    SIGNUP_DEPARTMENT, SIGNUP_EMAIL_DOMAINS, SIGNUP_MODE, SIGNUP_RATE_PER_HOUR,
)
from .db import db
from .security import create_token, hash_password

router = APIRouter(prefix="/api")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,64}$")
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}


@router.get("/auth/config")
def auth_config():
    """Public: tells the login page which options to show."""
    return {"signup": SIGNUP_MODE, "google": GOOGLE_ENABLED}


# ------------------------------------------------------------------ email sign-up
_signup_hits: dict[str, list[float]] = defaultdict(list)


def _rate_limited(ip: str) -> bool:
    now = time.time()
    _signup_hits[ip] = [t for t in _signup_hits[ip] if now - t < 3600]
    if len(_signup_hits[ip]) >= SIGNUP_RATE_PER_HOUR:
        return True
    _signup_hits[ip].append(now)
    return False


class SignupIn(BaseModel):
    # Loose types on purpose: we validate by hand so the page gets a readable message, not a 422 list.
    username: str = ""
    email: str = ""
    password: str = ""


def _domain_ok(email: str) -> bool:
    return not SIGNUP_EMAIL_DOMAINS or email.rsplit("@", 1)[-1] in SIGNUP_EMAIL_DOMAINS


@router.post("/signup", status_code=201)
def signup(body: SignupIn, request: Request):
    if SIGNUP_MODE == "off":
        raise HTTPException(403, "Sign-up is turned off. Ask an administrator to create your account.")
    ip = request.client.host if request.client else "unknown"
    if _rate_limited(ip):
        raise HTTPException(429, "Too many sign-up attempts. Try again in an hour.")
    username, email, password = body.username.strip(), body.email.strip().lower(), body.password
    if not USERNAME_RE.match(username):
        raise HTTPException(422, "Username must be 3 to 64 characters: letters, numbers, dot, dash or underscore.")
    if len(email) > 254 or not EMAIL_RE.match(email):
        raise HTTPException(422, "Enter a valid email address.")
    if not _domain_ok(email):
        raise HTTPException(403, "Sign-up is limited to these email domains: " + ", ".join(sorted(SIGNUP_EMAIL_DOMAINS)))
    if len(password) < 8 or len(password.encode()) > 72:
        raise HTTPException(422, "Password must be 8 to 72 characters.")

    active = 1 if SIGNUP_MODE == "open" else 0
    taken = HTTPException(409, "That username or email is already registered.")
    pw_hash = hash_password(password)
    try:
        with db() as conn:
            # SQLite's UNIQUE is case-sensitive; also block "Admin" vs "admin" look-alikes.
            if conn.execute("SELECT 1 FROM users WHERE lower(username)=lower(?) OR lower(email)=?", (username, email)).fetchone():
                raise taken
            cur = conn.execute(
                "INSERT INTO users (username, email, email_verified, password_hash, role, department, is_active) VALUES (?,?,0,?,?,?,?)",
                (username, email, pw_hash, "employee", SIGNUP_DEPARTMENT, active),
            )
            uid = cur.lastrowid
    except sqlite3.IntegrityError:
        raise taken
    audit.log(action="signup", decision="allowed", username=username, detail=f"mode={SIGNUP_MODE}")
    if active:
        return {"status": "active", "access_token": create_token(uid), "token_type": "bearer"}
    return {"status": "pending", "message": "Account created. An administrator must approve it before you can sign in."}


# ------------------------------------------------------------------ Google sign-in
_codes: dict[str, tuple[int, float]] = {}  # one-time login codes (in-memory: single-process demo setup)


def _fail(reason: str) -> RedirectResponse:
    resp = RedirectResponse(f"/#sso_error={reason}", status_code=302)
    resp.delete_cookie("g_state")
    return resp


@router.get("/auth/google/login")
def google_login():
    if not GOOGLE_ENABLED:
        raise HTTPException(404, "Google sign-in is not configured")
    state = secrets.token_urlsafe(32)
    params = {"client_id": GOOGLE_CLIENT_ID, "redirect_uri": GOOGLE_REDIRECT_URI, "response_type": "code",
              "scope": "openid email profile", "state": state, "prompt": "select_account"}
    resp = RedirectResponse(GOOGLE_AUTH_URL + "?" + urlencode(params), status_code=302)
    resp.set_cookie("g_state", state, max_age=600, httponly=True, samesite="lax", secure=GOOGLE_REDIRECT_URI.startswith("https://"))
    return resp


def _unique_username(conn, email: str) -> str:
    base = re.sub(r"[^A-Za-z0-9_.-]", "", email.split("@", 1)[0])[:40]
    base = base if len(base) >= 3 else (base + "user")[:40]
    name, i = base, 1
    while conn.execute("SELECT 1 FROM users WHERE lower(username)=lower(?)", (name,)).fetchone():
        i += 1
        name = f"{base}{i}"
    return name


def _google_claims(code: str) -> dict | None:
    """Exchange the code. The ID token comes straight from Google's token endpoint over TLS, so (per OpenID Connect
    Core 3.1.3.7) we validate its claims instead of re-verifying the signature."""
    try:
        r = httpx.post(GOOGLE_TOKEN_URL, timeout=10, data={
            "code": code, "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI, "grant_type": "authorization_code"})
        r.raise_for_status()
        claims = jwt.decode(r.json()["id_token"], options={"verify_signature": False})
    except Exception:
        return None
    if claims.get("aud") != GOOGLE_CLIENT_ID or claims.get("iss") not in GOOGLE_ISSUERS:
        return None
    if float(claims.get("exp", 0)) < time.time() or claims.get("email_verified") is not True:
        return None
    if not claims.get("sub") or not claims.get("email"):
        return None
    return claims


@router.get("/auth/google/callback")
def google_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if not GOOGLE_ENABLED:
        raise HTTPException(404, "Google sign-in is not configured")
    if error:
        return _fail("cancelled")
    cookie = request.cookies.get("g_state", "")
    if not code or not state or not cookie or not hmac.compare_digest(state, cookie):
        return _fail("state")  # CSRF / expired / opened in another browser
    claims = _google_claims(code)
    if claims is None:
        return _fail("google")
    sub, email = claims["sub"], claims["email"].strip().lower()
    if not _domain_ok(email):
        audit.log(action="login_failed", decision="denied", username=email, detail="google: email domain not allowed")
        return _fail("domain")

    created = False
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE google_sub=?", (sub,)).fetchone()
        if row is None:
            row = conn.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
            if row is not None:
                if row["google_sub"] not in (None, sub):
                    return _fail("google")
                # Unverified local sign-up with this email: cut off whoever chose that password.
                new_hash = hash_password(secrets.token_urlsafe(32)) if not row["email_verified"] else row["password_hash"]
                conn.execute("UPDATE users SET google_sub=?, email_verified=1, password_hash=? WHERE id=?", (sub, new_hash, row["id"]))
            elif SIGNUP_MODE == "off":
                return _fail("closed")
            else:
                cur = conn.execute(
                    "INSERT INTO users (username, email, email_verified, google_sub, password_hash, role, department, is_active) VALUES (?,?,1,?,?,?,?,?)",
                    (_unique_username(conn, email), email, sub, hash_password(secrets.token_urlsafe(32)), "employee", SIGNUP_DEPARTMENT,
                     1 if SIGNUP_MODE == "open" else 0))
                created = True
            row = conn.execute("SELECT * FROM users WHERE google_sub=?", (sub,)).fetchone()
    if created:  # logged after the transaction closes: a second connection would hit SQLite's write lock
        audit.log(action="signup", decision="allowed", username=email, detail=f"google;mode={SIGNUP_MODE}")
    if not row["is_active"]:
        audit.log(action="login_failed", decision="denied", username=row["username"], detail="google: account inactive or pending approval")
        return _fail("inactive")

    now = time.time()
    for k in [k for k, (_, exp) in _codes.items() if exp < now]:
        del _codes[k]
    one_time = secrets.token_urlsafe(32)
    _codes[one_time] = (row["id"], now + 60)
    resp = RedirectResponse(f"/#sso={one_time}", status_code=302)
    resp.delete_cookie("g_state")
    return resp


class ExchangeIn(BaseModel):
    code: str


@router.post("/auth/exchange")
def exchange(body: ExchangeIn):
    entry = _codes.pop(body.code, None)  # single use
    if entry is None or entry[1] < time.time():
        raise HTTPException(401, "That sign-in link expired. Try again.")
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (entry[0],)).fetchone()
    if row is None or not row["is_active"]:
        raise HTTPException(401, "That account is not active.")
    audit.log(action="login", decision="allowed", user=dict(row), detail="google")
    return {"access_token": create_token(row["id"]), "token_type": "bearer"}
