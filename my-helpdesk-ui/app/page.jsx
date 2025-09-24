'use client';

import { useEffect, useRef, useState } from 'react';

const BACKEND_URL = 'http://127.0.0.1:8000';
const PATH = '/chat'; // change if your FastAPI route differs

export default function Home() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: "Hi! I'm your IT Helpdesk bot. How can I help you today?" }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const logRef = useRef(null);

  // Auto-scroll
  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  // Append text to the last assistant message (create one if missing)
  const appendAssistant = (chunk) => {
    setMessages((prev) => {
      let out = [...prev];
      if (!out.length || out[out.length - 1].role !== 'assistant') {
        out.push({ role: 'assistant', content: '' });
      }
      out[out.length - 1] = {
        ...out[out.length - 1],
        content: (out[out.length - 1].content || '') + chunk
      };
      return out;
    });
  };

  // Typewriter fallback if server returns a full string
  const typewriter = async (text, delay = 18) => {
    for (let i = 0; i < text.length; i++) {
      appendAssistant(text[i]);
      await new Promise((r) => setTimeout(r, delay));
    }
  };

  async function onSubmit(e) {
    e.preventDefault();
    const userText = input.trim();
    if (!userText) return;

    setInput('');
    setMessages((m) => [...m, { role: 'user', content: userText }]);
    setLoading(true);

    try {
      const res = await fetch(BACKEND_URL + PATH, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userText }),
      });

      // If we can stream, read chunks and render live
      if (res.ok && res.body) {
        // Start an empty assistant message to stream into
        setMessages((m) => [...m, { role: 'assistant', content: '' }]);

        const reader = res.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buf = '';

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });

          // Try to handle NDJSON / SSE-like lines and plain text
          let idx;
          while ((idx = buf.indexOf('\n')) >= 0) {
            const line = buf.slice(0, idx).trim();
            buf = buf.slice(idx + 1);
            if (!line) continue;

            // Allow a few common formats:
            // 1) raw text chunk
            // 2) JSON lines: { "delta": "..." } or { "text": "..." }
            // 3) SSE: data: { "delta": "..." }
            let payload = line;
            if (line.startsWith('data:')) payload = line.slice(5).trim();

            try {
              const obj = JSON.parse(payload);
              const delta = obj.delta ?? obj.text ?? obj.chunk ?? '';
              if (delta) appendAssistant(delta);
            } catch {
              // not JSON, treat as raw text
              appendAssistant(payload);
            }
          }
        }

        // Flush any remainder
        if (buf.trim()) {
          try {
            const obj = JSON.parse(buf.trim());
            const delta = obj.delta ?? obj.text ?? obj.chunk ?? '';
            appendAssistant(delta || buf);
          } catch {
            appendAssistant(buf);
          }
        }
      } else {
        // Fallback: full JSON, then type to screen
        const data = await res.json().catch(() => ({}));
        const text =
          data?.answer ?? data?.response ?? data?.message ?? JSON.stringify(data);
        // Start the assistant bubble, then type it out
        setMessages((m) => [...m, { role: 'assistant', content: '' }]);
        await typewriter(text);
      }
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: `Sorry, I hit an error: ${err?.message ?? err}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="chat-wrap">
      <section className="chat-card">
        <header className="chat-header">
          <span className="msg-avatar bot">IT</span>
          IT Helpdesk Bot
        </header>

        <div ref={logRef} className="chat-log">
          {messages.map((m, i) => (
            <div key={i} className={`msg-row ${m.role}`}>
              {m.role === 'assistant' && <span className="msg-avatar bot">IT</span>}
              <div className={`bubble ${m.role}`}>{m.content}</div>
              {m.role === 'user' && <span className="msg-avatar">U</span>}
            </div>
          ))}

          {loading && (
            <div className="msg-row assistant">
              <span className="msg-avatar bot">IT</span>
              <div className="bubble bot">…thinking</div>
            </div>
          )}
        </div>

        <div className="chat-input-bar">
          <form className="chat-form" onSubmit={onSubmit}>
            <input
              className="chat-input"
              type="text"
              placeholder="Type your IT question…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
            />
            <button className="chat-btn" type="submit" disabled={loading}>
              {loading ? 'Sending…' : 'Send'}
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}
