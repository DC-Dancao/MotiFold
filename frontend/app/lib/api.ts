export { getApiUrl } from './api-base';
import { getApiUrl } from './api-base';

let refreshPromise: Promise<boolean> | null = null;

export type SSECallback = (data: Record<string, unknown>, raw: string) => void;
export type SSEErrorCallback = (error: Error) => void;

export interface SSECancelFn {
  cancel: () => void;
  onerror?: SSEErrorCallback;
}

export function streamSSE(
  url: string,
  callbacks: {
    onMessage: SSECallback;
    onDone?: () => void;
    onError?: SSEErrorCallback;
  }
): SSECancelFn {
  let cancelled = false;
  const controller = new AbortController();

  (async () => {
    try {
      const response = await fetch(url, {
        credentials: 'include',
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        callbacks.onError?.(new Error(`SSE connection failed: ${response.status}`));
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (!cancelled) {
        const { done, value } = await reader.read();
        if (done) {
          callbacks.onDone?.();
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';

        for (const event of events) {
          const dataLine = event
            .split('\n')
            .find(line => line.startsWith('data:'));

          if (!dataLine) continue;

          try {
            const raw = dataLine.slice(5).trim();
            const parsed = JSON.parse(raw);
            callbacks.onMessage(parsed, raw);
          } catch {
            callbacks.onMessage({ raw: dataLine.slice(5).trim() }, dataLine.slice(5).trim());
          }
        }
      }
    } catch (err) {
      if (!cancelled) {
        callbacks.onError?.(err instanceof Error ? err : new Error(String(err)));
      }
    }
  })();

  return {
    cancel: () => {
      cancelled = true;
      controller.abort();
    },
    onerror: callbacks.onError,
  };
}

const redirectToLogin = () => {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('motifold_access_token');
    if (window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
  }
};

const refreshAuth = async (): Promise<boolean> => {
  if (!refreshPromise) {
    const apiUrl = getApiUrl();
    refreshPromise = fetch(`${apiUrl}/auth/refresh`, {
      method: 'POST',
      credentials: 'include'
    })
      .then((res) => {
        if (!res.ok) {
          console.warn('Refresh auth failed with status:', res.status);
          return false;
        }
        return true;
      })
      .catch((err) => {
        console.error('Refresh auth request error:', err);
        return false;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
};

const isRefreshRequest = (url: string) => {
  if (url.includes('/auth/refresh')) {
    return true;
  }

  try {
    const base = typeof window !== 'undefined' ? window.location.origin : getApiUrl();
    return new URL(url, base).pathname === '/auth/refresh';
  } catch {
    return false;
  }
};

export const fetchWithAuth = async (url: string, options: RequestInit = {}) => {
  const currentOrgId = typeof window !== 'undefined'
    ? localStorage.getItem('motifold_current_org_id')
    : null;

  const accessToken = typeof window !== 'undefined'
    ? localStorage.getItem('motifold_access_token')
    : null;

  const headers = new Headers(options.headers);

  if (currentOrgId && !url.includes('/auth/')) {
    headers.set('X-Org-ID', currentOrgId);
  }

  // Add Authorization header for endpoints that require Bearer token (not cookie fallback)
  if (accessToken && !url.includes('/auth/refresh')) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }

  const finalOptions: RequestInit = {
    ...options,
    credentials: 'include',
    headers,
  };

  const response = await fetch(url, finalOptions);

  if (response.status !== 401 || isRefreshRequest(url)) {
    return response;
  }

  const refreshed = await refreshAuth();
  if (!refreshed) {
    redirectToLogin();
    return response;
  }

  const retryResponse = await fetch(url, finalOptions);
  if (retryResponse.status === 401) {
    redirectToLogin();
  }

  return retryResponse;
};
