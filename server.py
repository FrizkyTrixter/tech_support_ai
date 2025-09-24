# server.py
# ──────────────────────────────────────────────────────────────────────────────
# FastAPI backend for IT Helpdesk AI (FAISS retrieval + LLM reply)
# - /query : JSON reply (full text)
# - /chat  : Streaming reply (newline-delimited chunks) for "typing" UI
# ──────────────────────────────────────────────────────────────────────────────

import os
# Avoid pulling in torchvision via transformers if not needed (prevents nms errors)
os.environ.setdefault("TRANSFORMERS_NO_TORCHVISION", "1")

from typing import AsyncIterator, Dict, Any

import asyncio
import logging
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

# Your project imports (assumed available)
from helpdesk_faiss_chatbot import (
    generate_llama_response,  # LLM call
    model,                    # sentence-transformers model
    df,                       # conversations dataframe
    index,                    # FAISS index
    TOP_K,                    # top-k neighbors to retrieve
    LLM_CONTEXT_LIMIT,        # char or token cutoff
)

# ──────────────────────────────────────────────────────────────────────────────
# App + CORS
# ──────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="IT Helpdesk API", version="1.0.0")

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
# Retrieval + Prompt building
# ──────────────────────────────────────────────────────────────────────────────

def retrieve_history(query: str) -> str:
    """Return the best matching prior helpdesk conversation text."""
    try:
        # Encode and search FAISS
        q_emb = model.encode([query], convert_to_numpy=True)
        distances, indices = index.search(np.array(q_emb), int(TOP_K))
        # Take best hit
        best_idx = int(indices[0][0])
        history = str(df.iloc[best_idx]["actionbody"])
    except Exception as e:
        log.exception("Retrieval failed")
        # Don’t crash—return empty history; LLM can still answer generically
        history = ""
    # Trim to context budget
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
# Streaming helpers
# ──────────────────────────────────────────────────────────────────────────────

def chunk_text(s: str, n: int = 24):
    """Yield ~n-sized chunks of s (nice for typing effect)."""
    for i in range(0, len(s), n):
        yield s[i : i + n]

async def stream_from_full_text(s: str, delay_sec: float = 0.0) -> AsyncIterator[str]:
    """Stream a precomputed string in small chunks."""
    for ch in chunk_text(s, 24):
        yield ch + "\n"
        if delay_sec:
            await asyncio.sleep(delay_sec)

# If your generate_llama_response supports streaming,
# you can swap in a generator here (left as fallback-ready).


# ──────────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=PlainTextResponse)
def root():
    return "IT Helpdesk API is running. See /docs for Swagger."

@app.get("/health", response_class=JSONResponse)
def health():
    return {"status": "ok"}

@app.post("/query")
async def post_query(req: ChatRequest) -> Dict[str, Any]:
    """
    Non-streaming endpoint. Returns the full reply as JSON.
    Body: {"message": "..."}
    """
    user_msg = (req.message or "").strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Missing 'message'")

    history = retrieve_history(user_msg)
    prompt = build_prompt(history, user_msg)

    try:
        reply = generate_llama_response(prompt)  # returns a string
    except Exception as e:
        log.exception("LLM generation failed")
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    return {"reply": reply}


@app.post("/chat")
async def post_chat(request: Request):
    """
    Streaming endpoint for ChatGPT-style typing.
    Accepts either {"query": "..."} or {"message": "..."}.
    Streams newline-delimited text chunks (media_type text/plain).
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    user_msg = (data.get("query") or data.get("message") or "").strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Missing 'query' or 'message'")

    history = retrieve_history(user_msg)
    prompt = build_prompt(history, user_msg)

    async def streamer() -> AsyncIterator[str]:
        """
        Try to stream. If your LLM helper only returns full text,
        we still stream it chunk-by-chunk for a typing effect.
        """
        try:
            # Attempt plain (non-streaming) generation first
            text = generate_llama_response(prompt)
            async for piece in stream_from_full_text(text):
                yield piece
        except TypeError:
            # Example pattern if you add a streaming API later:
            # for token in generate_llama_response(prompt, stream=True):
            #     yield (token if isinstance(token, str) else str(token)) + "\n"
            raise
        except Exception as e:
            err = f"[Backend error] {e}"
            log.exception("Streaming failed")
            # Send the error to the client as a final line
            yield err + "\n"

    return StreamingResponse(streamer(), media_type="text/plain")
