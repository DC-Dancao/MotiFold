"use client";

import React, { useState, useEffect, useMemo } from 'react';
import { fetchWithAuth, getApiUrl } from '../../app/lib/api';
import {
  Key,
  Plus,
  Trash2,
  Copy,
  Search,
  Loader2,
  X,
  ChevronDown,
  ChevronRight,
  Terminal,
  XCircle,
  CheckCircle,
  Clock,
  AlertCircle
} from 'lucide-react';

// =============================================================================
// Types
// =============================================================================

interface ApiKey {
  id: number;
  key_id: string;
  key_prefix: string;
  name: string | null;
  organization_id: number;
  expires_at: string | null;
  created_at: string;
}

interface MCPTool {
  name: string;
  category: string;
  description: string;
  inputs: string[];
}

interface MCPToolCategory {
  name: string;
  icon: string;
  tools: MCPTool[];
}

// =============================================================================
// Constants
// =============================================================================

const MCP_TOOLS: MCPToolCategory[] = [
  {
    name: 'Workspace',
    icon: 'folder',
    tools: [
      { name: 'workspace_list', category: 'Workspace', description: 'List all workspaces', inputs: [] },
      { name: 'workspace_get', category: 'Workspace', description: 'Get workspace by ID', inputs: ['workspace_id: int'] },
      { name: 'workspace_create', category: 'Workspace', description: 'Create a new workspace', inputs: ['name: str'] },
      { name: 'workspace_delete', category: 'Workspace', description: 'Delete a workspace', inputs: ['workspace_id: int'] },
    ],
  },
  {
    name: 'Chat',
    icon: 'message',
    tools: [
      { name: 'chat_list', category: 'Chat', description: 'List chats', inputs: ['workspace_id?: int'] },
      { name: 'chat_get', category: 'Chat', description: 'Get chat by ID', inputs: ['chat_id: int'] },
      { name: 'chat_create', category: 'Chat', description: 'Create a new chat', inputs: ['workspace_id?: int'] },
      { name: 'chat_send_message', category: 'Chat', description: 'Send message to chat', inputs: ['chat_id: int', 'content: str'] },
      { name: 'chat_get_history', category: 'Chat', description: 'Get chat message history', inputs: ['chat_id: int', 'limit?: int'] },
    ],
  },
  {
    name: 'Matrix',
    icon: 'grid',
    tools: [
      { name: 'matrix_list_analyses', category: 'Matrix', description: 'List morphological analyses', inputs: ['workspace_id?: int'] },
      { name: 'matrix_get_analysis', category: 'Matrix', description: 'Get analysis by ID', inputs: ['analysis_id: int'] },
      { name: 'matrix_start_analysis', category: 'Matrix', description: 'Start new analysis', inputs: ['focus_question: str', 'workspace_id?: int'] },
      { name: 'matrix_evaluate_consistency', category: 'Matrix', description: 'Evaluate matrix consistency', inputs: ['analysis_id: int'] },
      { name: 'matrix_save_analysis', category: 'Matrix', description: 'Save analysis', inputs: ['focus_question: str', 'parameters: list', 'matrix: dict', 'analysis_id?: int'] },
      { name: 'matrix_delete_analysis', category: 'Matrix', description: 'Delete analysis', inputs: ['analysis_id: int'] },
    ],
  },
  {
    name: 'Blackboard',
    icon: 'presentation',
    tools: [
      { name: 'blackboard_list', category: 'Blackboard', description: 'List blackboards', inputs: ['workspace_id?: int'] },
      { name: 'blackboard_get', category: 'Blackboard', description: 'Get blackboard by ID', inputs: ['blackboard_id: int'] },
      { name: 'blackboard_generate', category: 'Blackboard', description: 'Generate new blackboard', inputs: ['topic: str', 'workspace_id?: int'] },
      { name: 'blackboard_delete', category: 'Blackboard', description: 'Delete blackboard', inputs: ['blackboard_id: int'] },
    ],
  },
  {
    name: 'Research',
    icon: 'search',
    tools: [
      { name: 'research_list_reports', category: 'Research', description: 'List research reports', inputs: [] },
      { name: 'research_get_report', category: 'Research', description: 'Get report by ID', inputs: ['report_id: int'] },
      { name: 'research_start', category: 'Research', description: 'Start deep research', inputs: ['query: str', 'level?: str', 'max_iterations?: int', 'max_results?: int'] },
      { name: 'research_get_result', category: 'Research', description: 'Get research result', inputs: ['task_id: str'] },
      { name: 'research_get_state', category: 'Research', description: 'Get research state', inputs: ['task_id: str'] },
      { name: 'research_delete_report', category: 'Research', description: 'Delete report', inputs: ['report_id: int'] },
    ],
  },
  {
    name: 'Memory',
    icon: 'brain',
    tools: [
      { name: 'memory_recall', category: 'Memory', description: 'Recall relevant memories', inputs: ['workspace_id: int', 'query: str', 'memory_type?: str', 'limit?: int'] },
      { name: 'memory_retain', category: 'Memory', description: 'Store a memory', inputs: ['workspace_id: int', 'content: str', 'memory_type?: str'] },
      { name: 'memory_get_stats', category: 'Memory', description: 'Get memory statistics', inputs: ['workspace_id: int'] },
      { name: 'memory_get_entity_memories', category: 'Memory', description: 'Get entity memories', inputs: ['workspace_id: int', 'entity_name: str', 'limit?: int'] },
    ],
  },
  {
    name: 'Operations',
    icon: 'activity',
    tools: [
      { name: 'operation_list', category: 'Operations', description: 'List recent operations', inputs: [] },
      { name: 'operation_get_status', category: 'Operations', description: 'Get operation status', inputs: ['task_id: str'] },
    ],
  },
];

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  folder: <span className="text-amber-500">📁</span>,
  message: <span className="text-blue-500">💬</span>,
  grid: <span className="text-purple-500">🔲</span>,
  presentation: <span className="text-orange-500">📋</span>,
  search: <span className="text-green-500">🔍</span>,
  brain: <span className="text-pink-500">🧠</span>,
  activity: <span className="text-cyan-500">📊</span>,
};

// =============================================================================
// Component
// =============================================================================

export default function McpPanel() {
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [isLoadingKeys, setIsLoadingKeys] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [expiresDays, setExpiresDays] = useState<string>('');
  const [isCreating, setIsCreating] = useState(false);
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);
  const [copiedKeyId, setCopiedKeyId] = useState<string | null>(null);
  const [deletingKeyId, setDeletingKeyId] = useState<number | null>(null);

  const [toolSearch, setToolSearch] = useState('');
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
    new Set(MCP_TOOLS.map((c) => c.name))
  );
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  // Fetch API keys
  useEffect(() => {
    fetchApiKeys();
  }, []);

  const fetchApiKeys = async () => {
    setIsLoadingKeys(true);
    try {
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/auth/api-keys`);
      if (res.ok) {
        const data = await res.json();
        setApiKeys(data);
      }
    } catch (err) {
      console.error('Failed to fetch API keys:', err);
    } finally {
      setIsLoadingKeys(false);
    }
  };

  const createApiKey = async () => {
    if (!newKeyName.trim()) return;
    setIsCreating(true);
    try {
      const apiUrl = getApiUrl();
      const body: Record<string, unknown> = { name: newKeyName.trim() };
      if (expiresDays) {
        body.expires_days = parseInt(expiresDays, 10);
      }
      const res = await fetchWithAuth(`${apiUrl}/auth/api-key`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const data = await res.json();
        setNewlyCreatedKey(data.key);
        fetchApiKeys();
      }
    } catch (err) {
      console.error('Failed to create API key:', err);
    } finally {
      setIsCreating(false);
    }
  };

  const deleteApiKey = async (keyId: string, id: number) => {
    setDeletingKeyId(id);
    try {
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/auth/api-key/${keyId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setApiKeys((prev) => prev.filter((k) => k.id !== id));
      }
    } catch (err) {
      console.error('Failed to delete API key:', err);
    } finally {
      setDeletingKeyId(null);
    }
  };

  const copyToClipboard = async (text: string, keyId: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKeyId(keyId);
      setTimeout(() => setCopiedKeyId(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const toggleCategory = (name: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  };

  // Filter tools
  const filteredCategories = useMemo(() => {
    if (!toolSearch.trim()) return MCP_TOOLS;
    const search = toolSearch.toLowerCase();
    return MCP_TOOLS.map((cat) => ({
      ...cat,
      tools: cat.tools.filter(
        (t) =>
          t.name.toLowerCase().includes(search) ||
          t.description.toLowerCase().includes(search) ||
          t.category.toLowerCase().includes(search)
      ),
    })).filter((cat) => cat.tools.length > 0);
  }, [toolSearch]);

  const displayedCategories = selectedCategory
    ? filteredCategories.filter((c) => c.name === selectedCategory)
    : filteredCategories;

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
  };

  const isExpired = (expiresAt: string | null) => {
    if (!expiresAt) return false;
    return new Date(expiresAt) < new Date();
  };

  return (
    <div className="flex flex-col h-full bg-slate-50">
      {/* Header */}
      <div className="px-6 py-4 bg-white border-b border-slate-200">
        <h1 className="text-xl font-bold text-slate-800 flex items-center gap-2">
          <Terminal className="w-5 h-5 text-indigo-600" />
          MCP 面板
        </h1>
        <p className="text-sm text-slate-500 mt-1">管理 API 密钥和查看可用工具</p>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {/* API Keys Section */}
        <section className="p-6 border-b border-slate-200">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Key className="w-4 h-4 text-slate-600" />
              <h2 className="text-sm font-semibold text-slate-700">API 密钥</h2>
            </div>
            <button
              onClick={() => {
                setShowCreateModal(true);
                setNewlyCreatedKey(null);
                setNewKeyName('');
                setExpiresDays('');
              }}
              className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors"
            >
              <Plus className="w-3 h-3" />
              新建密钥
            </button>
          </div>

          {/* API Keys List */}
          {isLoadingKeys ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-5 h-5 text-slate-400 animate-spin" />
            </div>
          ) : apiKeys.length === 0 ? (
            <div className="text-center py-6 text-sm text-slate-500">
              暂无 API 密钥
            </div>
          ) : (
            <div className="space-y-2">
              {apiKeys.map((key) => (
                <div
                  key={key.id}
                  className="flex items-center justify-between p-3 bg-white rounded-xl border border-slate-200 group"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-700">
                        {key.name || '未命名密钥'}
                      </span>
                      {isExpired(key.expires_at) && (
                        <span className="flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-medium text-red-600 bg-red-50 rounded">
                          <XCircle className="w-3 h-3" />
                          已过期
                        </span>
                      )}
                      {key.expires_at && !isExpired(key.expires_at) && (
                        <span className="flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-medium text-amber-600 bg-amber-50 rounded">
                          <Clock className="w-3 h-3" />
                          {formatDate(key.expires_at)}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-1 mt-1">
                      <code className="text-xs text-slate-500 font-mono">{key.key_prefix}***</code>
                      <button
                        onClick={() => copyToClipboard(key.key_id, key.key_id)}
                        className="p-1 text-slate-400 hover:text-slate-600 transition-colors"
                        title="复制 Key ID"
                      >
                        {copiedKeyId === key.key_id ? (
                          <CheckCircle className="w-3 h-3 text-green-500" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )}
                      </button>
                    </div>
                  </div>
                  <button
                    onClick={() => deleteApiKey(key.key_id, key.id)}
                    disabled={deletingKeyId === key.id}
                    className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100 disabled:opacity-50"
                    title="删除密钥"
                  >
                    {deletingKeyId === key.id ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Trash2 className="w-4 h-4" />
                    )}
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Tools Section */}
        <section className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Terminal className="w-4 h-4 text-slate-600" />
              <h2 className="text-sm font-semibold text-slate-700">可用工具</h2>
              <span className="text-xs text-slate-400">
                {MCP_TOOLS.reduce((acc, c) => acc + c.tools.length, 0)} 个
              </span>
            </div>
          </div>

          {/* Search */}
          <div className="relative mb-4">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              value={toolSearch}
              onChange={(e) => setToolSearch(e.target.value)}
              placeholder="搜索工具..."
              className="w-full pl-9 pr-4 py-2 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            />
            {toolSearch && (
              <button
                onClick={() => setToolSearch('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Category Filter */}
          <div className="flex flex-wrap gap-2 mb-4">
            <button
              onClick={() => setSelectedCategory(null)}
              className={`px-2 py-1 text-xs font-medium rounded-lg transition-colors ${
                !selectedCategory
                  ? 'bg-indigo-100 text-indigo-700'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              全部
            </button>
            {MCP_TOOLS.map((cat) => (
              <button
                key={cat.name}
                onClick={() => setSelectedCategory(cat.name === selectedCategory ? null : cat.name)}
                className={`px-2 py-1 text-xs font-medium rounded-lg transition-colors ${
                  selectedCategory === cat.name
                    ? 'bg-indigo-100 text-indigo-700'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {cat.name}
              </button>
            ))}
          </div>

          {/* Tools List */}
          <div className="space-y-3">
            {displayedCategories.map((category) => (
              <div key={category.name} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                <button
                  onClick={() => toggleCategory(category.name)}
                  className="w-full flex items-center justify-between p-3 hover:bg-slate-50 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    {CATEGORY_ICONS[category.icon]}
                    <span className="text-sm font-medium text-slate-700">{category.name}</span>
                    <span className="text-xs text-slate-400">({category.tools.length})</span>
                  </div>
                  {expandedCategories.has(category.name) ? (
                    <ChevronDown className="w-4 h-4 text-slate-400" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-slate-400" />
                  )}
                </button>

                {expandedCategories.has(category.name) && (
                  <div className="border-t border-slate-100">
                    {category.tools.map((tool) => (
                      <div
                        key={tool.name}
                        className="px-3 py-2.5 border-b border-slate-100 last:border-b-0 hover:bg-slate-50 transition-colors"
                      >
                        <div className="flex items-start gap-2">
                          <code className="text-xs font-mono text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded shrink-0">
                            {tool.name}
                          </code>
                          <div className="flex-1 min-w-0">
                            <p className="text-xs text-slate-600">{tool.description}</p>
                            {tool.inputs.length > 0 && (
                              <p className="text-[10px] text-slate-400 mt-0.5 font-mono">
                                {tool.inputs.join(', ')}
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}

            {displayedCategories.length === 0 && (
              <div className="text-center py-8 text-sm text-slate-500">
                <Search className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                未找到匹配的工具
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-slate-800">创建 API 密钥</h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-slate-600 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {newlyCreatedKey ? (
              <div className="p-6">
                <div className="flex items-center gap-2 mb-4">
                  <CheckCircle className="w-5 h-5 text-green-500" />
                  <span className="text-sm font-medium text-green-700">密钥创建成功</span>
                </div>
                <p className="text-xs text-slate-500 mb-3">
                  请立即复制密钥，关闭后将无法再次查看完整密钥。
                </p>
                <div className="flex items-center gap-2 p-3 bg-slate-100 rounded-xl">
                  <code className="flex-1 text-sm font-mono text-slate-700 break-all">
                    {newlyCreatedKey}
                  </code>
                  <button
                    onClick={() => copyToClipboard(newlyCreatedKey, 'new')}
                    className="p-2 text-slate-500 hover:text-indigo-600 hover:bg-white rounded-lg transition-colors shrink-0"
                  >
                    {copiedKeyId === 'new' ? (
                      <CheckCircle className="w-4 h-4 text-green-500" />
                    ) : (
                      <Copy className="w-4 h-4" />
                    )}
                  </button>
                </div>
                <button
                  onClick={() => setShowCreateModal(false)}
                  className="w-full mt-4 px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-xl hover:bg-indigo-700 transition-colors"
                >
                  关闭
                </button>
              </div>
            ) : (
              <div className="p-6">
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1.5">
                      密钥名称
                    </label>
                    <input
                      type="text"
                      autoFocus
                      value={newKeyName}
                      onChange={(e) => setNewKeyName(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && createApiKey()}
                      placeholder="例如：生产环境密钥"
                      className="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1.5">
                      过期时间（可选）
                    </label>
                    <select
                      value={expiresDays}
                      onChange={(e) => setExpiresDays(e.target.value)}
                      className="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent bg-white"
                    >
                      <option value="">永不过期</option>
                      <option value="7">7 天</option>
                      <option value="30">30 天</option>
                      <option value="90">90 天</option>
                      <option value="365">365 天</option>
                    </select>
                  </div>
                </div>
                <div className="flex items-center gap-3 mt-6">
                  <button
                    onClick={() => setShowCreateModal(false)}
                    className="flex-1 px-4 py-2 text-sm font-medium text-slate-600 bg-slate-100 rounded-xl hover:bg-slate-200 transition-colors"
                  >
                    取消
                  </button>
                  <button
                    onClick={createApiKey}
                    disabled={!newKeyName.trim() || isCreating}
                    className="flex-1 px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-xl hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    {isCreating && <Loader2 className="w-4 h-4 animate-spin" />}
                    创建
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
