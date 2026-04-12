"use client";

import React, { useState, useEffect } from 'react';
import { Brain, Search, Loader2, FileText, X, ChevronDown, ChevronUp } from 'lucide-react';
import { fetchWithAuth, getApiUrl } from '../../app/lib/api';

interface MemoryStats {
  total: number;
  by_type: Record<string, number>;
}

interface MemoryRecentItem {
  id: string;
  content: string;
  memory_type: string;
  created_at: string;
  mentioned_at: string | null;
}

interface RecallResult {
  id: string;
  content: string;
  memory_type: string;
  similarity: number;
}

const MEMORY_TYPE_COLORS: Record<string, string> = {
  fact: 'bg-blue-100 text-blue-700',
  preference: 'bg-green-100 text-green-700',
  conclusion: 'bg-purple-100 text-purple-700',
  context: 'bg-amber-100 text-amber-700',
};

export default function MemoryArea() {
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [recentMemories, setRecentMemories] = useState<MemoryRecentItem[]>([]);
  const [hitRate, setHitRate] = useState<number>(0);
  const [isLoading, setIsLoading] = useState(true);

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<RecallResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  // Entity lookup state
  const [entityName, setEntityName] = useState('');
  const [entityResults, setEntityResults] = useState<RecallResult[]>([]);
  const [isEntitySearching, setIsEntitySearching] = useState(false);

  // Collapsible sections
  const [isRecentOpen, setIsRecentOpen] = useState(true);

  // Error state
  const [error, setError] = useState<string | null>(null);

  // Workspace ID from localStorage
  const workspaceIdFromStorage = typeof window !== 'undefined'
    ? parseInt(localStorage.getItem('motifold_active_workspace_id') || '0', 10)
    : 0;
  const workspaceId = isNaN(workspaceIdFromStorage) ? 0 : workspaceIdFromStorage;

  useEffect(() => {
    loadData();
  }, [workspaceId]);

  const loadData = async () => {
    if (!workspaceId) return;

    setIsLoading(true);
    setError(null);
    try {
      const apiUrl = getApiUrl();

      // Load stats and recent in parallel
      const [statsRes, recentRes, hitRateRes] = await Promise.all([
        fetchWithAuth(`${apiUrl}/memory/${workspaceId}/stats`),
        fetchWithAuth(`${apiUrl}/memory/${workspaceId}/recent?limit=20`),
        fetchWithAuth(`${apiUrl}/memory/${workspaceId}/hit-rate`),
      ]);

      if (!statsRes.ok || !recentRes.ok || !hitRateRes.ok) {
        setError('Failed to load memory data. Please try again.');
        return;
      }

      setStats(await statsRes.json());
      const recentData = await recentRes.json();
      setRecentMemories(recentData.memories || []);
      const hitRateData = await hitRateRes.json();
      setHitRate(hitRateData.hit_rate || 0);
    } catch (err) {
      console.error('Failed to load memory data:', err);
      setError('Failed to load memory data. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim() || !workspaceId) return;

    setIsSearching(true);
    try {
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(
        `${apiUrl}/memory/${workspaceId}/recall?query=${encodeURIComponent(searchQuery)}&use_multi_strategy=true&limit=10`,
        { method: 'POST' }
      );

      if (res.ok) {
        const data = await res.json();
        setSearchResults(data.results || []);
      }
    } catch (error) {
      console.error('Failed to search memories:', error);
    } finally {
      setIsSearching(false);
    }
  };

  const handleEntitySearch = async () => {
    if (!entityName.trim() || !workspaceId) return;

    setIsEntitySearching(true);
    try {
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(
        `${apiUrl}/memory/${workspaceId}/entities/${encodeURIComponent(entityName)}?limit=20`
      );

      if (res.ok) {
        const data = await res.json();
        setEntityResults(data.memories || []);
      }
    } catch (error) {
      console.error('Failed to search entity:', error);
    } finally {
      setIsEntitySearching(false);
    }
  };

  if (isLoading) {
    return (
      <main className="flex-1 flex flex-col bg-white min-w-0 relative">
        <div className="absolute inset-0 z-0 opacity-[0.02] pointer-events-none"
          style={{ backgroundImage: 'radial-gradient(#000 1px, transparent 1px)', backgroundSize: '20px 20px' }}
        />
        <div className="relative z-10 flex-1 flex items-center justify-center">
          <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="flex-1 flex flex-col bg-white min-w-0 relative">
        <div className="absolute inset-0 z-0 opacity-[0.02] pointer-events-none"
          style={{ backgroundImage: 'radial-gradient(#000 1px, transparent 1px)', backgroundSize: '20px 20px' }}
        />
        <div className="relative z-10 flex-1 flex items-center justify-center">
          <div className="text-center">
            <p className="text-red-600 mb-4">{error}</p>
            <button
              onClick={() => { setError(null); loadData(); }}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700"
            >
              重试
            </button>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="flex-1 flex flex-col bg-white min-w-0 relative">
      {/* Background Pattern */}
      <div
        className="absolute inset-0 z-0 opacity-[0.02] pointer-events-none"
        style={{ backgroundImage: 'radial-gradient(#000 1px, transparent 1px)', backgroundSize: '20px 20px' }}
      />

      <div className="relative z-10 flex-1 flex flex-col h-full overflow-y-auto">
        {/* Header */}
        <div className="h-16 border-b border-slate-100 flex items-center px-6 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center">
              <Brain className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-slate-800">记忆</h3>
              <p className="text-xs text-slate-400">Memory · 工作区记忆存储</p>
            </div>
          </div>
        </div>

        <div className="flex-1 p-6 space-y-6 max-w-4xl mx-auto w-full">
          {/* Stats Overview */}
          <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-5">
            <h4 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
              <Brain className="w-4 h-4 text-indigo-500" />
              记忆统计
            </h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-slate-50 rounded-xl p-4 text-center">
                <div className="text-2xl font-bold text-slate-800">{stats?.total || 0}</div>
                <div className="text-xs text-slate-500 mt-1">总记忆数</div>
              </div>
              <div className="bg-green-50 rounded-xl p-4 text-center">
                <div className="text-2xl font-bold text-green-700">{stats?.by_type?.preference || 0}</div>
                <div className="text-xs text-green-600 mt-1">偏好</div>
              </div>
              <div className="bg-blue-50 rounded-xl p-4 text-center">
                <div className="text-2xl font-bold text-blue-700">{stats?.by_type?.fact || 0}</div>
                <div className="text-xs text-blue-600 mt-1">事实</div>
              </div>
              <div className="bg-purple-50 rounded-xl p-4 text-center">
                <div className="text-2xl font-bold text-purple-700">{(hitRate * 100).toFixed(0)}%</div>
                <div className="text-xs text-purple-600 mt-1">命中率</div>
              </div>
            </div>

            {/* Additional type breakdown */}
            <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-slate-100">
              {stats?.by_type && Object.entries(stats.by_type).map(([type, count]) => (
                <span
                  key={type}
                  className={`px-3 py-1 rounded-full text-xs font-medium ${MEMORY_TYPE_COLORS[type] || 'bg-slate-100 text-slate-700'}`}
                >
                  {type}: {count}
                </span>
              ))}
            </div>
          </div>

          {/* Search Section */}
          <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-5">
            <h4 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
              <Search className="w-4 h-4 text-indigo-500" />
              搜索记忆
            </h4>
            <div className="flex gap-2">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="输入关键词搜索记忆..."
                className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 text-sm"
              />
              <button
                onClick={handleSearch}
                disabled={!searchQuery.trim() || isSearching}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isSearching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                搜索
              </button>
            </div>

            {/* Search Results */}
            {searchResults.length > 0 && (
              <div className="mt-4 space-y-2">
                <div className="text-xs text-slate-500 mb-2">找到 {searchResults.length} 条相关记忆</div>
                {searchResults.map((result) => (
                  <div key={result.id} className="border border-slate-100 rounded-xl p-4 bg-slate-50">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${MEMORY_TYPE_COLORS[result.memory_type] || 'bg-slate-100 text-slate-700'}`}>
                        {result.memory_type}
                      </span>
                      <span className="text-xs text-slate-400">{(result.similarity * 100).toFixed(0)}% 相似</span>
                    </div>
                    <p className="text-sm text-slate-700">{result.content}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Entity Lookup Section */}
          <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-5">
            <h4 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
              <FileText className="w-4 h-4 text-indigo-500" />
              实体查找
            </h4>
            <div className="flex gap-2">
              <input
                type="text"
                value={entityName}
                onChange={(e) => setEntityName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleEntitySearch()}
                placeholder="输入实体名称查找相关记忆..."
                className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 text-sm"
              />
              <button
                onClick={handleEntitySearch}
                disabled={!entityName.trim() || isEntitySearching}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isEntitySearching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                查找
              </button>
            </div>

            {/* Entity Results */}
            {entityResults.length > 0 && (
              <div className="mt-4 space-y-2">
                <div className="text-xs text-slate-500 mb-2">找到 {entityResults.length} 条包含该实体的记忆</div>
                {entityResults.map((result) => (
                  <div key={result.id} className="border border-slate-100 rounded-xl p-4 bg-slate-50">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${MEMORY_TYPE_COLORS[result.memory_type] || 'bg-slate-100 text-slate-700'}`}>
                        {result.memory_type}
                      </span>
                    </div>
                    <p className="text-sm text-slate-700">{result.content}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Recent Memories Section */}
          <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
            <button
              onClick={() => setIsRecentOpen(!isRecentOpen)}
              className="w-full px-5 py-4 flex items-center justify-between bg-slate-50 hover:bg-slate-100 transition-colors"
            >
              <h4 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                <FileText className="w-4 h-4 text-indigo-500" />
                最近记忆 ({recentMemories.length})
              </h4>
              {isRecentOpen ? (
                <ChevronUp className="w-4 h-4 text-slate-400" />
              ) : (
                <ChevronDown className="w-4 h-4 text-slate-400" />
              )}
            </button>

            {isRecentOpen && (
              <div className="p-4 space-y-2 max-h-[400px] overflow-y-auto">
                {recentMemories.length === 0 ? (
                  <div className="text-center text-sm text-slate-400 py-8">
                    暂无记忆记录
                  </div>
                ) : (
                  recentMemories.map((memory) => (
                    <div key={memory.id} className="border border-slate-100 rounded-xl p-4 hover:bg-slate-50 transition-colors">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${MEMORY_TYPE_COLORS[memory.memory_type] || 'bg-slate-100 text-slate-700'}`}>
                          {memory.memory_type}
                        </span>
                        <span className="text-xs text-slate-400">
                          {new Date(memory.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      <p className="text-sm text-slate-700 line-clamp-3">{memory.content}</p>
                      {memory.mentioned_at && memory.mentioned_at !== memory.created_at && (
                        <div className="text-xs text-green-600 mt-2">
                          曾被引用
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}