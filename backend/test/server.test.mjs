import test from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { createServer } from '../src/server.mjs';
import { sessionConfiguration } from '../src/session.mjs';
import { geminiTokenConfiguration } from '../src/gemini-session.mjs';

// Transport-contract fixtures only. These are not simulated conversational responses,
// and passing these tests is not evidence of live OpenAI authentication or audio.
const env = { OPENAI_API_KEY: 'unit-test-not-a-real-api-key', APP_ACCESS_TOKEN: 'unit-test-private-access-token-at-least-32-characters' };

test('Gemini works without OpenAI credentials, locks the Romanian setup, and redacts token metadata', async () => {
  const geminiEnv = { GEMINI_API_KEY: 'unit-test-google-key', APP_ACCESS_TOKEN: env.APP_ACCESS_TOKEN };
  let calls = 0;
  await withServer({ env: geminiEnv, fetchImpl: async (url, options) => {
    calls++;
    assert.equal(url, 'https://generativelanguage.googleapis.com/v1beta/auth_tokens');
    assert.equal(options.headers['x-goog-api-key'], geminiEnv.GEMINI_API_KEY);
    assert.equal(options.headers.Authorization, undefined);
    const config = JSON.parse(options.body);
    assert.equal(config.uses, 1); assert.equal(config.fieldMask, undefined);
    assert.equal(config.bidiGenerateContentSetup.model, 'models/gemini-3.8-live');
    assert.deepEqual(config.bidiGenerateContentSetup.generationConfig.responseModalities, ['AUDIO']);
    assert.match(config.bidiGenerateContentSetup.systemInstruction.parts[0].text, /Nu inventa/);
    assert.equal(config.bidiGenerateContentSetup.tools[0].functionDeclarations[0].name, 'request_camera_image');
    assert.ok(Date.parse(config.newSessionExpireTime) > Date.now());
    assert.equal(Date.parse(config.expireTime) - Date.parse(config.newSessionExpireTime), 9 * 60_000);
    return Response.json({ name: 'auth_tokens/unit-test-only', ignored: 'private metadata' });
  } }, async base => {
    const url = `${base}/gemini/client-secret`;
    assert.equal((await fetch(url, { method: 'POST' })).status, 401);
    const headers = { Authorization: `Bearer ${env.APP_ACCESS_TOKEN}` };
    assert.equal((await fetch(url, { method: 'POST', headers: { ...headers, Origin: 'https://example.org' } })).status, 403);
    assert.equal((await fetch(url, { method: 'POST', headers, body: '{}' })).status, 400);
    const result = await fetch(url, { method: 'POST', headers });
    assert.equal(result.status, 200); assert.equal(result.headers.get('cache-control'), 'no-store');
    assert.deepEqual(Object.keys(await result.json()).sort(), ['expires_at', 'model', 'value']);
    assert.equal(calls, 1);
    assert.equal((await post(base)).status, 503);
  });
});

test('Gemini rejects unexpected upstream credential formats and separates main and app credentials', async () => {
  for (const [access, upstream, expected] of [
    [env.APP_ACCESS_TOKEN, { name: 'not-a-token' }, 502],
    ['same-credential-longer-than-32-characters', {}, 503]
  ]) {
    await withServer({ env: { GEMINI_API_KEY: 'same-credential-longer-than-32-characters', APP_ACCESS_TOKEN: access },
      fetchImpl: async () => Response.json(upstream) }, async base => {
      const response = await fetch(`${base}/gemini/client-secret`, { method: 'POST', headers: { Authorization: `Bearer ${access}` } });
      assert.equal(response.status, expected);
      assert.doesNotMatch(await response.text(), /same-credential|not-a-token/);
    });
  }
  assert.equal(geminiTokenConfiguration('gemini-test', 0).bidiGenerateContentSetup.model, 'models/gemini-test');
});
async function withServer(options, run) {
  const server = createServer(options); server.listen(0, '127.0.0.1'); await once(server, 'listening');
  try { await run(`http://127.0.0.1:${server.address().port}`); }
  finally { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
}
const post = (base, headers = {}, body) => fetch(`${base}/realtime/client-secret`, {
  method: 'POST', headers: { Authorization: `Bearer ${env.APP_ACCESS_TOKEN}`, ...headers }, body
});
test('GA session uses Romanian audio, explicit image tool, and one-minute client secret', () => {
  const value = sessionConfiguration();
  assert.equal(value.session.type, 'realtime'); assert.equal(value.session.model, 'gpt-realtime-2.1');
  assert.equal(value.expires_after.seconds, 60); assert.deepEqual(value.session.output_modalities, ['audio']);
  assert.match(value.session.instructions, /română/); assert.match(value.session.instructions, /Nu inventa/);
  assert.equal(value.session.tools[0].name, 'request_camera_image');
  assert.equal(value.session.audio.input.turn_detection.interrupt_response, true);
});
test('starts without secrets, health is factual, minting fails closed', async () => {
  await withServer({ env: {}, fetchImpl: () => assert.fail('must not call upstream') }, async base => {
    assert.deepEqual(await (await fetch(`${base}/health`)).json(), { status: 'ok', configured: false });
    assert.equal((await post(base)).status, 503);
  });
});
test('rejects unauthorized clients, browser origins, body overrides and wrong routes before upstream', async () => {
  await withServer({ env, fetchImpl: () => assert.fail('must not call upstream') }, async base => {
    assert.equal((await post(base, { Authorization: 'Bearer wrong' })).status, 401);
    assert.equal((await post(base, { Origin: 'https://untrusted.example' })).status, 403);
    assert.equal((await post(base, {}, '{"session":{"instructions":"override"}}')).status, 400);
    assert.equal((await fetch(`${base}/realtime/client-secret`)).status, 404);
  });
});
test('mints only GA ephemeral secret, returns minimum fields and no-cache headers', async () => {
  let calls = 0;
  await withServer({ env, fetchImpl: async (url, options) => {
    calls++;
    assert.equal(url, 'https://api.openai.com/v1/realtime/client_secrets');
    assert.equal(options.headers.Authorization, `Bearer ${env.OPENAI_API_KEY}`);
    assert.equal(options.headers['OpenAI-Beta'], undefined);
    assert.match(options.headers['OpenAI-Safety-Identifier'], /^[0-9a-f]{64}$/);
    assert.equal(JSON.parse(options.body).session.model, 'gpt-realtime-2.1');
    return Response.json({ value: 'ek_unit_test_only', expires_at: Math.floor(Date.now() / 1000) + 60, session: { irrelevant: true } });
  } }, async base => {
    const response = await post(base);
    assert.equal(response.status, 200); assert.equal(response.headers.get('cache-control'), 'no-store');
    const value = await response.json(); assert.deepEqual(Object.keys(value).sort(), ['expires_at', 'value']);
    assert.equal(value.value, 'ek_unit_test_only'); assert.equal(calls, 1);
  });
});
test('rejects expired/invalid credentials and redacts upstream failures', async () => {
  for (const response of [Response.json({ value: 'not-ephemeral', expires_at: 0 }),
    Response.json({ private_error: 'never expose this' }, { status: 401 })]) {
    await withServer({ env, fetchImpl: async () => response }, async base => {
      const result = await post(base); assert.equal(result.status, 502);
      const body = await result.text(); assert.doesNotMatch(body, /never expose|unit-test-not/);
    });
  }
});
test('rate-limits authenticated mint attempts before issuing more secrets', async () => {
  let calls = 0;
  await withServer({ env, fetchImpl: async () => { calls++; return Response.json({}, { status: 503 }); } }, async base => {
    for (let i = 0; i < 6; i++) assert.equal((await post(base)).status, 502);
    assert.equal((await post(base)).status, 429); assert.equal(calls, 6);
  });
});
test('distinguishes exhausted quota from transient rate limits without returning upstream data', async () => {
  for (const [code, expected] of [['insufficient_quota', 'upstream_quota_exceeded'],
    ['credit_balance_exhausted', 'upstream_quota_exceeded'], ['rate_limit_exceeded', 'upstream_rate_limited']]) {
    await withServer({ env, fetchImpl: async () => Response.json({ error: { code, message: 'sensitive upstream details' } }, { status: 429 }) }, async base => {
      const response = await post(base);
      assert.equal(response.status, 429);
      assert.deepEqual(await response.json(), { error: expected });
    });
  }
});
