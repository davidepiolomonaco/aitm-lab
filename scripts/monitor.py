#!/usr/bin/env python3
"""Read-only Rich monitor of Allsafe demo authentication events (no secrets)."""
import json
import subprocess
import threading
from collections import deque
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.table import Table

ROOT = Path(__file__).resolve().parent.parent
entries = deque(maxlen=30)

def render():
    table = Table(title="Allsafe — authentication events")
    
    for field in ("Time", "Event", "Account"):
        table.add_column(field)
    
    for item in list(entries):
        table.add_row(item["timestamp"][11:19], item["kind"], item.get("username") or "—")
    return table

def main():
    cmd = [
            "docker", "compose", "-f", str(ROOT / "legitimate/compose.yaml"),
           "logs", "--follow", "--tail", "20", "--no-color", "app"
    ]

    Console().print("Monitoring Allsafe events. Ctrl+C to exit.")
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    
    try:
        with Live(render(), refresh_per_second=3) as live:
            for line in process.stdout:
                chunk = line.split(" | ", 1)[-1].strip()
                try:
                    event = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict) and event.get("kind") in {
                    "login_success", 
                    "login_denied", 
                    "logout", 
                    "database_ready"
                }:
                    entries.append(event)
                    live.update(render())
    except KeyboardInterrupt:
        pass
    finally:
        process.terminate()
        try: process.wait(timeout=2)
        except subprocess.TimeoutExpired: process.kill()

if __name__ == "__main__":
    main()
