import { NextResponse } from 'next/server';

export async function POST(request) {
  const { message } = await request.json();

  const res = await fetch('http://localhost:11434/api/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: 'llama3', prompt: message, stream: false }),
  });

  const json = await res.json();
  return NextResponse.json({ reply: json.response.trim() });
}
