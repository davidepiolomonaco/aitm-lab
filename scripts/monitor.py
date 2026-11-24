#!/usr/bin/env python3
#Read-only Rich monitor of Allsafe demo events (no secrets but tokens).

import json
import queue
import shutil
import subprocess
import threading
from collections import deque
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Per-cell styling for the events table.
SOURCE_STYLE = {"phishing": "red", "legitimate": "green"}
KIND_STYLE = {
    "credentials_captured": "bold red",
    "session_hijacked": "bold red",
    "relay_error": "bold yellow",
    "login_denied": "yellow",
    "login_denied_upstream": "yellow",
    "login_success": "green",
    "database_ready": "cyan",
    "logout": "dim",
}

ROOT = Path(__file__).resolve().parent.parent
entries = deque(maxlen=40)
events = queue.Queue()
last_capture = None  # most recent session_hijacked event, for the panel below the table

# Prefer the `docker compose` plugin; fall back to the standalone `docker-compose`.
if shutil.which("docker") and subprocess.run(
    ["docker", "compose", "version"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
).returncode == 0:
    COMPOSE = ["docker", "compose"]
elif shutil.which("docker-compose"):
    COMPOSE = ["docker-compose"]
else:
    raise SystemExit("Neither 'docker compose' nor 'docker-compose' is available on PATH.")

SOURCES = {
    "legitimate": {
        "compose": ROOT / "legitimate/compose.yaml",
        "service": "app",
        "kinds": {"login_success", "login_denied", "logout", "database_ready"},
    },
    "phishing": {
        "compose": ROOT / "phishing/compose.yaml",
        "service": "relay",
        "kinds": {"credentials_captured", "session_hijacked", "login_denied_upstream", "relay_error"},
    },
}


def local_time(ts):
    # Events carry a UTC ISO timestamp; show it in the host's local timezone.
    try:
        dt = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return ts[11:19]
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    return dt.strftime("%H:%M:%S")


def burp_request(capture):
    # Fall back to the known target for events captured before the relay
    # started emitting replay_url.
    url = capture.get("replay_url") or "http://127.0.0.1:8081/workspace"
    parsed = urlparse(url)
    host = parsed.netloc or "127.0.0.1:8081"
    path = parsed.path or "/workspace"
    cookie = capture.get("replay_header", "")
    return (
        f"GET {path} HTTP/1.1\n"
        f"Host: {host}\n"
        f"Cookie: {cookie}\n"
        "Connection: close\n"
    )


def render():
    table = Table(title="Allsafe — authentication & relay events", title_style="bold")

    for field in ("Time", "Source", "Event", "Account", "Token"):
        table.add_column(field)

    for item in list(entries):
        source = item["source"]
        kind = item["kind"]
        username = item.get("username")
        sid = item.get("sid")
        table.add_row(
            Text(local_time(item["timestamp"]), style="dim"),
            Text(source, style=SOURCE_STYLE.get(source, "")),
            Text(kind, style=KIND_STYLE.get(kind, "")),
            Text(username, style="magenta") if username else Text("—", style="dim"),
            Text(sid, style="yellow") if sid else Text("—", style="dim"),
        )

    if last_capture is None:
        panel = Panel(
            "No session exfiltrated yet — submit the demo credentials on http://127.0.0.1:8082",
            title="Last captured session (for Burp Suite)",
            border_style="grey50",
        )
    else:
        # Open-sided frame: only the top and bottom rules carry corners, there
        # are no │ side borders. The request lines therefore sit at column 0
        # with nothing to their left, so a mouse-selection copies them cleanly
        # into Burp instead of dragging in the panel borders.
        width = max(20, shutil.get_terminal_size((100, 24)).columns)
        label = f" Copy and paste this into Burp Repeater  ({last_capture.get('username')}) "
        # Title centered in the top rule, same red as the frame.
        inner = max(len(label), width - 2)
        pad = inner - len(label)
        left = pad // 2
        top = "┌" + "─" * left + label + "─" * (pad - left) + "┐"
        bottom = "└" + "─" * (width - 2) + "┘"
        panel = Group(
            Text(top, style="red", no_wrap=True, overflow="ignore"),
            Text(""),
            Text(burp_request(last_capture).rstrip("\n"), style="green", no_wrap=True, overflow="ignore"),
            Text(""),
            Text(bottom, style="red", no_wrap=True, overflow="ignore"),
        )

    return Group(table, panel)


def follow(source, cfg):
    cmd = [
        *COMPOSE, "-f", str(cfg["compose"]),
        "logs", "--follow", "--tail", "20", "--no-color", cfg["service"],
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    try:
        for line in process.stdout:
            chunk = line.split(" | ", 1)[-1].strip()
            try:
                event = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict) and event.get("kind") in cfg["kinds"]:
                event["source"] = source
                events.put(event)
    finally:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()


def main():
    global last_capture
    Console().print("Monitoring Allsafe legitimate + phishing relay events. Ctrl+C to exit.")

    threads = [
        threading.Thread(target=follow, args=(name, cfg), daemon=True)
        for name, cfg in SOURCES.items()
    ]
    for t in threads:
        t.start()

    try:
        with Live(render(), refresh_per_second=3) as live:
            while True:
                event = events.get()
                entries.append(event)
                if event.get("kind") == "session_hijacked":
                    last_capture = event
                live.update(render())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
