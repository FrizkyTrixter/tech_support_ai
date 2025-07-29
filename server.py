# server.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from helpdesk_faiss_chatbot import generate_llama_response, model, df, index, TOP_K, LLM_CONTEXT_LIMIT

import numpy as np

app = FastAPI()

class ChatRequest(BaseModel):
    message: str

@app.post("/query")
async def query_helpdesk(req: ChatRequest):
    q = req.message
    # 1) FAISS lookup
    q_emb = model.encode([q], convert_to_numpy=True)
    distances, indices = index.search(np.array(q_emb), TOP_K)
    best_idx = indices[0][0]
    history = df.iloc[best_idx]["actionbody"]
    if len(history) > LLM_CONTEXT_LIMIT:
        history = history[:LLM_CONTEXT_LIMIT]

    # 2) build prompt
    prompt = f"""
You are an expert IT helpdesk agent.

The following is a historical helpdesk ticket conversation:
---
{history}
---

A user now asks: "{q}"

Based on the above, summarize the issue and resolution, then write a helpful and friendly support reply for the user.
"""
    # 3) call LLaMA via Ollama
    try:
        reply = generate_llama_response(prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"reply": reply}

