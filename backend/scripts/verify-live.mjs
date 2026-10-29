import { once } from 'node:events';
import assert from 'node:assert/strict';
import { createServer } from '../src/server.mjs';

// This performs a real paid-account API operation when explicitly invoked.
// It never prints the main key, access token, ephemeral secret or full API response.
if (!process.env.OPENAI_API_KEY || !process.env.APP_ACCESS_TOKEN) {
  console.error('Live verification requires backend credentials. No API call was made.');
  process.exitCode = 2;
} else {
  const server = createServer(); server.listen(0, '127.0.0.1'); await once(server, 'listening');
  try {
    const base = `http://127.0.0.1:${server.address().port}`;
    const denied = await fetch(`${base}/realtime/client-secret`, { method: 'POST' });
    assert.equal(denied.status, 401);
    const response = await fetch(`${base}/realtime/client-secret`, {
      method: 'POST', headers: { Authorization: `Bearer ${process.env.APP_ACCESS_TOKEN}` }
    });
    if (response.status !== 200) throw new Error(`Backend live check returned HTTP ${response.status}`);
    const value = await response.json();
    assert.ok(value.value.startsWith('ek_')); assert.ok(value.expires_at * 1000 > Date.now());
    console.log('PASS: unauthorized access rejected; real GA client secret created with future expiry.');
    console.log('WebRTC media/session initialization still requires the Android client.');
  } catch (error) {
    console.error(error.message.startsWith('Backend live check') ? error.message : 'Live verification failed.');
    process.exitCode = 1;
  } finally { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
}
