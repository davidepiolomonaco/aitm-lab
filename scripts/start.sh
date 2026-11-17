#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a
[[ ! -f "$ROOT/.env" ]] || source "$ROOT/.env"
set +a

docker network inspect aitm-relay-net >/dev/null 2>&1 || docker network create --internal aitm-relay-net >/dev/null

case "${1:-all}" in
  legitimate) docker-compose -f "$ROOT/legitimate/compose.yaml" up -d --build ;;
  phishing) docker-compose -f "$ROOT/phishing/compose.yaml" up -d --build ;;
  all) docker-compose -f "$ROOT/legitimate/compose.yaml" up -d --build
       docker-compose -f "$ROOT/phishing/compose.yaml" up -d --build ;;
  *) echo 'Usage: scripts/start.sh [legitimate | phishing | all]' >&2;exit 2 ;;
esac
