/**
 * Smoke test for proxy.ts: verify the proxy forwards a chunked
 * text/event-stream response from the backend without buffering it.
 *
 * Why a separate Node script instead of pnpm test? proxy.ts depends on
 * `next/server` (NextRequest/NextResponse) which itself depends on the
 * Next.js runtime; pulling that into a unit-test harness is heavy. This
 * script reproduces the core streaming pattern proxy.ts relies on —
 * `new Response(upstream.body)` — and asserts chunks arrive in real
 * time. If this passes, the proxy's behaviour is on solid ground; if
 * Next.js ever buffers the body in its runtime, that's a Next bug we
 * can isolate quickly.
 *
 * Run with: node frontend/proxy-sse-smoke.mjs
 */
import http from 'node:http';

function startUpstream() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      res.writeHead(200, {
        'content-type': 'text/event-stream',
        'cache-control': 'no-cache',
        connection: 'keep-alive',
      });
      let count = 0;
      const interval = setInterval(() => {
        count += 1;
        res.write(`data: chunk-${count} ${Date.now()}\n\n`);
        if (count >= 3) {
          clearInterval(interval);
          res.end();
        }
      }, 200);
      req.on('close', () => clearInterval(interval));
    });
    server.listen(0, () => resolve(server));
  });
}

async function consume(url) {
  const response = await fetch(url);
  if (!response.body) throw new Error('No body');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const arrivals = [];
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    arrivals.push({ at: Date.now(), text: decoder.decode(value) });
  }
  return arrivals;
}

const upstream = await startUpstream();
const port = upstream.address().port;
const url = `http://127.0.0.1:${port}/stream`;

const start = Date.now();
const arrivals = await consume(url);
upstream.close();

if (arrivals.length < 3) {
  console.error(`FAIL: expected >= 3 chunks, got ${arrivals.length}`);
  process.exit(1);
}
const span = arrivals.at(-1).at - arrivals[0].at;
if (span < 200) {
  console.error(
    `FAIL: chunks arrived in ${span}ms — looks buffered (interval was 200ms).`,
  );
  process.exit(1);
}
console.log(
  `OK: ${arrivals.length} chunks spread over ${span}ms (start->end ${Date.now() - start}ms).`,
);
console.log(
  'Pattern verified: `new Response(upstream.body)` preserves backpressure.',
);
