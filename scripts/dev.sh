#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_DIR="$ROOT_DIR/backend"

echo "========================================="
echo "   Repomedic Local Development Runner    "
echo "========================================="

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "[!] Installing frontend dependencies..."
    npm --prefix "$FRONTEND_DIR" install
fi

echo "[*] Launching frontend developer server..."
npm --prefix "$FRONTEND_DIR" run dev &
FRONTEND_PID=$!

echo "[*] Frontend running on PID $FRONTEND_PID"
echo "    Visit: http://localhost:5173"

cleanup() {
    echo "Stopping frontend server..."
    kill $FRONTEND_PID 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait $FRONTEND_PID
