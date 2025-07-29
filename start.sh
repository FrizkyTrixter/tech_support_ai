#!/usr/bin/env bash
set -e

# 1) Start the FastAPI‑powered server in the background
echo "🟢 Starting Python FastAPI server on http://localhost:8000..."
uvicorn server:app --reload &
BACKEND_PID=$!

# When this script exits, kill the backend
trap "echo '🔴 Shutting down backend…'; kill $BACKEND_PID" EXIT

# 2) Give Uvicorn a second to spin up
sleep 2

# 3) Move into the Next.js frontend and start it
echo "🟢 Starting Next.js dev server on http://localhost:3000..."
cd my-helpdesk-ui
npm run dev

