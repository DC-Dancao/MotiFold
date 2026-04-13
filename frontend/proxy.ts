import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

import { resolveServerApiUrl, shouldUseSecureCookies } from './app/lib/api-base';

function isTokenExpired(token: string) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const exp = payload.exp * 1000;
    return Date.now() >= exp - 5000; // 5 seconds buffer
  } catch (e) {
    return true;
  }
}

export async function proxy(req: NextRequest) {
  const token = req.cookies.get('motifold_token')?.value;
  const refreshToken = req.cookies.get('motifold_refresh_token')?.value;
  const currentOrgId = req.cookies.get('motifold_current_org_id')?.value;

  const pathname = req.nextUrl.pathname;

  const API_PATHS = [
    '/api',
    '/auth',
    '/chats',
    '/workspaces',
    '/matrix',
    '/blackboard',
    '/research',
    '/memory',
    '/notifications',
  ];
  const FRONTEND_PAGE_PATHS = new Set([
    '/matrix',
    '/blackboard',
    '/research',
    '/memory',
  ]);
  const isFrontendPageRequest = req.method === 'GET' && FRONTEND_PAGE_PATHS.has(pathname);
  const shouldProxy = !isFrontendPageRequest && API_PATHS.some(prefix => pathname === prefix || pathname.startsWith(`${prefix}/`));

  if (shouldProxy) {
    const apiUrl = resolveServerApiUrl();

    const headers = new Headers();
    req.headers.forEach((value, key) => {
      if (key.toLowerCase() !== 'host' && key.toLowerCase() !== 'content-length') {
        headers.set(key, value);
      }
    });

    if (currentOrgId && !pathname.startsWith('/auth/')) {
      headers.set('X-Org-ID', currentOrgId);
    }

    const cookieHeader: string[] = [];
    if (token) cookieHeader.push(`motifold_token=${token}`);
    if (refreshToken) cookieHeader.push(`motifold_refresh_token=${refreshToken}`);
    if (cookieHeader.length > 0) {
      headers.set('cookie', cookieHeader.join('; '));
    }

    const needsTrailingSlash = (
      pathname === '/api/orgs' ||
      pathname === '/workspaces' ||
      pathname === '/chats' ||
      pathname === '/blackboard' ||
      pathname === '/research'
    );
    const backendPath = needsTrailingSlash ? `${pathname}/` : pathname;
    const backendUrl = `${apiUrl}${backendPath}${req.nextUrl.search}`;

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

      if ([301, 302, 307, 308].includes(response.status)) {
        const location = response.headers.get('location');
        console.warn('Backend redirect detected', {
          pathname,
          backendUrl,
          status: response.status,
          location,
        });

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

  const isLoginPage = pathname.startsWith('/login');

  if (isLoginPage) {
    // If user is already logged in, redirect to home
    if (token && !isTokenExpired(token)) {
      return NextResponse.redirect(new URL('/', req.url));
    }
    return NextResponse.next();
  }

  // Protected routes
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

  // Need to refresh
  const apiUrl = resolveServerApiUrl();
  try {
    const refreshRes = await fetch(`${apiUrl}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken })
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
    console.error('Middleware refresh failed:', error);
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