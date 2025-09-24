# server.py
# ──────────────────────────────────────────────────────────────────────────────
# FastAPI backend for IT Helpdesk AI with TRUE streaming from Ollama → SSE
# - POST /query    : full JSON reply
# - GET  /chat-sse : Server-Sent Events (flushes each token immediately)
# ──────────────────────────────────────────────────────────────────────────────

import os
os.environ.setdefault("TRANSFORMERS_NO_TORCHVISION", "1")  # avoid torchvision import issues

from typing import AsyncIterator, Dict, Any

import asyncio
import json
import logging
import numpy as np
import httpx  # async HTTP client for streaming with Ollama

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

# ── Project imports (provided by your repo)
from helpdesk_faiss_chatbot import (
    model,                    # sentence-transformers model
    df,                       # dataframe with historical conversations
    index,                    # FAISS index
    TOP_K,                    # top-k neighbors
    LLM_CONTEXT_LIMIT,        # character/token budget for history
)

# ──────────────────────────────────────────────────────────────────────────────
# Config — tune these if you hit memory issues
# ──────────────────────────────────────────────────────────────────────────────
OLLAMA_URL   = "http://127.0.0.1:11434/api/generate"
MODEL_NAME   = os.getenv("HELPDESK_MODEL", "llama3.2:3b-instruct-q4_K_M")  # light + fast
NUM_CTX      = int(os.getenv("HELPDESK_NUM_CTX", "1024"))
NUM_PREDICT  = int(os.getenv("HELPDESK_NUM_PREDICT", "512"))
TEMPERATURE  = float(os.getenv("HELPDESK_TEMP", "0.2"))

# ──────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="IT Helpdesk API", version="1.1.0")

# CORS for Next.js dev on 3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

log = logging.getLogger("uvicorn.error")


# ──────────────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., description="User's query")


# ──────────────────────────────────────────────────────────────────────────────
# Retrieval + Prompt
# ──────────────────────────────────────────────────────────────────────────────

def retrieve_history(query: str) -> str:
    """Return best matching prior helpdesk conversation text (or empty on failure)."""
    try:
        q_emb = model.encode([query], convert_to_numpy=True)
        distances, indices = index.search(np.array(q_emb), int(TOP_K))
        best_idx = int(indices[0][0])
        history = str(df.iloc[best_idx]["actionbody"])
    except Exception:
        log.exception("Retrieval failed")
        history = ""
    if history and LLM_CONTEXT_LIMIT:
        history = history[: int(LLM_CONTEXT_LIMIT)]
    return history


def build_prompt(history: str, user_msg: str) -> str:
    return f"""You are an expert IT helpdesk agent.

The following is a historical helpdesk ticket conversation:
---
{history}
---

A user now asks: "{user_msg}"

Based on the above, summarize the issue and resolution (if applicable), then write a helpful and friendly support reply for the user. If the history is not directly relevant, still provide a best-effort, step-by-step IT troubleshooting answer.
"""


# ──────────────────────────────────────────────────────────────────────────────
# Ollama streaming → async generator (yields tokens as they arrive)
# Ollama /api/generate with "stream": true returns NDJSON lines like:
#   {"model":"...","created_at":"...","response":"He","done":false}
#   {"model":"...","created_at":"...","response":"llo","done":false}
#   ...
#   {"done":true, "total_duration":..., ...}
# ──────────────────────────────────────────────────────────────────────────────

async def ollama_stream(prompt: str) -> AsyncIterator[str]:
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": True,
        "options": {
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
            "temperature": TEMPERATURE,
        },
    }
    timeout = httpx.Timeout(60.0, read=60.0, write=60.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", OLLAMA_URL, json=payload) as resp:
            # Propagate Ollama errors (e.g., OOM)
            if resp.status_code >= 400:
                text = await resp.aread()
                raise HTTPException(
                    status_code=500,
                    detail=f"Ollama API error: {resp.status_code} - {text.decode(errors='ignore')}",
                )

            buffer = b""
            async for chunk in resp.aiter_bytes():
                if not chunk:
                    continue
                buffer += chunk
                # split by newlines (NDJSON)
                while True:
                    nl = buffer.find(b"\n")
                    if nl == -1:
                        break
                    line = buffer[:nl].decode("utf-8", errors="ignore").strip()
                    buffer = buffer[nl + 1:]
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        # If non-JSON text sneaks in, yield it anyway
                        yield line
                        continue

                    # Normal incremental token
                    if not obj.get("done"):
                        piece = obj.get("response", "")
                        if piece:
                            yield piece
                    else:
                        # done message: stop
                        return


# ──────────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=PlainTextResponse)
def root():
    return "IT Helpdesk API is running. See /docs."

@app.get("/health", response_class=JSONResponse)
def health():
    return {"status": "ok"}

@app.post("/query")
async def post_query(req: ChatRequest) -> Dict[str, Any]:
    """
    Non-streaming endpoint. Returns full reply as JSON.
    Body: {"message": "..."}
    """
    user_msg = (req.message or "").strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Missing 'message'")

    history = retrieve_history(user_msg)
    prompt = build_prompt(history, user_msg)

    # If you want to call Ollama non-streaming here, you can, but to keep simple:
    # we'll stream then join (so both code paths share the same logic).
    try:
        out = []
        async for tok in ollama_stream(prompt):
            out.append(tok)
        reply = "".join(out)
    except HTTPException:
        raise
    except Exception as e:
        log.exception("LLM generation failed")
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    return {"reply": reply}

@app.get("/chat-sse")
async def chat_sse(q: str):
    """
    Server-Sent Events endpoint used by the Next.js UI.
    Connect with: GET /chat-sse?q=...
    Sends 'data: <token>\\n\\n' as soon as Ollama emits it,
    then finishes with 'data: [END]\\n\\n'.
    """
    user_msg = (q or "").strip()
    if not user_msg:
        return StreamingResponse(iter(["data: [error] missing query\n\n"]),
                                 media_type="text/event-stream")

    history = retrieve_history(user_msg)
    prompt = build_prompt(history, user_msg)

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for token in ollama_stream(prompt):
                # one token per SSE frame → browser flushes immediately
                yield f"data: {token}\n\n"
                await asyncio.sleep(0)  # allow event loop to flush
            yield "data: [END]\n\n"
        except HTTPException as he:
            yield f"data: [Backend error] {he.detail}\n\n"
        except Exception as e:
            yield f"data: [Backend error] {str(e)}\n\n"

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_stream(),
                             media_type="text/event-stream",
                             headers=headers)
