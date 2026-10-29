import { once } from 'node:events';
import { createServer } from '../src/server.mjs';

// Optional real credential check. Prints neither provider nor app-access credentials.
if (!process.env.GEMINI_API_KEY?.trim() || !process.env.APP_ACCESS_TOKEN?.trim()) {
  console.error('Gemini key or private backend access token is missing.'); process.exit(1);
}
const server = createServer(); server.listen(0, '127.0.0.1'); await once(server, 'listening');
try {
  const url = `http://127.0.0.1:${server.address().port}/gemini/client-secret`;
  const unauthorized = await fetch(url, { method: 'POST' });
  if (unauthorized.status !== 401) throw new Error('Private endpoint authentication failed');
  const response = await fetch(url, { method: 'POST', headers: { Authorization: `Bearer ${process.env.APP_ACCESS_TOKEN}` } });
  const body = await response.json();
  if (!response.ok) throw new Error(`Gemini token mint failed (HTTP ${response.status})`);
  if (!body.value?.startsWith('auth_tokens/') || body.expires_at * 1000 <= Date.now()) throw new Error('Invalid or expired ephemeral token');
  console.log('PASS: private authentication, live Gemini ephemeral token mint, future expiry.');
  if (process.argv.includes('--session')) {
    // Node's WebSocket has no custom-header constructor; token appears only in this in-memory URL.
    const ws = new WebSocket(`wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContentConstrained?access_token=${encodeURIComponent(body.value)}`);
    await new Promise((resolve, reject) => {
      let setup = false;
      const timer = setTimeout(() => { ws.close(); reject(new Error('Gemini live session timed out')); }, 30_000);
      ws.onopen = () => ws.send(JSON.stringify({ setup: { model: body.model } }));
      ws.onmessage = async event => {
        try {
          const text = typeof event.data === 'string' ? event.data : await event.data.text();
          const message = JSON.parse(text);
          if (message.setupComplete) {
            setup = true;
            console.log('PASS: real Gemini Live session setup.');
            ws.send(JSON.stringify({ clientContent: { turns: [{ role: 'user', parts: [{ text: 'Spune doar: Bună ziua.' }] }], turnComplete: true } }));
          }
          if (message.serverContent?.modelTurn?.parts?.some(part => part.inlineData?.mimeType?.startsWith('audio/pcm'))) {
            clearTimeout(timer); ws.close(); console.log('PASS: real streamed PCM voice response (not retained).'); resolve();
          }
          if (message.error) { clearTimeout(timer); ws.close(); reject(new Error('Gemini returned a session error')); }
        } catch { clearTimeout(timer); ws.close(); reject(new Error('Invalid Gemini session response')); }
      };
      ws.onerror = () => { clearTimeout(timer); reject(new Error('Gemini WebSocket connection failed')); };
      ws.onclose = event => { clearTimeout(timer); reject(new Error(`Gemini closed connection (code ${event.code}, setup ${setup ? 'complete' : 'incomplete'})`)); };
    });
  }
} catch (error) { console.error(error.message); process.exitCode = 1; }
finally { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
