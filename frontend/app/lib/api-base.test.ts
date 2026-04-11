import test from 'node:test';
import assert from 'node:assert/strict';

import { resolveBrowserApiUrl, resolveServerApiUrl } from './api-base';

test('browser resolver falls back to the exposed host API port', () => {
  assert.equal(resolveBrowserApiUrl({} as NodeJS.ProcessEnv), 'http://localhost:18000');
});

test('server resolver falls back to the Docker service URL', () => {
  assert.equal(resolveServerApiUrl({} as NodeJS.ProcessEnv), 'http://api:8000');
});

test('server resolver prefers INTERNAL_API_URL when present', () => {
  assert.equal(
    resolveServerApiUrl({
      INTERNAL_API_URL: 'http://api:9000',
      NEXT_PUBLIC_API_URL: 'http://localhost:18000',
    } as NodeJS.ProcessEnv),
    'http://api:9000',
  );
});
