"use client";

import React, { useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams, usePathname } from 'next/navigation';
import { fetchWithAuth, getApiUrl } from '../../app/lib/api';
import { clearAuthCookies } from '../../app/lib/auth-actions';
import { useOrg } from '../../app/lib/org-context';
import {
  MessageSquare,
  ChevronDown,
  Plus,
  Network,
  Presentation,
  Loader2,
  MoreHorizontal,
  Trash2,
  X,
  Search,
  Brain,
  Terminal,
  LayoutDashboard,
} from 'lucide-react';

interface Chat {
  id: number;
  title: string;
  created_at: string;
}

interface ChatTitleUpdatedDetail {
  chatId: number;
  title: string;
  createdAt?: string;
}

interface Workspace {
  id: number;
  name: string;
}

interface MorphologicalHistory {
  id: number;
  focus_question?: string;
  updated_at: string;
  [key: string]: unknown;
}

interface BlackboardHistory {
  id: number;
  topic?: string;
  created_at: string;
  status?: string;
  [key: string]: unknown;
}

interface ResearchHistory {
  id: number;
  query?: string;
  research_topic?: string;
  updated_at: string;
  level?: string;
  status?: 'running' | 'done' | 'error';
  task_id?: string;
  [key: string]: unknown;
}

export default function LeftSidebar() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const [username, setUsername] = useState('U');
  const [chats, setChats] = useState<Chat[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<number | null>(null);
  const [isLoadingChats, setIsLoadingChats] = useState(false);
  
  // Morphological History State
  const [morphologicalHistory, setMorphologicalHistory] = useState<MorphologicalHistory[]>([]);
  const [isLoadingMorphological, setIsLoadingMorphological] = useState(false);
  
  // Blackboard History State
  const [blackboardHistory, setBlackboardHistory] = useState<BlackboardHistory[]>([]);
  const [isLoadingBlackboard, setIsLoadingBlackboard] = useState(false);

  // Research History State
  const [researchHistory, setResearchHistory] = useState<ResearchHistory[]>([]);
  const [isLoadingResearch, setIsLoadingResearch] = useState(false);
  
  const [skip, setSkip] = useState(0);
  const [isChatsOpen, setIsChatsOpen] = useState(true);
  const [isViewsOpen, setIsViewsOpen] = useState(true);
  const [hasMore, setHasMore] = useState(true);
  const [isFetchingMore, setIsFetchingMore] = useState(false);
  const [openMenuId, setOpenMenuId] = useState<number | null>(null);
  const [isCreateWorkspaceModalOpen, setIsCreateWorkspaceModalOpen] = useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState('');
  const [chatToDelete, setChatToDelete] = useState<number | null>(null);
  const LIMIT = 20;

  const { organizations, currentOrg, setCurrentOrg, isLoading: isLoadingOrgs } = useOrg();
  const [isOrgDropdownOpen, setIsOrgDropdownOpen] = useState(false);
  const [isCreateOrgModalOpen, setIsCreateOrgModalOpen] = useState(false);
  const [newOrgName, setNewOrgName] = useState('');
  const [newOrgSlug, setNewOrgSlug] = useState('');

  const activeChatId = searchParams.get('chatId');

  useEffect(() => {
    const storedUsername = localStorage.getItem('motifold_username');
    if (storedUsername) {
      setUsername(storedUsername.charAt(0).toUpperCase());
    }
  }, []);

  const fetchChats = useCallback(async (currentSkip = 0, append = false, workspaceId?: number) => {
    try {
      if (!append) {
        setIsLoadingChats(true);
      } else {
        setIsFetchingMore(true);
      }

      const apiUrl = getApiUrl();
      const wsQuery = workspaceId ? `&workspace_id=${workspaceId}` : '';
      const res = await fetchWithAuth(`${apiUrl}/chats/?skip=${currentSkip}&limit=${LIMIT}${wsQuery}`);

      if (res.ok) {
        const data = await res.json();
        const fetchedChats = Array.isArray(data) ? data : data.items ?? [];

        if (append) {
          setChats(prev => {
            // Filter out any duplicates just in case
            const existingIds = new Set(prev.map(c => c.id));
            const uniqueNewChats = fetchedChats.filter((c: Chat) => !existingIds.has(c.id));
            return [...prev, ...uniqueNewChats];
          });
        } else {
          setChats(fetchedChats);
        }

        setHasMore(fetchedChats.length === LIMIT);
      }
    } catch (error) {
      console.error("Failed to fetch chats:", error);
    } finally {
      setIsLoadingChats(false);
      setIsFetchingMore(false);
    }
  }, []);

  const refreshChats = useCallback((workspaceId?: number) => {
    setSkip(0);
    fetchChats(0, false, workspaceId);
  }, [fetchChats]);

  useEffect(() => {
    const fetchWorkspaces = async () => {
      try {
        const apiUrl = getApiUrl();
        const res = await fetchWithAuth(`${apiUrl}/workspaces/`);
        if (res.ok) {
          const data = await res.json();
          if (data.length > 0) {
            setWorkspaces(data);
            const savedWsId = localStorage.getItem('motifold_active_workspace_id');
            let wsId = savedWsId ? parseInt(savedWsId, 10) : data[0].id;
            // Validate if saved wsId actually exists
            if (!data.find((w: Workspace) => w.id === wsId)) {
              wsId = data[0].id;
            }
            setActiveWorkspaceId(wsId);
            refreshChats(wsId);
            // Tell ChatArea about the active workspace
            window.dispatchEvent(new CustomEvent('workspace-changed', { detail: { workspaceId: wsId } }));
          } else {
            // Create default workspace
            const createRes = await fetchWithAuth(`${apiUrl}/workspaces/`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ name: 'Default Workspace' })
            });
            if (createRes.ok) {
              const newWs = await createRes.json();
              setWorkspaces([newWs]);
              setActiveWorkspaceId(newWs.id);
              refreshChats(newWs.id);
              window.dispatchEvent(new CustomEvent('workspace-changed', { detail: { workspaceId: newWs.id } }));
            }
          }
        }
      } catch (e) {
        console.error('Failed to fetch workspaces', e);
      }
    };
    
    fetchWorkspaces();
  }, [refreshChats, currentOrg?.id]);

  useEffect(() => {
    if (pathname === '/matrix') {
      fetchMorphologicalHistory();
    } else if (pathname === '/blackboard') {
      fetchBlackboardHistory();
    } else if (pathname === '/research') {
      fetchResearchHistory();
    }
  }, [pathname]);

  useEffect(() => {
    const handleRefreshHistory = () => {
      if (pathname === '/matrix') {
        fetchMorphologicalHistory();
      } else if (pathname === '/blackboard') {
        fetchBlackboardHistory();
      } else if (pathname === '/research') {
        fetchResearchHistory();
      }
    };
    window.addEventListener('refresh-history', handleRefreshHistory);
    return () => {
      window.removeEventListener('refresh-history', handleRefreshHistory);
    };
  }, [pathname]);

  const fetchBlackboardHistory = async () => {
    try {
      setIsLoadingBlackboard(true);
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/blackboard/history`);
      if (res.ok) {
        const data = await res.json();
        setBlackboardHistory(data);
      }
    } catch (error) {
      console.error("Failed to fetch blackboard history", error);
    } finally {
      setIsLoadingBlackboard(false);
    }
  };

  const handleSelectBlackboard = (id: number) => {
    window.dispatchEvent(new CustomEvent('load-blackboard', { detail: { id } }));
  };

  const confirmDeleteBlackboard = async () => {
    if (!chatToDelete) return;
    
    try {
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/blackboard/${chatToDelete}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        setBlackboardHistory(prev => prev.filter(a => a.id !== chatToDelete));
        window.dispatchEvent(new CustomEvent('deleted-blackboard', { detail: { id: chatToDelete } }));
      }
    } catch (error) {
      console.error("Failed to delete blackboard:", error);
    } finally {
      setChatToDelete(null);
    }
  };

  const fetchMorphologicalHistory = async () => {
    try {
      setIsLoadingMorphological(true);
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/matrix/morphological`);
      if (res.ok) {
        const data = await res.json();
        setMorphologicalHistory(data);
      }
    } catch (error) {
      console.error("Failed to fetch morphological history", error);
    } finally {
      setIsLoadingMorphological(false);
    }
  };

  const fetchResearchHistory = async () => {
    try {
      setIsLoadingResearch(true);
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/research/history`);
      if (res.ok) {
        const data = await res.json();
        setResearchHistory(data);
      }
    } catch (error) {
      console.error("Failed to fetch research history", error);
    } finally {
      setIsLoadingResearch(false);
    }
  };

  // Auto-refresh research history every 30s to update running status dots
  useEffect(() => {
    if (pathname !== '/research') return;
    const interval = setInterval(() => {
      fetchResearchHistory();
    }, 30000);
    return () => clearInterval(interval);
  }, [pathname]);

  const handleSelectMorphologicalAnalysis = (id: number) => {
    // We dispatch an event to let MorphologicalTab know which analysis to load
    window.dispatchEvent(new CustomEvent('load-morphological-analysis', { detail: { id } }));
  };

  const handleSelectResearch = (id: number) => {
    window.dispatchEvent(new CustomEvent('load-research-report', { detail: { id } }));
  };

  const handleDeleteMorphologicalClick = (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    setChatToDelete(id); // reuse the modal state
    setOpenMenuId(null);
  };

  const handleDeleteResearchClick = (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    setChatToDelete(id);
    setOpenMenuId(null);
  };

  const confirmDeleteMorphological = async () => {
    if (!chatToDelete) return;

    try {
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/matrix/morphological/${chatToDelete}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        setMorphologicalHistory(prev => prev.filter(a => a.id !== chatToDelete));
        // Clear current active one if deleted
        window.dispatchEvent(new CustomEvent('deleted-morphological-analysis', { detail: { id: chatToDelete } }));
      }
    } catch (error) {
      console.error("Failed to delete morphological analysis:", error);
    } finally {
      setChatToDelete(null);
    }
  };

  const confirmDeleteResearch = async () => {
    if (!chatToDelete) return;

    try {
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/research/${chatToDelete}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        setResearchHistory(prev => prev.filter(a => a.id !== chatToDelete));
        window.dispatchEvent(new CustomEvent('deleted-research-report', { detail: { id: chatToDelete } }));
      }
    } catch (error) {
      console.error("Failed to delete research report:", error);
    } finally {
      setChatToDelete(null);
    }
  };

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
    if (scrollHeight - scrollTop - clientHeight < 20 && hasMore && !isFetchingMore && !isLoadingChats) {
      const newSkip = skip + LIMIT;
      setSkip(newSkip);
      fetchChats(newSkip, true);
    }
  };

  // Only refresh active chat when we already have an active workspace
  useEffect(() => {
    if (activeChatId && activeChatId !== 'new' && !isLoadingChats && chats.length > 0 && activeWorkspaceId) {
      const chatExists = chats.some(c => c.id.toString() === activeChatId);
      if (!chatExists) {
        refreshChats(activeWorkspaceId);
      }
    }
  }, [activeChatId, chats, isLoadingChats, refreshChats, activeWorkspaceId]);

  useEffect(() => {
    const handleChatTitleUpdated = (event: Event) => {
      const customEvent = event as CustomEvent<ChatTitleUpdatedDetail>;
      const detail = customEvent.detail;

      if (!detail?.chatId || !detail.title) {
        return;
      }

      setChats(prev => {
        const existingIndex = prev.findIndex(chat => chat.id === detail.chatId);

        if (existingIndex === -1) {
          return [
            {
              id: detail.chatId,
              title: detail.title,
              created_at: detail.createdAt || new Date().toISOString()
            },
            ...prev
          ];
        }

        return prev.map(chat => (
          chat.id === detail.chatId
            ? {
                ...chat,
                title: detail.title,
                created_at: detail.createdAt || chat.created_at
              }
            : chat
        ));
      });
    };

    window.addEventListener('chat-title-updated', handleChatTitleUpdated as EventListener);
    return () => window.removeEventListener('chat-title-updated', handleChatTitleUpdated as EventListener);
  }, []);

  const handleLogout = async () => {
    localStorage.removeItem('motifold_username');
    localStorage.removeItem('motifold_active_workspace_id');
    localStorage.removeItem('motifold_current_org_id');
    try {
      await clearAuthCookies();
    } catch (e) {
      // Ignore redirect error
    }
    window.location.href = '/login';
  };

  const handleNewChat = () => {
    router.push('/chat?chatId=new');
  };

  const handleSelectWorkspace = (workspaceId: number) => {
    setActiveWorkspaceId(workspaceId);
    localStorage.setItem('motifold_active_workspace_id', workspaceId.toString());
    refreshChats(workspaceId);
    window.dispatchEvent(new CustomEvent('workspace-changed', { detail: { workspaceId } }));
    router.push('/chat?chatId=new');
  };

  const handleCreateWorkspaceClick = () => {
    setNewWorkspaceName('');
    setIsCreateWorkspaceModalOpen(true);
  };

  const confirmCreateWorkspace = async () => {
    if (!newWorkspaceName.trim()) return;

    try {
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/workspaces/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newWorkspaceName.trim() })
      });
      if (res.ok) {
        const newWs = await res.json();
        setWorkspaces(prev => [newWs, ...prev]);
        handleSelectWorkspace(newWs.id);
        setIsCreateWorkspaceModalOpen(false);
      }
    } catch (e) {
      console.error('Failed to create workspace', e);
    }
  };

  const activeWorkspace = workspaces.find(w => w.id === activeWorkspaceId);

  const handleSelectOrg = async (org: typeof organizations[0]) => {
    // If org is still provisioning, poll until it's active or failed
    if (org.status === 'provisioning') {
      setCurrentOrg(org);
      setIsOrgDropdownOpen(false);

      // Poll org status until provisioning completes
      const apiUrl = getApiUrl();
      let attempts = 0;
      const maxAttempts = 30; // 30 seconds max wait

      while (attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        attempts++;

        try {
          const res = await fetchWithAuth(`${apiUrl}/api/orgs/${org.slug}`, { credentials: 'include' });
          if (res.ok) {
            const updatedOrg: typeof organizations[0] = await res.json();
            if (updatedOrg.status === 'active') {
              setCurrentOrg(updatedOrg);
              break;
            } else if (updatedOrg.status === 'failed') {
              setCurrentOrg(updatedOrg);
              alert('组织创建失败，请重试');
              return;
            }
          }
        } catch (e) {
          console.error('Failed to poll org status', e);
        }
      }

      if (attempts >= maxAttempts) {
        alert('组织创建超时，请刷新页面重试');
      }

      // Refresh data after org change
      setSkip(0);
      setChats([]);
      setActiveWorkspaceId(null);
      setWorkspaces([]);
      return;
    }

    setCurrentOrg(org);
    setIsOrgDropdownOpen(false);
    // Refresh data after org change
    setSkip(0);
    setChats([]);
    setActiveWorkspaceId(null);
    setWorkspaces([]);
  };

  const handleCreateOrgClick = () => {
    setNewOrgName('');
    setNewOrgSlug('');
    setIsOrgDropdownOpen(false);
    setIsCreateOrgModalOpen(true);
  };

  const confirmCreateOrg = async () => {
    if (!newOrgName.trim() || !newOrgSlug.trim()) return;

    try {
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/api/orgs/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newOrgName.trim(), slug: newOrgSlug.trim().toLowerCase().replace(/\s+/g, '-') })
      });
      if (res.ok) {
        const newOrg = await res.json();
        handleSelectOrg(newOrg);
        setIsCreateOrgModalOpen(false);
      }
    } catch (e) {
      console.error('Failed to create org', e);
    }
  };

  const handleSelectChat = (id: number) => {
    router.push(`/chat?chatId=${id}`);
  };

  const handleDeleteChatClick = (e: React.MouseEvent, chatId: number) => {
    e.stopPropagation();
    setChatToDelete(chatId);
    setOpenMenuId(null);
  };

  const confirmDeleteChat = async () => {
    if (!chatToDelete) return;
    
    const chatId = chatToDelete;
    try {
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/chats/${chatId}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        setChats(prev => prev.filter(c => c.id !== chatId));
        if (activeChatId === chatId.toString()) {
          router.push('/chat?chatId=new');
        }
      }
    } catch (error) {
      console.error("Failed to delete chat:", error);
    } finally {
      setChatToDelete(null);
    }
  };

  return (
    <>
      {/* 1. Leftmost Global Sidebar (Topics) */}
      <aside className="w-[76px] bg-slate-950 flex flex-col items-center py-4 flex-shrink-0 z-20 shadow-xl">
        {/* Org Selector */}
        <div className="relative mb-4">
          <button
            onClick={() => setIsOrgDropdownOpen(!isOrgDropdownOpen)}
            className="w-11 h-11 rounded-2xl bg-indigo-600 text-white flex items-center justify-center font-bold text-xl shadow-lg shadow-indigo-500/30 hover:bg-indigo-500 transition-colors"
            title={currentOrg?.name || 'Select Org'}
          >
            {isLoadingOrgs || currentOrg?.status === 'provisioning' ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              currentOrg?.name?.substring(0, 2).toUpperCase() || 'M'
            )}
          </button>

          {isOrgDropdownOpen && (
            <div className="absolute left-full ml-2 top-0 w-48 bg-slate-800 rounded-xl shadow-xl border border-slate-700 py-1 z-50">
              <div className="px-3 py-2 text-xs text-slate-400 border-b border-slate-700">
                选择组织
              </div>
              {organizations.map(org => (
                <button
                  key={org.id}
                  onClick={() => handleSelectOrg(org)}
                  className={`w-full text-left px-3 py-2 text-sm hover:bg-slate-700 transition-colors ${
                    currentOrg?.id === org.id ? 'text-indigo-400' : 'text-white'
                  }`}
                >
                  {org.name}
                </button>
              ))}
              <div className="border-t border-slate-700 mt-1 pt-1">
                <button
                  onClick={handleCreateOrgClick}
                  className="w-full text-left px-3 py-2 text-sm text-indigo-400 hover:bg-slate-700 transition-colors flex items-center gap-2"
                >
                  <Plus className="w-3 h-3" /> 新建组织
                </button>
              </div>
            </div>
          )}
        </div>
        
        <div className="flex-1 flex flex-col gap-3 overflow-y-auto overflow-x-hidden w-full px-2 items-center">
          {workspaces.map((ws) => (
            <button 
              key={ws.id}
              onClick={() => handleSelectWorkspace(ws.id)}
              className={`w-11 h-11 rounded-2xl flex items-center justify-center font-semibold text-sm transition-all duration-200 relative group ${
                activeWorkspaceId === ws.id
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-500/40 ring-2 ring-indigo-400/30'
                  : 'bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-white'
              }`}
              title={ws.name}
            >
              <span>{ws.name.substring(0, 2).toUpperCase()}</span>
            </button>
          ))}
          
          <button 
            onClick={handleCreateWorkspaceClick}
            className="w-11 h-11 rounded-2xl border border-slate-800 bg-slate-900 text-slate-400 flex items-center justify-center hover:bg-slate-800 hover:text-white transition-colors" 
            title="新建工作区"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>

        <div className="mt-4 flex flex-col gap-4 items-center">
          <button className="w-10 h-10 rounded-full bg-slate-800 border border-slate-700 text-white flex items-center justify-center text-sm font-medium hover:bg-slate-700 transition-colors">
            {username}
          </button>
          <button 
            onClick={handleLogout}
            className="text-slate-500 hover:text-slate-300 text-xs transition-colors"
          >
            退出
          </button>
        </div>
      </aside>

      {/* 2. Inner Sidebar (Chats & Views) */}
      <aside className="w-[280px] bg-white border-r border-slate-200 flex flex-col flex-shrink-0 z-10">
        {/* Topic Header */}
        <div className="p-5 border-b border-slate-100 bg-slate-50/50 flex-shrink-0">
          <h2 className="text-lg font-bold text-slate-800 truncate">
            {activeWorkspace ? activeWorkspace.name : 'Loading...'}
          </h2>
        </div>

        <div className="flex-1 flex flex-col p-3 gap-6 overflow-hidden">
          
          {/* History Section (Chats or Morphological) */}
          <div className={`flex flex-col ${isChatsOpen ? 'flex-1 min-h-0' : 'flex-shrink-0'}`}>
            <div 
              className="flex items-center justify-between px-2 mb-2 flex-shrink-0 cursor-pointer group"
              onClick={() => setIsChatsOpen(!isChatsOpen)}
            >
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-widest group-hover:text-slate-600 transition-colors">
                {pathname === '/matrix' ? `形态分析历史 (${morphologicalHistory.length})` : pathname === '/blackboard' ? `黑板历史 (${blackboardHistory.length})` : pathname === '/research' ? `研究报告 (${researchHistory.length})` : pathname === '/memory' ? `记忆` : `对话 (${chats.length})`}
              </span>
              <ChevronDown className={`w-3 h-3 text-slate-400 transition-transform duration-200 ${isChatsOpen ? '' : '-rotate-90'}`} />
            </div>
            
            {isChatsOpen && (
              <div 
                className="flex-1 overflow-y-auto space-y-1 mt-1 pr-1 custom-scrollbar"
                onScroll={pathname !== '/matrix' && pathname !== '/blackboard' ? handleScroll : undefined}
              >
                {pathname === '/blackboard' ? (
                  <>
                    <button 
                      onClick={() => window.dispatchEvent(new CustomEvent('new-blackboard'))}
                      className={`w-full text-left px-3 py-2 mb-2 rounded-xl transition-colors flex items-center justify-center gap-2 text-sm font-medium flex-shrink-0 bg-indigo-50 border border-indigo-100 text-indigo-700 hover:bg-indigo-100 shadow-sm`}
                    >
                      <Plus className="w-4 h-4 flex-shrink-0" /> 新建黑板
                    </button>
                    <button 
                      onClick={() => router.push('/chat?chatId=new')}
                      className={`w-full text-left px-3 py-2 mb-2 rounded-xl transition-colors flex items-center justify-center gap-2 text-sm font-medium flex-shrink-0 bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-indigo-600 shadow-sm`}
                    >
                      返回对话
                    </button>
                    {isLoadingBlackboard ? (
                      <div className="flex justify-center py-4">
                        <Loader2 className="w-5 h-5 text-slate-400 animate-spin" />
                      </div>
                    ) : blackboardHistory.length === 0 ? (
                      <div className="text-center text-xs text-slate-400 py-4">暂无历史记录</div>
                    ) : (
                      blackboardHistory.map(bb => (
                        <div key={bb.id} className="relative group">
                          <button 
                            onClick={() => handleSelectBlackboard(bb.id)}
                            className={`w-full text-left px-3 py-2.5 rounded-xl transition-all duration-200 flex items-start gap-3 hover:bg-slate-50 border border-transparent`}
                          >
                            <div className="mt-0.5 flex-shrink-0 text-slate-400 group-hover:text-indigo-500">
                              <Presentation className="w-3.5 h-3.5" />
                            </div>
                            <div className="flex-1 min-w-0 pr-6">
                              <div className="text-sm font-medium truncate text-slate-700">
                                {bb.topic || '未命名'}
                              </div>
                              <div className="text-xs text-slate-400 truncate mt-0.5 flex justify-between">
                                <span>{new Date(bb.created_at).toLocaleDateString()}</span>
                                {bb.status === 'generating' && <span className="text-yellow-500">生成中...</span>}
                              </div>
                            </div>
                          </button>
                          
                          {/* Hover Menu Button */}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setOpenMenuId(openMenuId === bb.id ? null : bb.id);
                            }}
                            className={`absolute right-2 top-2.5 p-1.5 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-200/50 transition-all duration-200 ${
                              openMenuId === bb.id ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                            }`}
                          >
                            <MoreHorizontal className="w-4 h-4" />
                          </button>

                          {/* Dropdown Menu */}
                          {openMenuId === bb.id && (
                            <>
                              <div 
                                className="fixed inset-0 z-40" 
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setOpenMenuId(null);
                                }}
                              />
                              <div className="absolute right-2 top-10 w-32 bg-white rounded-lg shadow-lg border border-slate-100 py-1 z-50 animate-in fade-in zoom-in duration-200">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setChatToDelete(bb.id);
                                    setOpenMenuId(null);
                                  }}
                                  className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2 transition-colors"
                                >
                                  <Trash2 className="w-4 h-4" /> 删除黑板
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      ))
                    )}
                  </>
                ) : pathname === '/matrix' ? (
                  <>
                    <button 
                      onClick={() => window.dispatchEvent(new CustomEvent('new-morphological-analysis'))}
                      className={`w-full text-left px-3 py-2 mb-2 rounded-xl transition-colors flex items-center justify-center gap-2 text-sm font-medium flex-shrink-0 bg-indigo-50 border border-indigo-100 text-indigo-700 hover:bg-indigo-100 shadow-sm`}
                    >
                      <Plus className="w-4 h-4 flex-shrink-0" /> 新建分析
                    </button>
                    <button 
                      onClick={() => router.push('/chat?chatId=new')}
                      className={`w-full text-left px-3 py-2 mb-2 rounded-xl transition-colors flex items-center justify-center gap-2 text-sm font-medium flex-shrink-0 bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-indigo-600 shadow-sm`}
                    >
                      返回对话
                    </button>
                    {isLoadingMorphological ? (
                      <div className="flex justify-center py-4">
                        <Loader2 className="w-5 h-5 text-slate-400 animate-spin" />
                      </div>
                    ) : morphologicalHistory.length === 0 ? (
                      <div className="text-center text-xs text-slate-400 py-4">暂无历史记录</div>
                    ) : (
                      morphologicalHistory.map(analysis => (
                        <div key={analysis.id} className="relative group">
                          <button 
                            onClick={() => handleSelectMorphologicalAnalysis(analysis.id)}
                            className={`w-full text-left px-3 py-2.5 rounded-xl transition-all duration-200 flex items-start gap-3 hover:bg-slate-50 border border-transparent`}
                          >
                            <div className="mt-0.5 flex-shrink-0 text-slate-400 group-hover:text-indigo-500">
                              <Network className="w-3.5 h-3.5" />
                            </div>
                            <div className="flex-1 min-w-0 pr-6">
                              <div className="text-sm font-medium truncate text-slate-700">
                                {analysis.focus_question || '未命名分析'}
                              </div>
                              <div className="text-xs text-slate-400 truncate mt-0.5">
                                {new Date(analysis.updated_at).toLocaleDateString()}
                              </div>
                            </div>
                          </button>
                          
                          {/* Hover Menu Button */}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setOpenMenuId(openMenuId === analysis.id ? null : analysis.id);
                            }}
                            className={`absolute right-2 top-2.5 p-1.5 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-200/50 transition-all duration-200 ${
                              openMenuId === analysis.id ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                            }`}
                          >
                            <MoreHorizontal className="w-4 h-4" />
                          </button>

                          {/* Dropdown Menu */}
                          {openMenuId === analysis.id && (
                            <>
                              <div 
                                className="fixed inset-0 z-40" 
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setOpenMenuId(null);
                                }}
                              />
                              <div className="absolute right-2 top-10 w-32 bg-white rounded-lg shadow-lg border border-slate-100 py-1 z-50 animate-in fade-in zoom-in duration-200">
                                <button
                                  onClick={(e) => handleDeleteMorphologicalClick(e, analysis.id)}
                                  className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2 transition-colors"
                                >
                                  <Trash2 className="w-4 h-4" /> 删除方案
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      ))
                    )}
                  </>
                ) : pathname === '/research' ? (
                  <>
                    <button
                      onClick={() => window.dispatchEvent(new CustomEvent('new-research'))}
                      className={`w-full text-left px-3 py-2 mb-2 rounded-xl transition-colors flex items-center justify-center gap-2 text-sm font-medium flex-shrink-0 bg-indigo-50 border border-indigo-100 text-indigo-700 hover:bg-indigo-100 shadow-sm`}
                    >
                      <Plus className="w-4 h-4 flex-shrink-0" /> 新建研究
                    </button>
                    <button
                      onClick={() => router.push('/chat?chatId=new')}
                      className={`w-full text-left px-3 py-2 mb-2 rounded-xl transition-colors flex items-center justify-center gap-2 text-sm font-medium flex-shrink-0 bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-indigo-600 shadow-sm`}
                    >
                      返回对话
                    </button>
                    {isLoadingResearch ? (
                      <div className="flex justify-center py-4">
                        <Loader2 className="w-5 h-5 text-slate-400 animate-spin" />
                      </div>
                    ) : researchHistory.length === 0 ? (
                      <div className="text-center text-xs text-slate-400 py-4">暂无历史记录</div>
                    ) : (
                      researchHistory.map(report => (
                        <div key={report.id} className="relative group">
                          <button
                            onClick={() => handleSelectResearch(report.id)}
                            className={`w-full text-left px-3 py-2.5 rounded-xl transition-all duration-200 flex items-start gap-3 hover:bg-slate-50 border border-transparent`}
                          >
                            {/* Status dot */}
                            <span className={`w-2 h-2 rounded-full flex-shrink-0 mt-0.5 ${
                              report.status === 'running' ? 'bg-yellow-400 animate-pulse' :
                              report.status === 'error' ? 'bg-red-400' :
                              'bg-green-400'
                            }`} />
                            <div className="mt-0.5 flex-shrink-0 text-slate-400 group-hover:text-indigo-500">
                              <Search className="w-3.5 h-3.5" />
                            </div>
                            <div className="flex-1 min-w-0 pr-6">
                              <div className="text-sm font-medium truncate text-slate-700">
                                {report.research_topic || report.query || '未命名研究'}
                              </div>
                              <div className="text-xs text-slate-400 truncate mt-0.5 flex justify-between">
                                <span>{new Date(report.updated_at).toLocaleDateString()}</span>
                                {report.level && <span className="capitalize">{report.level}</span>}
                              </div>
                            </div>
                          </button>

                          {/* Hover Menu Button */}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setOpenMenuId(openMenuId === report.id ? null : report.id);
                            }}
                            className={`absolute right-2 top-2.5 p-1.5 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-200/50 transition-all duration-200 ${
                              openMenuId === report.id ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                            }`}
                          >
                            <MoreHorizontal className="w-4 h-4" />
                          </button>

                          {/* Dropdown Menu */}
                          {openMenuId === report.id && (
                            <>
                              <div
                                className="fixed inset-0 z-40"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setOpenMenuId(null);
                                }}
                              />
                              <div className="absolute right-2 top-10 w-32 bg-white rounded-lg shadow-lg border border-slate-100 py-1 z-50 animate-in fade-in zoom-in duration-200">
                                <button
                                  onClick={(e) => handleDeleteResearchClick(e, report.id)}
                                  className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2 transition-colors"
                                >
                                  <Trash2 className="w-4 h-4" /> 删除报告
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      ))
                    )}
                  </>
                ) : pathname === '/memory' ? (
                  <>
                    <button
                      onClick={() => router.push('/chat?chatId=new')}
                      className={`w-full text-left px-3 py-2 mb-2 rounded-xl transition-colors flex items-center justify-center gap-2 text-sm font-medium flex-shrink-0 bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-indigo-600 shadow-sm`}
                    >
                      返回对话
                    </button>
                    <div className="text-center text-xs text-slate-400 py-4">
                      记忆面板位于右侧工作区
                    </div>
                  </>
                ) : (
                  <>
                    <button 
                      onClick={handleNewChat}
                      className={`w-full text-left px-3 py-2 mb-2 rounded-xl transition-colors flex items-center gap-2 text-sm font-medium flex-shrink-0 ${
                        activeChatId === 'new'
                          ? 'bg-indigo-50 border border-indigo-100 text-indigo-700'
                          : 'hover:bg-indigo-50/50 border border-dashed border-indigo-100 text-indigo-600'
                      }`}
                    >
                      <Plus className="w-3 h-3 flex-shrink-0" /> 新建对话
                    </button>

                    {isLoadingChats && chats.length === 0 ? (
                      <div className="flex justify-center py-4">
                        <Loader2 className="w-5 h-5 text-slate-400 animate-spin" />
                      </div>
                    ) : (
                      chats.map(chat => {
                        const isActive = activeChatId === chat.id.toString();
                        return (
                          <div key={chat.id} className="relative group">
                            <button 
                              onClick={() => handleSelectChat(chat.id)}
                              className={`w-full text-left px-3 py-2.5 rounded-xl transition-all duration-200 flex items-start gap-3 ${
                                isActive 
                                  ? 'bg-indigo-50 border border-indigo-100/50' 
                                  : 'hover:bg-slate-50 border border-transparent'
                              }`}
                            >
                              <div className={`mt-0.5 flex-shrink-0 ${isActive ? 'text-indigo-500' : 'text-slate-400 group-hover:text-slate-500'}`}>
                                <MessageSquare className="w-3.5 h-3.5" />
                              </div>
                              <div className="flex-1 min-w-0 pr-6">
                                <div className={`text-sm font-medium truncate ${isActive ? 'text-indigo-700' : 'text-slate-700'}`}>
                                  {chat.title || 'New Chat'}
                                </div>
                                <div className="text-xs text-slate-400 truncate mt-0.5">
                                  {new Date(chat.created_at).toLocaleDateString()}
                                </div>
                              </div>
                            </button>
                            
                            {/* Hover Menu Button */}
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setOpenMenuId(openMenuId === chat.id ? null : chat.id);
                              }}
                              className={`absolute right-2 top-2.5 p-1.5 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-200/50 transition-all duration-200 ${
                                openMenuId === chat.id ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                              }`}
                            >
                              <MoreHorizontal className="w-4 h-4" />
                            </button>

                            {/* Dropdown Menu */}
                            {openMenuId === chat.id && (
                              <>
                                <div 
                                  className="fixed inset-0 z-40" 
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setOpenMenuId(null);
                                  }}
                                />
                                <div className="absolute right-2 top-10 w-32 bg-white rounded-lg shadow-lg border border-slate-100 py-1 z-50 animate-in fade-in zoom-in duration-200">
                                  <button
                                    onClick={(e) => handleDeleteChatClick(e, chat.id)}
                                    className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2 transition-colors"
                                  >
                                    <Trash2 className="w-4 h-4" /> 删除对话
                                  </button>
                                </div>
                              </>
                            )}
                          </div>
                        );
                      })
                    )}
                    
                    {isFetchingMore && (
                      <div className="flex justify-center py-2">
                        <Loader2 className="w-4 h-4 text-slate-400 animate-spin" />
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>

          {/* Overview */}
          <button
            onClick={() => router.push('/overview')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200 ${pathname === '/overview' ? 'bg-indigo-50 text-indigo-700 font-bold' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'}`}
          >
            <LayoutDashboard className={`w-4 h-4 flex-shrink-0 ${pathname === '/overview' ? 'text-indigo-600' : 'text-slate-400'}`} />
            <span className="font-medium">总览</span>
          </button>

          {/* Workspace Views Section */}
          <div className={`flex flex-col ${isChatsOpen ? 'flex-shrink-0 max-h-[40%]' : 'flex-1 min-h-0'}`}>
            <div 
              className="flex items-center justify-between px-2 mb-2 flex-shrink-0 cursor-pointer group"
              onClick={() => setIsViewsOpen(!isViewsOpen)}
            >
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-widest group-hover:text-slate-600 transition-colors">工作流视图</span>
              <ChevronDown className={`w-3 h-3 text-slate-400 transition-transform duration-200 ${isViewsOpen ? '' : '-rotate-90'}`} />
            </div>
            
            {isViewsOpen && (
              <div className="flex-1 overflow-y-auto space-y-1 mt-1 pr-1 custom-scrollbar">
                <button 
                  onClick={() => router.push('/matrix')}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200 ${pathname === '/matrix' ? 'bg-indigo-50 text-indigo-700 font-bold' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'}`}
                >
                  <Network className={`w-4 h-4 flex-shrink-0 ${pathname === '/matrix' ? 'text-indigo-600' : 'text-slate-400'}`} />
                  <span className="font-medium">形态分析</span>
                </button>
                
                <button
                  onClick={() => router.push('/blackboard')}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200 ${pathname === '/blackboard' ? 'bg-indigo-50 text-indigo-700 font-bold' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'}`}
                >
                  <Presentation className={`w-4 h-4 flex-shrink-0 ${pathname === '/blackboard' ? 'text-indigo-600' : 'text-slate-400'}`} />
                  <span className="font-medium">黑板讲解</span>
                </button>

                <button
                  onClick={() => router.push('/research')}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200 ${pathname === '/research' ? 'bg-indigo-50 text-indigo-700 font-bold' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'}`}
                >
                  <Search className={`w-4 h-4 flex-shrink-0 ${pathname === '/research' ? 'text-indigo-600' : 'text-slate-400'}`} />
                  <span className="font-medium">深度研究</span>
                </button>

                <button
                  onClick={() => router.push('/memory')}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200 ${pathname === '/memory' ? 'bg-indigo-50 text-indigo-700 font-bold' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'}`}
                >
                  <Brain className={`w-4 h-4 flex-shrink-0 ${pathname === '/memory' ? 'text-indigo-600' : 'text-slate-400'}`} />
                  <span className="font-medium">记忆</span>
                </button>

                <button
                  onClick={() => router.push('/mcp')}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200 ${pathname === '/mcp' ? 'bg-indigo-50 text-indigo-700 font-bold' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'}`}
                >
                  <Terminal className={`w-4 h-4 flex-shrink-0 ${pathname === '/mcp' ? 'text-indigo-600' : 'text-slate-400'}`} />
                  <span className="font-medium">MCP</span>
                </button>
              </div>
            )}
          </div>

        </div>
      </aside>

      {/* Modals */}
      {isCreateWorkspaceModalOpen && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-slate-800">新建工作区</h3>
              <button 
                onClick={() => setIsCreateWorkspaceModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6">
              <input
                type="text"
                autoFocus
                value={newWorkspaceName}
                onChange={(e) => setNewWorkspaceName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && confirmCreateWorkspace()}
                placeholder="工作区名称..."
                className="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
              />
            </div>
            <div className="px-6 py-4 bg-slate-50 flex justify-end gap-3 rounded-b-2xl">
              <button
                onClick={() => setIsCreateWorkspaceModalOpen(false)}
                className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-200 rounded-xl transition-colors"
              >
                取消
              </button>
              <button
                onClick={confirmCreateWorkspace}
                disabled={!newWorkspaceName.trim()}
                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Org Modal */}
      {isCreateOrgModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 w-96 shadow-xl">
            <h3 className="text-lg font-bold mb-4">新建组织</h3>
            <input
              type="text"
              placeholder="组织名称"
              value={newOrgName}
              onChange={(e) => setNewOrgName(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg mb-3"
            />
            <input
              type="text"
              placeholder="URL slug (如 my-org)"
              value={newOrgSlug}
              onChange={(e) => setNewOrgSlug(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg mb-4"
            />
            <div className="flex gap-3">
              <button
                onClick={() => setIsCreateOrgModalOpen(false)}
                className="flex-1 px-4 py-2 border border-slate-200 rounded-lg hover:bg-slate-50"
              >
                取消
              </button>
              <button
                onClick={confirmCreateOrg}
                className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}

      {chatToDelete !== null && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-red-600 flex items-center gap-2">
                <Trash2 className="w-5 h-5" />
                确认删除
              </h3>
              <button 
                onClick={() => setChatToDelete(null)}
                className="text-slate-400 hover:text-slate-600 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6">
              <p className="text-slate-600">确定要删除此条记录吗？此操作无法撤销。</p>
            </div>
            <div className="px-6 py-4 bg-slate-50 flex justify-end gap-3 rounded-b-2xl">
              <button
                onClick={() => setChatToDelete(null)}
                className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-200 rounded-xl transition-colors"
              >
                取消
              </button>
              <button
                onClick={pathname === '/matrix' ? confirmDeleteMorphological : pathname === '/blackboard' ? confirmDeleteBlackboard : pathname === '/research' ? confirmDeleteResearch : confirmDeleteChat}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-xl transition-colors"
              >
                删除
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
