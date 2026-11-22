#!/usr/bin/env bash
# Start the local API and web app. Both bind to 127.0.0.1 only.
set -euo pipefail
cd "$(dirname "$0")/.."

for endpoint in mortality icu; do
  if [[ ! -f "${PREOPXAI_ARTIFACTS:-artifacts}/$endpoint/metadata.json" ]]; then
    echo "Model artifacts are missing. Run: make export-models" >&2
    exit 1
  fi
done
[[ -d app/web/node_modules ]] || npm --prefix app/web ci

uv run --locked --group app uvicorn app.api.main:create_app --factory --host 127.0.0.1 --port 8000 &
api=$!
trap 'kill "$api" 2>/dev/null || true' EXIT INT TERM

for _ in {1..120}; do
  (exec 3<>/dev/tcp/127.0.0.1/8000) 2>/dev/null && break
  kill -0 "$api" 2>/dev/null || { echo "The API failed to start." >&2; exit 1; }
  sleep 0.5
done

echo "PreOp-XAI: http://127.0.0.1:5173 (research prototype, not for clinical use)"
npm --prefix app/web run dev
