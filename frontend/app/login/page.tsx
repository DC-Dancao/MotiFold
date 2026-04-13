"use client";

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Bot } from 'lucide-react';
import { setAuthCookies } from '../lib/auth-actions';
import { resolveBrowserApiUrl } from '../lib/api-base';

export default function LoginPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    const apiUrl = resolveBrowserApiUrl();

    try {
      if (!isLogin) {
        // Register flow
        const regRes = await fetch(`${apiUrl}/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password })
        });

        if (!regRes.ok) {
          const data = await regRes.json();
          throw new Error(data.detail || 'Registration failed');
        }
      }

      // Login flow (for both login and after successful register)
      const loginRes = await fetch(`${apiUrl}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username, password })
      });

      if (!loginRes.ok) {
        const data = await loginRes.json();
        throw new Error(data.detail || 'Login failed');
      }

      const data = await loginRes.json();

      localStorage.setItem('motifold_username', username);
      localStorage.removeItem('motifold_access_token');

      // Store in cookies for proxy/server-side access and backend auth
      await setAuthCookies(data.access_token, data.refresh_token, username);

      // Redirect to main app
      router.push('/');

    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError(String(err));
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8 relative">
      {/* Background Pattern */}
      <div
        className="absolute inset-0 z-0 opacity-[0.02] pointer-events-none"
        style={{ backgroundImage: 'radial-gradient(#000 1px, transparent 1px)', backgroundSize: '20px 20px' }}
      ></div>

      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        <div className="flex justify-center">
          <div className="w-16 h-16 rounded-2xl bg-indigo-600 text-white flex items-center justify-center font-bold text-3xl shadow-lg shadow-indigo-500/30">
            M
          </div>
        </div>
        <h2 className="mt-6 text-center text-3xl font-extrabold text-slate-900">
          {isLogin ? '登录 Motifold' : '注册 Motifold'}
        </h2>
        <p className="mt-2 text-center text-sm text-slate-600">
          {isLogin ? '没有账号？' : '已有账号？'}{' '}
          <button
            onClick={() => setIsLogin(!isLogin)}
            className="font-medium text-indigo-600 hover:text-indigo-500 transition-colors"
          >
            {isLogin ? '立即注册' : '返回登录'}
          </button>
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        <div className="bg-white py-8 px-4 shadow-xl shadow-slate-200/50 sm:rounded-2xl sm:px-10 border border-slate-100">
          <form className="space-y-6" onSubmit={handleSubmit}>
            {error && (
              <div className="bg-red-50 text-red-500 text-sm p-3 rounded-xl border border-red-100 flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-red-500"></div>
                {error}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-slate-700">用户名</label>
              <div className="mt-1">
                <input
                  type="text"
                  required
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  className="appearance-none block w-full px-3 py-2.5 border border-slate-300 rounded-xl shadow-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 sm:text-sm transition-all"
                  placeholder="输入用户名"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700">密码</label>
              <div className="mt-1">
                <input
                  type="password"
                  required
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="appearance-none block w-full px-3 py-2.5 border border-slate-300 rounded-xl shadow-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 sm:text-sm transition-all"
                  placeholder="输入密码"
                />
              </div>
            </div>

            <div>
              <button
                type="submit"
                disabled={isLoading || !username || !password}
                className="w-full flex justify-center py-2.5 px-4 border border-transparent rounded-xl shadow-md shadow-indigo-500/20 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {isLoading ? (
                  <span className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                    {isLogin ? '登录中...' : '注册中...'}
                  </span>
                ) : (
                  isLogin ? '登录' : '注册'
                )}
              </button>
            </div>
          </form>

          <div className="mt-6 flex items-center justify-center gap-2 text-xs text-slate-400">
            <Bot className="w-3.5 h-3.5" />
            Motifold AI 驱动的工作区
          </div>
        </div>
      </div>
    </div>
  );
}
