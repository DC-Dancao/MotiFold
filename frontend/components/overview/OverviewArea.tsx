"use client";

import React, { useState, useEffect } from 'react';
import {
  MessageSquare,
  Grid3X3,
  Presentation,
  Search,
  Brain,
  TrendingUp,
  Clock,
  Loader2,
  AlertCircle,
  ChevronRight,
} from 'lucide-react';
import { fetchWithAuth, getApiUrl } from '../../app/lib/api';

interface OverviewStats {
  chats: {
    total: number;
    recent: Array<{
      id: number;
      title: string;
      model: string;
      created_at: string;
    }>;
  };
  morphological_analyses: {
    total: number;
    recent: Array<{
      id: number;
      focus_question: string;
      status: string;
      created_at: string;
    }>;
  };
  blackboards: {
    total: number;
    status_breakdown: Record<string, number>;
    recent: Array<{
      id: number;
      topic: string;
      status: string;
      created_at: string;
    }>;
  };
  research_reports: {
    total: number;
    status_breakdown: Record<string, number>;
    recent: Array<{
      id: number;
      query: string;
      research_topic: string;
      status: string;
      level: string;
      created_at: string;
    }>;
  };
  memory: {
    total: number;
    by_type: Record<string, number>;
  } | null;
}

const STATUS_COLORS: Record<string, string> = {
  done: 'bg-green-100 text-green-700',
  running: 'bg-blue-100 text-blue-700',
  pending: 'bg-amber-100 text-amber-700',
  error: 'bg-red-100 text-red-700',
  completed: 'bg-green-100 text-green-700',
};

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return '刚刚';
  if (minutes < 60) return `${minutes}分钟前`;
  if (hours < 24) return `${hours}小时前`;
  if (days < 7) return `${days}天前`;
  return date.toLocaleDateString('zh-CN');
}

function StatCard({
  icon: Icon,
  title,
  value,
  subtitle,
  color,
}: {
  icon: React.ElementType;
  title: string;
  value: number | string;
  subtitle?: string;
  color: string;
}) {
  return (
    <div className="bg-white rounded-xl p-5 shadow-sm border border-slate-100 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500">{title}</p>
          <p className="text-3xl font-bold text-slate-900 mt-1">{value}</p>
          {subtitle && (
            <p className="text-xs text-slate-400 mt-1">{subtitle}</p>
          )}
        </div>
        <div className={`p-3 rounded-xl ${color}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </div>
  );
}

function RecentItem({
  title,
  subtitle,
  status,
  date,
  onClick,
}: {
  title: string;
  subtitle?: string;
  status?: string;
  date: string;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center justify-between p-3 rounded-lg hover:bg-slate-50 transition-colors text-left"
    >
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-slate-800 truncate">{title}</p>
        {subtitle && (
          <p className="text-xs text-slate-500 truncate mt-0.5">{subtitle}</p>
        )}
      </div>
      <div className="flex items-center gap-2 ml-3">
        {status && STATUS_COLORS[status] && (
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[status]}`}>
            {status === 'done' ? '完成' : status === 'running' ? '运行中' : status === 'completed' ? '完成' : status}
          </span>
        )}
        <span className="text-xs text-slate-400 whitespace-nowrap">{formatDate(date)}</span>
        <ChevronRight className="w-4 h-4 text-slate-300" />
      </div>
    </button>
  );
}

export default function OverviewArea() {
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Workspace ID from localStorage
  const workspaceIdFromStorage = typeof window !== 'undefined'
    ? parseInt(localStorage.getItem('motifold_active_workspace_id') || '0', 10)
    : 0;
  const workspaceId = isNaN(workspaceIdFromStorage) ? 0 : workspaceIdFromStorage;

  useEffect(() => {
    loadStats();
  }, [workspaceId]);

  // Listen for workspace changes from sidebar
  useEffect(() => {
    const handleWorkspaceChanged = (e: CustomEvent) => {
      if (e.detail?.workspaceId) {
        loadStats();
      }
    };
    window.addEventListener('workspace-changed', handleWorkspaceChanged as EventListener);
    return () => {
      window.removeEventListener('workspace-changed', handleWorkspaceChanged as EventListener);
    };
  }, []);

  const loadStats = async () => {
    if (!workspaceId) {
      setIsLoading(false);
      setError('请先选择一个工作区');
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const apiUrl = getApiUrl();
      const response = await fetchWithAuth(
        `${apiUrl}/stats/overview?workspace_id=${workspaceId}`
      );

      if (!response.ok) {
        throw new Error('Failed to load stats');
      }

      const data = await response.json();
      setStats(data);
    } catch (err) {
      console.error('Failed to load overview stats:', err);
      setError('加载数据失败，请刷新重试');
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-white">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-indigo-600 animate-spin mx-auto" />
          <p className="mt-3 text-sm text-slate-500">加载中...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center bg-white">
        <div className="text-center">
          <AlertCircle className="w-8 h-8 text-red-500 mx-auto" />
          <p className="mt-3 text-sm text-slate-600">{error}</p>
          <button
            onClick={loadStats}
            className="mt-3 px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 transition-colors"
          >
            重试
          </button>
        </div>
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="flex-1 overflow-y-auto bg-white">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900">总览</h1>
          <p className="text-sm text-slate-500 mt-1">查看当前工作区的整体数据情况</p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4 mb-8">
          <StatCard
            icon={MessageSquare}
            title="对话"
            value={stats.chats.total}
            subtitle="聊天记录"
            color="bg-blue-50 text-blue-600"
          />
          <StatCard
            icon={Grid3X3}
            title="形态分析"
            value={stats.morphological_analyses.total}
            subtitle="形态学分析"
            color="bg-indigo-50 text-indigo-600"
          />
          <StatCard
            icon={Presentation}
            title="黑板讲解"
            value={stats.blackboards.total}
            subtitle={
              stats.blackboards.status_breakdown?.running
                ? `${stats.blackboards.status_breakdown.running} 运行中`
                : undefined
            }
            color="bg-amber-50 text-amber-600"
          />
          <StatCard
            icon={Search}
            title="深度研究"
            value={stats.research_reports.total}
            subtitle={
              stats.research_reports.status_breakdown?.running
                ? `${stats.research_reports.status_breakdown.running} 运行中`
                : undefined
            }
            color="bg-purple-50 text-purple-600"
          />
          <StatCard
            icon={Brain}
            title="记忆"
            value={stats.memory?.total ?? 0}
            subtitle="记忆单元"
            color="bg-green-50 text-green-600"
          />
        </div>

        {/* Recent Activity */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Recent Chats */}
          <div className="bg-white rounded-xl p-5 shadow-sm border border-slate-100">
            <div className="flex items-center gap-2 mb-4">
              <MessageSquare className="w-4 h-4 text-blue-500" />
              <h2 className="font-semibold text-slate-800">最近对话</h2>
            </div>
            <div className="space-y-1">
              {stats.chats.recent.length === 0 ? (
                <p className="text-sm text-slate-400 py-4 text-center">暂无对话记录</p>
              ) : (
                stats.chats.recent.map((chat) => (
                  <RecentItem
                    key={chat.id}
                    title={chat.title}
                    subtitle={chat.model}
                    date={chat.created_at}
                  />
                ))
              )}
            </div>
          </div>

          {/* Recent Research */}
          <div className="bg-white rounded-xl p-5 shadow-sm border border-slate-100">
            <div className="flex items-center gap-2 mb-4">
              <Search className="w-4 h-4 text-purple-500" />
              <h2 className="font-semibold text-slate-800">最近研究</h2>
            </div>
            <div className="space-y-1">
              {stats.research_reports.recent.length === 0 ? (
                <p className="text-sm text-slate-400 py-4 text-center">暂无研究记录</p>
              ) : (
                stats.research_reports.recent.map((report) => (
                  <RecentItem
                    key={report.id}
                    title={report.research_topic || report.query}
                    status={report.status}
                    date={report.created_at}
                  />
                ))
              )}
            </div>
          </div>

          {/* Recent Blackboards */}
          <div className="bg-white rounded-xl p-5 shadow-sm border border-slate-100">
            <div className="flex items-center gap-2 mb-4">
              <Presentation className="w-4 h-4 text-amber-500" />
              <h2 className="font-semibold text-slate-800">最近黑板</h2>
            </div>
            <div className="space-y-1">
              {stats.blackboards.recent.length === 0 ? (
                <p className="text-sm text-slate-400 py-4 text-center">暂无黑板记录</p>
              ) : (
                stats.blackboards.recent.map((bb) => (
                  <RecentItem
                    key={bb.id}
                    title={bb.topic}
                    status={bb.status}
                    date={bb.created_at}
                  />
                ))
              )}
            </div>
          </div>

          {/* Recent Morphological Analyses */}
          <div className="bg-white rounded-xl p-5 shadow-sm border border-slate-100">
            <div className="flex items-center gap-2 mb-4">
              <Grid3X3 className="w-4 h-4 text-indigo-500" />
              <h2 className="font-semibold text-slate-800">最近形态分析</h2>
            </div>
            <div className="space-y-1">
              {stats.morphological_analyses.recent.length === 0 ? (
                <p className="text-sm text-slate-400 py-4 text-center">暂无形态分析记录</p>
              ) : (
                stats.morphological_analyses.recent.map((ma) => (
                  <RecentItem
                    key={ma.id}
                    title={ma.focus_question || '形态分析'}
                    status={ma.status}
                    date={ma.created_at}
                  />
                ))
              )}
            </div>
          </div>
        </div>

        {/* Memory Breakdown (if available) */}
        {stats.memory && stats.memory.total > 0 && (
          <div className="mt-6 bg-white rounded-xl p-5 shadow-sm border border-slate-100">
            <div className="flex items-center gap-2 mb-4">
              <Brain className="w-4 h-4 text-green-500" />
              <h2 className="font-semibold text-slate-800">记忆类型分布</h2>
            </div>
            <div className="flex flex-wrap gap-3">
              {Object.entries(stats.memory.by_type).map(([type, count]) => (
                <div
                  key={type}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-50"
                >
                  <span className="text-sm text-slate-600">
                    {type === 'fact' ? '事实' : type === 'preference' ? '偏好' : type === 'conclusion' ? '结论' : type === 'context' ? '上下文' : type}
                  </span>
                  <span className="font-semibold text-slate-800">{count}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
