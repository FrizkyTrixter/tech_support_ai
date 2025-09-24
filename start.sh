#!/usr/bin/env bash
set -e

# Avoid pulling in torchvision via transformers (we only need text)
export TRANSFORMERS_NO_TORCHVISION=1

# If you use a venv, uncomment:
# source .venv/bin/activate

# 1) Start the FastAPI-powered server in the background
echo "🟢 Starting Python FastAPI server on http://localhost:8000..."
uvicorn server:app --reload &
BACKEND_PID=$!

# Kill backend when this script exits
trap "echo '🔴 Shutting down backend…'; kill $BACKEND_PID" EXIT

# 2) Give Uvicorn a second to spin up
sleep 2

# 3) Move into the Next.js frontend and start it
echo "🟢 Starting Next.js dev server on http://localhost:3000..."
cd my-helpdesk-ui
npm run dev

