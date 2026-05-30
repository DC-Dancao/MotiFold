import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

import { resolveServerApiUrl, shouldUseSecureCookies } from './app/lib/api-base';

function isTokenExpired(token: string) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const exp = payload.exp * 1000;
    return Date.now() >= exp - 1000; // 1 second buffer for clock skew
  } catch {
    return true;
  }
}

// Request headers that are forwarded to the backend. We use a closed
// allowlist (rather than denylist) so that hop-by-hop headers, framing
// headers, and arbitrary client-supplied headers cannot be smuggled
// through. When adding a feature that depends on a header not listed
// here, add it explicitly. Common candidates:
//   - 'accept-encoding'                if the backend handles compression
//   - 'if-none-match' / 'if-modified-since'  if the backend issues ETags
//   - 'range'                          if any endpoint serves byte ranges
//   - 'x-forwarded-for' / 'x-forwarded-proto' if the backend logs client IP
//   - 'traceparent' / 'tracestate'     if distributed tracing is added
const FORWARD_REQUEST_HEADERS = new Set([
  'accept',
  'accept-language',
  'authorization',
  'content-type',
  'idempotency-key',
  'user-agent',
  'x-requested-with',
]);

export async function proxy(req: NextRequest) {
  const token = req.cookies.get('motifold_token')?.value;
  const refreshToken = req.cookies.get('motifold_refresh_token')?.value;
  const currentOrgId = req.cookies.get('motifold_current_org_id')?.value;

  const pathname = req.nextUrl.pathname;
  const isApiRequest = pathname.startsWith('/api/');

  if (isApiRequest) {
    return forwardToBackend(req, pathname, token, refreshToken, currentOrgId);
  }

  return enforceAuth(req, pathname, token, refreshToken);
}

async function forwardToBackend(
  req: NextRequest,
  pathname: string,
  token: string | undefined,
  refreshToken: string | undefined,
  currentOrgId: string | undefined,
) {
  const apiUrl = resolveServerApiUrl();

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (FORWARD_REQUEST_HEADERS.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });

  // Tenant header: the X-Org-ID cookie is the canonical source. Skip for
  // /api/auth/* (login/refresh/register predate any selected tenant).
  if (currentOrgId && !pathname.startsWith('/api/auth/')) {
    headers.set('X-Org-ID', currentOrgId);
  }

  const cookieHeader: string[] = [];
  if (token) cookieHeader.push(`motifold_token=${token}`);
  if (refreshToken) cookieHeader.push(`motifold_refresh_token=${refreshToken}`);
  if (cookieHeader.length > 0) {
    headers.set('cookie', cookieHeader.join('; '));
  }

  const backendUrl = `${apiUrl}${pathname}${req.nextUrl.search}`;

  try {
    const body = req.method === 'GET' || req.method === 'HEAD'
      ? undefined
      : await req.text();

    const response = await fetch(backendUrl, {
      method: req.method,
      headers,
      body,
      redirect: 'manual',
    });

    const responseHeaders = new Headers(response.headers);

    // Defense-in-depth: if the backend ever issues a redirect, rewrite the
    // Location header so the browser stays inside this origin rather than
    // following directly to the internal backend URL.
    if ([301, 302, 307, 308].includes(response.status)) {
      const location = response.headers.get('location');
      if (location) {
        const redirectedUrl = new URL(location, backendUrl);
        const backendOrigin = new URL(apiUrl).origin;
        if (redirectedUrl.origin === backendOrigin) {
          responseHeaders.set('location', `${req.nextUrl.origin}${redirectedUrl.pathname}${redirectedUrl.search}`);
        }
      }
    }
    responseHeaders.delete('content-encoding');
    responseHeaders.delete('content-length');
    responseHeaders.delete('transfer-encoding');

    return new NextResponse(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    console.error('API proxy failed:', error);
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 502 });
  }
}

async function enforceAuth(
  req: NextRequest,
  pathname: string,
  token: string | undefined,
  refreshToken: string | undefined,
) {
  const isLoginPage = pathname.startsWith('/login');

  if (isLoginPage) {
    // Already-authenticated users skip the login screen and go straight to
    // the chat workspace (avoids the "/" → "/chat" hop).
    if (token && !isTokenExpired(token)) {
      return NextResponse.redirect(new URL('/chat', req.url));
    }
    return NextResponse.next();
  }

  // Protected page navigations need at least one token to proceed.
  if (!token && !refreshToken) {
    return NextResponse.redirect(new URL('/login', req.url));
  }

  const accessExpired = !token || isTokenExpired(token);

  if (!accessExpired) {
    return NextResponse.next();
  }

  if (!refreshToken) {
    return NextResponse.redirect(new URL('/login', req.url));
  }

  // Access token has expired but we still have a refresh token — try to
  // mint a new one server-side so the upcoming SSR/Server-Component fetches
  // see a valid session cookie. Client-side `fetchWithAuth` runs the same
  // dance for browser-initiated requests.
  const apiUrl = resolveServerApiUrl();
  try {
    const refreshRes = await fetch(`${apiUrl}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!refreshRes.ok) {
      const res = NextResponse.redirect(new URL('/login', req.url));
      res.cookies.delete('motifold_token');
      res.cookies.delete('motifold_refresh_token');
      return res;
    }

    const data = await refreshRes.json();
    const newAccessToken = data.access_token;
    const newRefreshToken = data.refresh_token || refreshToken;
    const secure = shouldUseSecureCookies(req.nextUrl.origin);

    const res = NextResponse.next();

    res.cookies.set('motifold_token', newAccessToken, {
      httpOnly: true,
      secure,
      sameSite: 'lax',
      path: '/',
      maxAge: 60 * 60 * 24 * 7,
    });

    if (data.refresh_token) {
      res.cookies.set('motifold_refresh_token', newRefreshToken, {
        httpOnly: true,
        secure,
        sameSite: 'lax',
        path: '/',
        maxAge: 60 * 60 * 24 * 30,
      });
    }

    return res;
  } catch (error) {
    console.error('Proxy refresh failed:', error);
    const res = NextResponse.redirect(new URL('/login', req.url));
    res.cookies.delete('motifold_token');
    res.cookies.delete('motifold_refresh_token');
    return res;
  }
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico, sitemap.xml, robots.txt (metadata files)
     */
    '/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)',
  ],
};