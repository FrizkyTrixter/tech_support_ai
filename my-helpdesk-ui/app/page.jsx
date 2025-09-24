// app/page.jsx
'use client';

import { useEffect, useRef, useState } from 'react';

const BACKEND_URL = 'http://127.0.0.1:8000';

export default function Home() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: "Hi! I'm your IT Helpdesk bot. How can I help you today?" }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const logRef = useRef(null);
  const sseRef = useRef(null);

  // Auto-scroll when messages change
  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  // Append text to the last assistant message (create one if missing)
  const appendAssistant = (text) => {
    setMessages((prev) => {
      const out = [...prev];
      if (!out.length || out[out.length - 1].role !== 'assistant') {
        out.push({ role: 'assistant', content: '' });
      }
      out[out.length - 1] = {
        ...out[out.length - 1],
        content: (out[out.length - 1].content || '') + text,
      };
      return out;
    });
  };

  async function onSubmit(e) {
    e.preventDefault();
    const userText = input.trim();
    if (!userText) return;

    // Close any previous stream
    if (sseRef.current) {
      sseRef.current.close();
      sseRef.current = null;
    }

    setInput('');
    setMessages((m) => [
      ...m,
      { role: 'user', content: userText },
      { role: 'assistant', content: '' },
    ]);
    setLoading(true);

    // Connect SSE: GET /chat-sse?q=...
    const url = `${BACKEND_URL}/chat-sse?q=${encodeURIComponent(userText)}`;
    const es = new EventSource(url, { withCredentials: false });
    sseRef.current = es;

    es.onmessage = (evt) => {
      if (evt.data === '[END]') {
        es.close();
        sseRef.current = null;
        setLoading(false);
        return;
      }
      appendAssistant(evt.data);
    };

    es.onerror = () => {
      appendAssistant('\n[stream closed]');
      es.close();
      sseRef.current = null;
      setLoading(false);
    };
  }

  return (
    <main className="chat-wrap">
      <section className="chat-card">
        <header className="chat-header">
          <span className="msg-avatar bot">IT</span>
          <span>IT Helpdesk Bot</span>
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
