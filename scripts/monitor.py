#!/usr/bin/env python3
#Read-only Rich monitor of Allsafe demo events (no secrets but tokens).

import json
import queue
import subprocess
import threading
from collections import deque
from pathlib import Path

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

ROOT = Path(__file__).resolve().parent.parent
entries = deque(maxlen=40)
events = queue.Queue()
last_capture = None  # most recent session_hijacked event, for the panel below the table

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


def render():
    table = Table(title="Allsafe — authentication & relay events")

    for field in ("Time", "Source", "Event", "Account", "Token"):
        table.add_column(field)

    for item in list(entries):
        table.add_row(
            item["timestamp"][11:19],
            item["source"],
            item["kind"],
            item.get("username") or "—",
            item.get("sid") or "—",
        )

    if last_capture is None:
        panel = Panel(
            "No session exfiltrated yet — submit the demo credentials on http://127.0.0.1:8082",
            title="Last captured session (for Burp Suite)",
            border_style="grey50",
        )
    else:
        body = (
            f"[bold]Account:[/bold]  {last_capture.get('username')}\n"
            f"[bold]Replay header:[/bold]  Cookie: {last_capture.get('replay_header')}\n"
            f"[bold]Replay target:[/bold]  GET {last_capture.get('replay_url', '')}\n"
            f"[dim]Paste the Cookie header above into Burp Suite's Repeater against the replay target.[/dim]"
        )
        panel = Panel(body, title="Last captured session (for Burp Suite)", border_style="red")

    return Group(table, panel)


def follow(source, cfg):
    cmd = [
        "docker", "compose", "-f", str(cfg["compose"]),
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
