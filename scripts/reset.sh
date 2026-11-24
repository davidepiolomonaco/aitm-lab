#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a
[[ ! -f "$ROOT/.env" ]] || source "$ROOT/.env"
set +a

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  BOLD=$'\e[1m'; DIM=$'\e[2m'; RED=$'\e[31m'; YELLOW=$'\e[33m'
  CYAN=$'\e[36m'; GREEN=$'\e[32m'; RESET_C=$'\e[0m'
else
  BOLD=''; DIM=''; RED=''; YELLOW=''; CYAN=''; GREEN=''; RESET_C=''
fi

if [[ "${1:-}" != "--yes" ]]; then
 echo "${BOLD}${RED}⚠ WARNING:${RESET_C}${RED} deletes the local Allsafe PostgreSQL database and all demo sessions.${RESET_C}"
 read -r -p "Type ${BOLD}${YELLOW}RESET${RESET_C} to confirm: " reply
 [[ "$reply" == RESET ]] || exit 1
fi

echo "${DIM}Ensuring the aitm-relay-net network exists…${RESET_C}"
docker network inspect aitm-relay-net >/dev/null 2>&1 || docker network create --internal aitm-relay-net >/dev/null

echo "${CYAN}▸ Tearing down and rebuilding the legitimate stack…${RESET_C}"
docker-compose -f "$ROOT/legitimate/compose.yaml" down -v
docker-compose -f "$ROOT/legitimate/compose.yaml" up -d --build

# Recreate the phishing relay so Docker drops its stdout logs: the monitor
# replays each service's last log lines (docker-compose logs --tail), so
# without this the old credentials_captured / session_hijacked events keep
# showing up after a reset. The loot_data volume is preserved on purpose
# (captured sessions survive for the Burp Suite follow-up) — no `-v` here.
echo "${CYAN}▸ Recreating the phishing relay stack (clears monitor history, keeps loot)…${RESET_C}"
docker-compose -f "$ROOT/phishing/compose.yaml" up -d --build --force-recreate

echo "${GREEN}✓ Reset complete.${RESET_C}"
echo "${DIM}Loot preserved. To wipe captured sessions too: docker-compose -f phishing/compose.yaml down -v${RESET_C}"
