import http from 'node:http';
import { timingSafeEqual, createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { sessionConfiguration } from './session.mjs';
import { geminiTokenConfiguration } from './gemini-session.mjs';

export function createServer({ env = process.env, fetchImpl = fetch, now = Date.now } = {}) {
  const key = env.OPENAI_API_KEY?.trim();
  const geminiKey = env.GEMINI_API_KEY?.trim();
  const access = env.APP_ACCESS_TOKEN?.trim();
  const accessReady = Boolean(access && access.length >= 32 && access !== key && access !== geminiKey);
  const ready = Boolean(key && accessReady);
  const geminiReady = Boolean(geminiKey && accessReady);
  let starts = [], inFlight = 0;
  const controllers = new Set();
  const reply = (res, status, data) => {
    res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff' });
    res.end(JSON.stringify(data));
  };
  const server = http.createServer(async (req, res) => {
    if (req.method === 'GET' && req.url === '/health') return reply(res, 200, { status: 'ok', configured: ready || geminiReady });
    const gemini = req.url === '/gemini/client-secret';
    if (req.method !== 'POST' || (!gemini && req.url !== '/realtime/client-secret')) return reply(res, 404, { error: 'not_found' });
    // Native clients have no Origin. Never expose this private prototype endpoint to websites.
    if (req.headers.origin) return reply(res, 403, { error: 'origin_not_allowed' });
    if (!(gemini ? geminiReady : ready)) return reply(res, 503, { error: 'backend_not_configured' });
    const provided = Buffer.from(req.headers.authorization ?? '');
    const expected = Buffer.from(`Bearer ${access}`);
    if (provided.length !== expected.length || !timingSafeEqual(provided, expected)) return reply(res, 401, { error: 'unauthorized' });
    // The client cannot select prompts/models or relay arbitrary upstream requests.
    if (req.headers['transfer-encoding'] || Number(req.headers['content-length'] ?? 0) !== 0) {
      req.resume(); return reply(res, 400, { error: 'body_not_allowed' });
    }
    starts = starts.filter(time => now() - time < 60_000);
    if (starts.length >= 6 || inFlight >= 2) return reply(res, 429, { error: 'rate_limited' });
    starts.push(now()); inFlight++;
    const controller = new AbortController(); controllers.add(controller);
    const timeout = setTimeout(() => controller.abort(), 15_000);
    const disconnect = () => { if (!res.writableEnded) controller.abort(); };
    res.once('close', disconnect);
    try {
      const geminiConfig = geminiTokenConfiguration(env.GEMINI_LIVE_MODEL || 'gemini-3.8-live', now());
      const upstream = await fetchImpl(gemini ? 'https://generativelanguage.googleapis.com/v1beta/auth_tokens' : 'https://api.openai.com/v1/realtime/client_secrets', {
        method: 'POST', signal: controller.signal,
        headers: gemini ? { 'x-goog-api-key': geminiKey, 'Content-Type': 'application/json' } : { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json',
          'OpenAI-Safety-Identifier': createHash('sha256').update(access).digest('hex') },
        body: JSON.stringify(gemini ? geminiConfig : sessionConfiguration(env.OPENAI_REALTIME_MODEL || 'gpt-realtime-2.1'))
      });
      if (!upstream.ok) {
        // Do not log upstream payloads, tokens, user audio, SDP or credentials.
        let quota = false;
        if (upstream.status === 429) {
          const failure = await upstream.json().catch(() => ({}));
          quota = failure.error?.type === 'insufficient_quota' ||
            ['insufficient_quota', 'credit_balance_exhausted', 'organization_spend_limit_exceeded',
              'project_spend_limit_exceeded', 'organization_usage_limit_exceeded'].includes(failure.error?.code);
        } else await upstream.body?.cancel();
        return reply(res, upstream.status === 429 ? 429 : 502, {
          error: quota ? 'upstream_quota_exceeded' : upstream.status === 429 ? 'upstream_rate_limited' : 'upstream_unavailable'
        });
      }
      const data = await upstream.json();
      if (gemini) {
        if (typeof data.name !== 'string' || !data.name.startsWith('auth_tokens/') || data.name.length > 8192) {
          return reply(res, 502, { error: 'invalid_upstream_response' });
        }
        if (!res.destroyed) reply(res, 200, { value: data.name,
          expires_at: Date.parse(geminiConfig.newSessionExpireTime) / 1000,
          model: geminiConfig.bidiGenerateContentSetup.model });
        return;
      }
      if (typeof data.value !== 'string' || !data.value.startsWith('ek_') || !Number.isFinite(data.expires_at) || data.expires_at * 1000 <= now()) {
        return reply(res, 502, { error: 'invalid_upstream_response' });
      }
      if (!res.destroyed) reply(res, 200, { value: data.value, expires_at: data.expires_at });
    } catch {
      if (!res.destroyed) reply(res, 502, { error: 'upstream_unavailable' });
    } finally {
      clearTimeout(timeout); res.off('close', disconnect); controllers.delete(controller); inFlight--;
    }
  });
  server.headersTimeout = 10_000; server.requestTimeout = 20_000; server.maxHeadersCount = 30;
  server.on('close', () => controllers.forEach(controller => controller.abort()));
  return server;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const server = createServer();
  const host = process.env.HOST || '127.0.0.1';
  const port = Number(process.env.PORT || 8787);
  server.listen(port, host, () => console.log(`VisionAssist backend listening on ${host}:${port}`));
  for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.close());
}
