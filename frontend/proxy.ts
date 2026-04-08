import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

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

  const isLoginPage = req.nextUrl.pathname.startsWith('/login');

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
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:18000';
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

    const res = NextResponse.next();
    
    // Update cookies in the response (sent to client)
    res.cookies.set('motifold_token', newAccessToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: 60 * 60 * 24 * 7,
    });
    
    // Update cookies in the request (visible to Server Components)
    req.cookies.set('motifold_token', newAccessToken);
    
    if (data.refresh_token) {
      res.cookies.set('motifold_refresh_token', newRefreshToken, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        path: '/',
        maxAge: 60 * 60 * 24 * 30,
      });
      req.cookies.set('motifold_refresh_token', newRefreshToken);
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
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico, sitemap.xml, robots.txt (metadata files)
     */
    '/((?!api|_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)',
  ],
};