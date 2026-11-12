#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a
[[ ! -f "$ROOT/.env" ]] || source "$ROOT/.env"
set +a

if [[ "${1:-}" != "--yes" ]]; then
 echo 'WARNING: deletes the local Allsafe PostgreSQL database and all demo sessions.'
 read -r -p 'Type RESET to confirm: ' reply
 [[ "$reply" == RESET ]] || exit 1
fi

docker-compose -f "$ROOT/legitimate/compose.yaml" down -v
docker-compose -f "$ROOT/legitimate/compose.yaml" up -d --build
