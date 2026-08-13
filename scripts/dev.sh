#!/usr/bin/env bash
# Start CUE: FastAPI on :8000, Next.js on :3000.
# Ctrl-C stops both.

set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"

# Load .env if present. This has to happen before uvicorn starts: app/config.py
# reads os.environ at import time, so a key exported after the process is up is
# invisible to it. Nothing else in the stack reads .env -- this is the only
# thing that makes the file mean anything.
if [ -f "$ROOT/.env" ]; then
  set -a  # export everything defined below
  # shellcheck disable=SC1091  # runtime file, not resolvable at lint time
  . "$ROOT/.env"
  set +a
  if [ -n "${ANTHROPIC_API_KEY:-}" ] || [ -n "${OPENAI_API_KEY:-}" ]; then
    echo "Loaded .env (LLM key found — enhancement layer will be active)"
  else
    echo "Loaded .env (no LLM key set — running deterministic-only)"
  fi
fi

LAN_IP=$(python3 -c "
import socket
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('8.8.8.8', 80))
    print(s.getsockname()[0]); s.close()
except Exception:
    print('127.0.0.1')
")

cleanup() {
  echo ""
  echo "Shutting down..."
  [ -n "${BACK_PID:-}" ] && kill "$BACK_PID" 2>/dev/null
  [ -n "${FRONT_PID:-}" ] && kill "$FRONT_PID" 2>/dev/null
  wait 2>/dev/null
  exit 0
}
trap cleanup INT TERM

echo "Starting CUE backend on :8000 ..."
(cd "$ROOT/backend" && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000) &
BACK_PID=$!

# Wait for the API to answer before starting the UI, so the dashboard's first
# paint has data instead of an error state.
for _ in $(seq 1 40); do
  if curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1; then break; fi
  sleep 0.5
done

echo "Starting CUE frontend on :3000 ..."
(cd "$ROOT/frontend" && npm run dev -- --port 3000 --hostname 0.0.0.0) &
FRONT_PID=$!

cat <<EOF

  CUE is running.

    Guest (phone)     http://${LAN_IP}:3000
    DJ dashboard      http://localhost:3000/dj
    Presenter screen  http://localhost:3000/present
    API health        http://localhost:8000/api/health

  Phones must be on the same wifi as this machine.
  Ctrl-C to stop.

EOF

wait
