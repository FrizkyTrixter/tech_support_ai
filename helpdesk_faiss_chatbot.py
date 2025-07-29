import pandas as pd
import faiss
import numpy as np
import requests
from sentence_transformers import SentenceTransformer

# === CONFIG ===
CSV_PATH = "grouped_conversations.csv"
TOP_K = 3
LLM_CONTEXT_LIMIT = 2000  # characters to feed to LLaMA
OLLAMA_MODEL = "llama3"   # or "llama3:8b" / "llama3:70b" etc.

# === Load Helpdesk Conversations ===
df = pd.read_csv(CSV_PATH)
texts = df["actionbody"].tolist()

# === Load Sentence Transformer ===
print("Loading sentence embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")
embeddings = model.encode(texts, convert_to_numpy=True)

# === Build FAISS Index ===
dimension = embeddings.shape[1]
index = faiss.IndexFlatL2(dimension)
index.add(embeddings)

# === LLaMA 3 via Ollama ===
def generate_llama_response(prompt: str):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        }
    )
    if response.status_code == 200:
        return response.json()["response"].strip()
    else:
        raise RuntimeError(f"Ollama API error: {response.status_code} - {response.text}")

# === Helpdesk Query Function ===
def search_helpdesk(query):
    query_embedding = model.encode([query])
    distances, indices = index.search(np.array(query_embedding), TOP_K)

    best_idx = indices[0][0]
    best_text = df.iloc[best_idx]["actionbody"]

    if len(best_text) > LLM_CONTEXT_LIMIT:
        best_text = best_text[:LLM_CONTEXT_LIMIT]

    # Prompt to LLaMA 3
    prompt = f"""
You are an expert IT helpdesk agent.

The following is a historical helpdesk ticket conversation:
---
{best_text}
---

A user now asks: "{query}"

Based on the above, summarize the issue and resolution, then write a helpful and friendly support reply for the user.
"""

    reply = generate_llama_response(prompt)

    print(f"\n🔎 Query: {query}")
    print(f"\n🤖 LLaMA 3 via Ollama says:\n{reply}\n")

# === CLI Chat Loop ===
if __name__ == "__main__":
    print("🧠 Helpdesk Chatbot (FAISS + Ollama LLaMA 3) is ready!")
    while True:
        user_query = input("Ask a helpdesk question (or type 'exit'): ")
        if user_query.lower() == "exit":
            break
        search_helpdesk(user_query)

