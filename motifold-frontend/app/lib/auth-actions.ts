"use server";

import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';

export async function setAuthCookies(accessToken: string, refreshToken?: string, username?: string) {
  const cookieStore = await cookies();
  
  cookieStore.set('motifold_token', accessToken, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    maxAge: 60 * 60 * 24 * 7, // 7 days
  });

  if (refreshToken) {
    cookieStore.set('motifold_refresh_token', refreshToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: 60 * 60 * 24 * 30, // 30 days
    });
  }

  if (username) {
    cookieStore.set('motifold_username', username, {
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: 60 * 60 * 24 * 30,
    });
  }
}

export async function clearAuthCookies() {
  const cookieStore = await cookies();
  cookieStore.delete('motifold_token');
  cookieStore.delete('motifold_refresh_token');
  cookieStore.delete('motifold_username');
  redirect('/login');
}
