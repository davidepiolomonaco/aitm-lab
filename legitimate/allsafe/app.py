import hashlib
import json
import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone

import psycopg
from flask import Flask, abort, make_response, redirect, render_template, request, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config.update(SEND_FILE_MAX_AGE_DEFAULT=0)
DATABASE_URL = os.environ["DATABASE_URL"]
DEMO_EMAIL = os.getenv("DEMO_EMAIL", "elliot@allsafe.test").lower()
DEMO_PASSWORD = os.environ["DEMO_PASSWORD"]
SESSION_TTL_MINUTES = int(os.getenv("SESSION_TTL_MINUTES", "45"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

logging.basicConfig(level=logging.INFO, format="%(message)s")

def connect():
    return psycopg.connect(DATABASE_URL)

def event(kind, username=None):
    # Never log passwords, tokens or cookies.
    app.logger.info(json.dumps({"kind": kind, "username": username, "timestamp": datetime.now(timezone.utc).isoformat()}))

def seed():
    for attempt in range(35):
        try:
            with connect() as db:
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id bigserial primary key, 
                        email text unique not null,
                        password_hash text not null, 
                        full_name text not null,
                        department text not null
                    )
                    """
                )

                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS active_sessions (
                        token_hash text primary key, 
                        user_id bigint not null references users(id),
                        expires_at timestamptz not null
                    )
                    """
                )
                
                db.execute(
                    """
                    INSERT INTO users(email,password_hash,full_name,department)
                    VALUES (%s,%s,%s,%s) ON CONFLICT(email) DO UPDATE SET
                    password_hash=excluded.password_hash
                    """,
                    (
                        DEMO_EMAIL, 
                        generate_password_hash(DEMO_PASSWORD),
                        "Elliot Alderson", 
                        "Information Security"
                    )
                )
            event("database_ready")
            return
        except psycopg.OperationalError:
            time.sleep(1)
    raise RuntimeError("Database unavailable")

seed()

def session_user():
    token = request.cookies.get("sid")
    if not token:
        return None
    
    digest = hashlib.sha256(token.encode()).hexdigest()
    
    with connect() as db:
        return db.execute(
            """
            SELECT u.id, u.email, u.full_name, u.department
            FROM active_sessions s JOIN users u ON u.id=s.user_id
            WHERE s.token_hash=%s AND s.expires_at > now()""", (digest,)
            ).fetchone()

def csrf():
    return request.cookies.get("csrf") or secrets.token_urlsafe(32)

def token_valid():
    cookie_value = request.cookies.get("csrf", "")
    posted_value = request.form.get("csrf_token", "")
    return bool(cookie_value and posted_value and secrets.compare_digest(cookie_value, posted_value))

def with_csrf(response, value):
    response.set_cookie(
        "csrf", 
        value, 
        httponly=True, 
        secure=COOKIE_SECURE,
        samesite="Strict", path="/"
    )
    
    return response

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def home():
    return redirect(url_for("workspace") if session_user() else url_for("login_form"))

@app.get("/login")
def login_form():
    if session_user():
        return redirect(url_for("workspace"))
    value = csrf()
    resp = make_response(render_template("login.html", csrf_token=value, error=None))
    return with_csrf(resp, value)

@app.post("/login")
def login():
    if not token_valid():
        abort(400, "Invalid form token")
    
    email = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "")
    
    with connect() as db:
        user = db.execute("SELECT id, password_hash FROM users WHERE email=%s", (email,)).fetchone()
    
    if not user or not check_password_hash(user[1], password):
        event("login_denied", email)
        value = csrf()
        resp = make_response(
            render_template(
                "login.html", 
                csrf_token=value,
                error="Invalid demo credentials"
            ), 
            401
        )

        return with_csrf(resp, value)
    
    token = secrets.token_urlsafe(32)
    expiry = datetime.now(timezone.utc) + timedelta(minutes=SESSION_TTL_MINUTES)
    
    with connect() as db:
        db.execute(
            "INSERT INTO active_sessions(token_hash,user_id,expires_at) VALUES (%s,%s,%s)",
            (
                hashlib.sha256(token.encode()).hexdigest(), 
                user[0], 
                expiry
            )
        )
    
    event("login_success", email)
    resp = make_response(redirect(url_for("workspace")))
    resp.set_cookie(
        "sid", 
        token, 
        httponly=True, 
        secure=COOKIE_SECURE, 
        samesite="Strict", 
        path="/", 
        max_age=SESSION_TTL_MINUTES * 60
    )
    
    return resp

@app.get("/workspace")
def workspace():
    user = session_user()
    
    if user is None:
        return redirect(url_for("login_form"))
    
    name = user[2]
    parts = name.split()
    
    details = {
        "email": user[1], 
        "full_name": name, 
        "department": user[3],
        "first_name": parts[0], 
        "initials": ''.join(p[0] for p in parts[:2]).upper()
    }
    
    value = csrf()
    resp = make_response(render_template("workspace.html", user=details, csrf_token=value))
    resp.headers["Cache-Control"] = "no-store"
    
    return with_csrf(resp, value)

@app.post("/logout")
def logout():
    if not token_valid():
        abort(400, "Invalid form token")
    token = request.cookies.get("sid")
    if token:
        with connect() as db:
            db.execute("DELETE FROM active_sessions WHERE token_hash=%s",
                       (hashlib.sha256(token.encode()).hexdigest(),))
    event("logout")
    resp = make_response(redirect(url_for("login_form")))
    resp.delete_cookie("sid", path="/")
    return resp

@app.after_request
def headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response
