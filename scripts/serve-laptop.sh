#!/usr/bin/env bash
# Demo hosting: run the Lantern server (real ML models) on this machine and expose it over HTTPS with ngrok.
#   NGROK_DOMAIN=lyricism-thus-subscript.ngrok-free.dev scripts/serve-laptop.sh
# The tourist app on GitHub Pages is built against this domain:
#   VITE_API_URL=https://$NGROK_DOMAIN scripts/deploy-pages.sh
# Twilio sandbox webhook: https://$NGROK_DOMAIN/twilio/whatsapp
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOMAIN="${NGROK_DOMAIN:?set NGROK_DOMAIN to your ngrok domain, e.g. lyricism-thus-subscript.ngrok-free.dev}"
PORT="${PORT:-8000}"

ngrok http "$PORT" --url "https://$DOMAIN" --log stdout --log-format logfmt >"$ROOT/server/data/ngrok.log" 2>&1 &
NGROK_PID=$!
trap 'kill $NGROK_PID 2>/dev/null' EXIT
echo "Tourist API + host page: https://$DOMAIN  (hosts: https://$DOMAIN/host)"

cd "$ROOT/server"
MOCK_AI="${MOCK_AI:-false}" PUBLIC_BASE_URL="https://$DOMAIN" .venv/bin/uvicorn app.main:app --port "$PORT"
