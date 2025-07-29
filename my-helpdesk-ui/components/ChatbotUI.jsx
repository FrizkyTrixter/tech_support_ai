'use client';

import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Send } from 'lucide-react';

export default function ChatbotUI() {
  const [messages, setMessages] = useState([
    { from: 'ai', text: 'Hello! How can I assist you today?' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const containerRef = useRef(null);

  // Scroll on new messages
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim()) return;
    const userMsg = { from: 'user', text: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: input }),
      });
      const { reply } = await res.json();
      setMessages(prev => [...prev, { from: 'ai', text: reply }]);
    } catch {
      setMessages(prev => [
        ...prev,
        { from: 'ai', text: 'Oops, something went wrong.' }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-xl bg-[#002B55] rounded-2xl shadow-2xl flex flex-col h-[80vh] p-6">
        <div
          ref={containerRef}
          className="flex-1 overflow-y-auto space-y-4 mb-4 px-2"
        >
          {messages.map((msg, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
              className={`flex ${
                msg.from === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              <div
                className={`max-w-[80%] p-3 rounded-2xl ${
                  msg.from === 'user'
                    ? 'bg-blue-500 text-white'
                    : 'bg-white text-black'
                }`}
              >
                {msg.text}
              </div>
            </motion.div>
          ))}
        </div>
        <div className="flex space-x-2">
          <input
            className="flex-1 p-3 rounded-xl border border-gray-300 focus:outline-none focus:ring"
            placeholder="Type your message..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && sendMessage()}
            disabled={loading}
          />
          <button
            onClick={sendMessage}
            disabled={loading}
            className="p-3 rounded-xl bg-blue-500 text-white disabled:opacity-50"
          >
            <Send size={20} />
          </button>
        </div>
      </div>
    </div>
  );
}
