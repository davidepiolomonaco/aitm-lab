#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a
[[ ! -f "$ROOT/.env" ]] || source "$ROOT/.env"
set +a

case "${1:-all}" in
  legitimate) docker-compose -f "$ROOT/legitimate/compose.yaml" down ;;
  simulation) docker-compose -f "$ROOT/phishing/compose.yaml" down ;;
  all) docker-compose -f "$ROOT/legitimate/compose.yaml" down
       docker-compose -f "$ROOT/phishing/compose.yaml" down ;;
  *) echo 'Usage: scripts/stop.sh [legitimate | simulation | all]' >&2;exit 2 ;;
esac
