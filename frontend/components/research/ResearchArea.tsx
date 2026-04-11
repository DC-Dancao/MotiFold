"use client";

import React, { useState, useRef, useEffect } from 'react';
import { Search, Loader2, FileText, Trash2, RotateCcw, MoreHorizontal, HelpCircle, MessageSquare } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { fetchWithAuth, getApiUrl } from '../../app/lib/api';

// Deep Research confirmation loop types
type DeepResearchStatus = 'idle' | 'streaming' | 'waiting_input' | 'complete' | 'error';

interface InterruptPayload {
  question: string;
  options: [string, string, string];
  allow_manual_input: boolean;
  allow_skip: boolean;
  allow_confirm_done: boolean;
}

type ResearchLevel = 'standard' | 'extended' | 'manual';

interface Note {
  iteration: number;
  content: string;
}

interface SavedReport {
  id: number;
  query: string;
  research_topic: string;
  report: string;
  notes: Note[];
  queries: string[];
  level: ResearchLevel;
  iterations: number;
  created_at: string;
  updated_at: string;
  status?: 'running' | 'done' | 'error';
  task_id?: string;
}

const LEVEL_INFO = {
  standard: { label: '标准', iters: 3, results: 10 },
  extended: { label: '扩展', iters: 6, results: 20 },
  manual: { label: '手动', iters: 5, results: 10 },
};

export default function ResearchArea() {
  const [queryInput, setQueryInput] = useState('');
  const [selectedLevel, setSelectedLevel] = useState<ResearchLevel>('standard');
  const [isRunning, setIsRunning] = useState(false);
  const [status, setStatus] = useState<string>('');
  const [progress, setProgress] = useState(0);
  const [currentIteration, setCurrentIteration] = useState(0);
  const [maxIterations, setMaxIterations] = useState(5);
  const [notes, setNotes] = useState<Note[]>([]);
  const [queries, setQueries] = useState<string[]>([]);
  const [clarifyQuestion, setClarifyQuestion] = useState<string | null>(null);
  const [finalReport, setFinalReport] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [eventSource, setEventSource] = useState<EventSource | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Deep Research confirmation loop state
  const [deepResearchThreadId, setDeepResearchThreadId] = useState<string | null>(null);
  const [deepResearchStatus, setDeepResearchStatus] = useState<DeepResearchStatus>('idle');
  const [researchHistory, setResearchHistory] = useState<string[]>([]);
  const [currentInterrupt, setCurrentInterrupt] = useState<InterruptPayload | null>(null);
  const [manualInput, setManualInput] = useState('');
  const [deepResearchError, setDeepResearchError] = useState<string | null>(null);

  // Save/Load state
  const [currentReportId, setCurrentReportId] = useState<number | null>(null);
  const [researchTopic, setResearchTopic] = useState('');
  const [showLevelDropdown, setShowLevelDropdown] = useState(false);
  const [showDeleteMenu, setShowDeleteMenu] = useState(false);

  // Listen for events from LeftSidebar
  useEffect(() => {
    const handleLoadReport = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      loadReport(detail.id);
    };

    const handleDeletedReport = () => {
      // If current report was deleted, reset
      if (currentReportId) {
        handleResetToNew();
      }
    };

    const handleNewResearch = () => {
      handleResetToNew();
    };

    const handleGlobalNotification = (e: Event) => {
      const data = (e as CustomEvent).detail;

      // Only handle research-related notifications
      if (data.resource_type !== 'research_report') return;

      // If this notification is about the currently loaded report
      if (data.resource_id === currentReportId) {
        if (data.result === 'success') {
          // Refetch to get latest data
          loadReport(data.resource_id);
        } else if (data.result === 'error') {
          // Could show error state or update status
          setError(data.message || '研究失败');
        }
      }

      // If research completed and user is not on research tab (currentReportId is null or different)
      // The global notification toast will show, but we should also refresh history
      if (data.result === 'success' && data.resource_type === 'research_report') {
        window.dispatchEvent(new Event('refresh-history'));
      }
    };

    window.addEventListener('load-research-report', handleLoadReport);
    window.addEventListener('deleted-research-report', handleDeletedReport);
    window.addEventListener('new-research', handleNewResearch);
    window.addEventListener('global-notification', handleGlobalNotification);

    return () => {
      window.removeEventListener('load-research-report', handleLoadReport);
      window.removeEventListener('deleted-research-report', handleDeletedReport);
      window.removeEventListener('new-research', handleNewResearch);
      window.removeEventListener('global-notification', handleGlobalNotification);
    };
  }, [currentReportId]);

  // Cleanup EventSource on unmount
  useEffect(() => {
    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [eventSource]);

  const loadReport = async (id: number) => {
    try {
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/research/${id}`);
      if (res.ok) {
        const data: SavedReport = await res.json();

        // If task is still running, use SSE rejoin instead of static data
        if (data.status === 'running' && data.task_id) {
          await rejoinResearch(data.task_id, data);
          return;
        }

        setCurrentReportId(data.id);
        setQueryInput(data.query);
        setResearchTopic(data.research_topic);
        setFinalReport(data.report);
        setNotes(data.notes || []);
        setQueries(data.queries || []);
        setSelectedLevel(data.level);
        setMaxIterations(data.iterations);
        setIsRunning(false);
        setError(null);
        setClarifyQuestion(null);
      }
    } catch (error) {
      console.error("Failed to load report", error);
    }
  };

  const rejoinResearch = async (taskId: string, reportData?: SavedReport) => {
    setIsRunning(true);
    setStatus('重新连接中...');
    setError(null);

    // Pre-populate from DB record if available
    if (reportData) {
      setQueryInput(reportData.query);
      setResearchTopic(reportData.research_topic || '');
      setNotes(reportData.notes || []);
      setQueries(reportData.queries || []);
      setSelectedLevel(reportData.level);
      setMaxIterations(reportData.iterations);
    }

    // Fetch persisted state from Redis
    const apiUrl = getApiUrl();
    try {
      const stateRes = await fetchWithAuth(`${apiUrl}/research/${taskId}/state`);
      if (stateRes.ok) {
        const state = await stateRes.json();
        if (state.notes) setNotes(state.notes.map((n: string, i: number) => ({ iteration: i, content: n })));
        if (state.queries) setQueries(state.queries);
        if (state.research_topic) setResearchTopic(state.research_topic);
        if (state.message) setStatus(state.message);
        if (state.progress) setProgress(state.progress);
      }
    } catch (e) {
      console.warn("Could not fetch persisted state, using defaults");
    }

    // Connect to SSE stream
    const streamUrl = `${apiUrl}/research/${taskId}/stream`;
    const es = new EventSource(streamUrl, { withCredentials: true });
    setEventSource(es);

    es.onmessage = (event) => {
      if (event.data === '[DONE]') {
        es.close();
        setEventSource(null);
        setIsRunning(false);
        return;
      }

      try {
        let raw = event.data;
        if (raw.startsWith('"') && raw.endsWith('"')) raw = JSON.parse(raw);
        const data = typeof raw === 'string' ? JSON.parse(raw) : raw;

        const eventType = data.type || data.event || '';

        // Handle rejoin event — merge persisted state
        if (eventType === 'rejoin') {
          if (data.notes) setNotes(data.notes.map((n: string, i: number) => ({ iteration: i, content: n })));
          if (data.queries) setQueries(data.queries);
          if (data.research_topic) setResearchTopic(data.research_topic);
          if (data.message) setStatus(data.message);
          if (data.progress) setProgress(data.progress);
          return;
        }

        if (eventType === 'status') {
          if (data.message) setStatus(data.message);
          if (data.iteration !== undefined) {
            setCurrentIteration(data.iteration + 1);
            setProgress(((data.iteration + 1) / maxIterations));
          }
        } else if (eventType === 'done') {
          if (data.report) setFinalReport(data.report);
          if (data.report_id) setCurrentReportId(data.report_id);
          setStatus('完成');
          setProgress(1);
          setIsRunning(false);
          es.close();
          setEventSource(null);
          window.dispatchEvent(new Event('refresh-history'));
        } else if (eventType === 'error') {
          setError(data.message || '研究过程中发生错误');
          setStatus('错误');
          setIsRunning(false);
          es.close();
          setEventSource(null);
        }
      } catch (e) {
        console.warn('Failed to parse SSE event:', e);
      }
    };

    es.onerror = () => {
      setError('SSE 连接错误');
      setIsRunning(false);
      es.close();
      setEventSource(null);
    };
  };

  const handleDelete = async () => {
    if (!currentReportId) return;
    try {
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/research/${currentReportId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        window.dispatchEvent(new CustomEvent('deleted-research-report', { detail: { id: currentReportId } }));
        handleResetToNew();
      }
    } catch (error) {
      console.error("Failed to delete report", error);
    }
  };

  const handleResetToNew = () => {
    if (eventSource) {
      eventSource.close();
      setEventSource(null);
    }
    setCurrentReportId(null);
    setQueryInput('');
    setResearchTopic('');
    setFinalReport(null);
    setNotes([]);
    setQueries([]);
    setClarifyQuestion(null);
    setError(null);
    setStatus('');
    setShowDeleteMenu(false);
    setShowLevelDropdown(false);
    setProgress(0);
    setCurrentIteration(0);
    // Reset deep research state
    setDeepResearchThreadId(null);
    setDeepResearchStatus('idle');
    setResearchHistory([]);
    setCurrentInterrupt(null);
    setManualInput('');
    setDeepResearchError(null);
  };

  // Auto-resize textarea
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setQueryInput(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  };

  const handleStartResearch = async () => {
    if (!queryInput.trim() || isRunning) return;

    // Reset state
    setIsRunning(true);
    setStatus('starting');
    setProgress(0);
    setCurrentIteration(0);
    setNotes([]);
    setQueries([]);
    setClarifyQuestion(null);
    setFinalReport(null);
    setError(null);
    setResearchTopic('');

    try {
      const apiUrl = getApiUrl();
      const level = selectedLevel;
      const { iters, results } = LEVEL_INFO[level];
      setMaxIterations(iters);

      const res = await fetchWithAuth(`${apiUrl}/research/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: queryInput.trim(),
          level,
          max_iterations: iters,
          max_results: results,
        }),
      });

      if (!res.ok) {
        throw new Error(`Failed to start research: ${res.status}`);
      }

      const taskData = await res.json();
      const taskId = taskData.task_id || '';

      const streamUrl = `${apiUrl}/research/${taskId}/stream`;
      const es = new EventSource(streamUrl, { withCredentials: true });
      setEventSource(es);

      es.onmessage = (event) => {
        if (event.data === '[DONE]') {
          es.close();
          setEventSource(null);
          setIsRunning(false);
          return;
        }

        try {
          let raw = event.data;
          if (raw.startsWith('"') && raw.endsWith('"')) {
            raw = JSON.parse(raw);
          }
          const data = typeof raw === 'string' ? JSON.parse(raw) : raw;
          const eventData = data;

          const eventType = eventData.type || eventData.event || '';

          switch (eventType) {
            case 'clarify':
              setClarifyQuestion(eventData.question || '需要澄清您的问题');
              setStatus('clarifying');
              setIsRunning(false);
              es.close();
              setEventSource(null);
              break;

            case 'status':
              if (eventData.message) {
                setStatus(eventData.message);
              }
              if (eventData.event === 'planning') {
                setStatus('规划搜索查询...');
              } else if (eventData.event === 'planning_done') {
                setStatus('查询规划完成');
                if (eventData.queries) {
                  setQueries(eventData.queries as string[]);
                }
              } else if (eventData.event === 'searching') {
                setStatus(`搜索中 (迭代 ${(eventData.iteration ?? 0) + 1}/${maxIterations})`);
                setCurrentIteration((eventData.iteration ?? 0) + 1);
                setProgress(((eventData.iteration ?? 0) + 1) / maxIterations);
              } else if (eventData.event === 'search_done') {
                setStatus(`搜索完成 (迭代 ${(eventData.iteration ?? 0) + 1})`);
              } else if (eventData.event === 'synthesizing') {
                setStatus(`综合分析中 (迭代 ${(eventData.iteration ?? 0) + 1}/${maxIterations})`);
              } else if (eventData.event === 'reporting') {
                setStatus('生成最终报告...');
              } else if (eventData.event === 'verified') {
                setStatus('已确认，开始研究');
              }
              break;

            case 'search_progress':
              break;

            case 'note':
              if (eventData.content) {
                setNotes(prev => [
                  ...prev,
                  {
                    iteration: eventData.iteration ?? prev.length,
                    content: eventData.content,
                  },
                ]);
              }
              break;

            case 'done':
              if (eventData.report) {
                setFinalReport(eventData.report);
              }
              if (eventData.report_id) {
                setCurrentReportId(eventData.report_id);
              }
              setStatus('完成');
              setProgress(1);
              setIsRunning(false);
              es.close();
              setEventSource(null);
              // Refresh history to show new saved report
              window.dispatchEvent(new Event('refresh-history'));
              break;

            case 'error':
              setError(eventData.message || '研究过程中发生错误');
              setStatus('错误');
              setIsRunning(false);
              es.close();
              setEventSource(null);
              break;

            default:
              if (eventData.message && !eventType) {
                setStatus(eventData.message);
              }
          }
        } catch (e) {
          console.warn('Failed to parse SSE event:', e);
        }
      };

      es.onerror = () => {
        setError('SSE 连接错误');
        setIsRunning(false);
        es.close();
        setEventSource(null);
      };

    } catch (e) {
      console.error('Failed to start research:', e);
      setError(`启动研究失败: ${e instanceof Error ? e.message : String(e)}`);
      setIsRunning(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleStartResearch();
    }
  };

  // Deep Research confirmation loop: connect to SSE stream
  const connectDeepResearchSSE = (threadId: string) => {
    const apiUrl = getApiUrl();
    const streamUrl = `${apiUrl}/research/stream/${threadId}`;
    const es = new EventSource(streamUrl, { withCredentials: true });

    es.onmessage = (event) => {
      try {
        let raw = event.data;
        if (raw.startsWith('"') && raw.endsWith('"')) raw = JSON.parse(raw);
        const data = typeof raw === 'string' ? JSON.parse(raw) : raw;
        const eventType = data.type || data.event || '';
        const eventData = data.data || data;

        switch (eventType) {
          case 'research_update':
            if (eventData.content) {
              setResearchHistory(prev => [...prev, eventData.content]);
            }
            break;

          case 'interrupt':
            setCurrentInterrupt({
              question: eventData.question || 'What would you like to explore further?',
              options: eventData.options || ['', '', ''],
              allow_manual_input: eventData.allow_manual_input ?? true,
              allow_skip: eventData.allow_skip ?? true,
              allow_confirm_done: eventData.allow_confirm_done ?? true,
            });
            setDeepResearchStatus('waiting_input');
            es.close();
            break;

          case 'complete':
            if (eventData.final_report) {
              setResearchHistory(prev => [...prev, '\n---\n# Final Report\n\n' + eventData.final_report]);
            }
            setDeepResearchStatus('complete');
            es.close();
            window.dispatchEvent(new Event('refresh-history'));
            break;

          case 'error':
            setDeepResearchError(eventData.message || 'Research error occurred');
            setDeepResearchStatus('error');
            es.close();
            break;

          default:
            if (eventData.content) {
              setResearchHistory(prev => [...prev, eventData.content]);
            }
        }
      } catch (e) {
        console.warn('Failed to parse SSE event:', e);
      }
    };

    es.onerror = () => {
      setDeepResearchError('SSE connection error');
      setDeepResearchStatus('error');
      es.close();
    };

    return es;
  };

  // Deep Research: start new research session
  const handleStartDeepResearch = async () => {
    if (!queryInput.trim() || deepResearchStatus === 'streaming') return;

    // Reset deep research state
    setDeepResearchThreadId(null);
    setDeepResearchStatus('streaming');
    setResearchHistory([]);
    setCurrentInterrupt(null);
    setManualInput('');
    setDeepResearchError(null);

    try {
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/research/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: queryInput.trim() }),
      });

      if (!res.ok) {
        throw new Error(`Failed to start research: ${res.status}`);
      }

      const data = await res.json();
      const threadId = data.thread_id;
      setDeepResearchThreadId(threadId);
      connectDeepResearchSSE(threadId);
    } catch (e) {
      console.error('Failed to start deep research:', e);
      setDeepResearchError(`启动研究失败: ${e instanceof Error ? e.message : String(e)}`);
      setDeepResearchStatus('error');
    }
  };

  // Deep Research: send resume action
  const handleDeepResearchResume = async (action: string) => {
    if (!deepResearchThreadId) return;

    setDeepResearchStatus('streaming');
    setCurrentInterrupt(null);
    setManualInput('');

    try {
      const apiUrl = getApiUrl();
      let body: Record<string, unknown> = { action };

      // Handle manual input case
      if (action.startsWith('manual:')) {
        body = { action: { type: 'manual', text: action.replace('manual:', '') } };
      }

      await fetchWithAuth(`${apiUrl}/research/resume/${deepResearchThreadId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      // Reconnect to SSE after sending resume
      connectDeepResearchSSE(deepResearchThreadId);
    } catch (e) {
      console.error('Failed to resume research:', e);
      setDeepResearchError(`Resume failed: ${e instanceof Error ? e.message : String(e)}`);
      setDeepResearchStatus('error');
    }
  };

  // Deep Research: option click handlers
  const handleOptionClick = (option: string) => {
    handleDeepResearchResume(option);
  };

  const handleSkipClick = () => {
    handleDeepResearchResume('skip');
  };

  const handleConfirmDoneClick = () => {
    handleDeepResearchResume('confirm_done');
  };

  const handleManualInputSubmit = () => {
    if (manualInput.trim()) {
      handleDeepResearchResume(`manual:${manualInput.trim()}`);
    }
  };

  // Determine current view mode
  const viewMode = finalReport ? 'result' : (isRunning || clarifyQuestion || error) ? 'running' : 'input';

  return (
    <main className="flex-1 flex flex-col bg-white min-w-0 relative">
      {/* Background Pattern */}
      <div
        className="absolute inset-0 z-0 opacity-[0.02] pointer-events-none"
        style={{ backgroundImage: 'radial-gradient(#000 1px, transparent 1px)', backgroundSize: '20px 20px' }}
      />

      <div className="relative z-10 flex-1 flex flex-col h-full">
        {/* Header */}
        <div className="h-16 border-b border-slate-100 flex items-center px-6 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center">
              <Search className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-slate-800">深度研究</h3>
              <p className="text-xs text-slate-400">Deep Research · AI 驱动的深度调研</p>
            </div>
          </div>

          {/* Level Selector - Dropdown in input view, static when running */}
          <div className="ml-auto flex items-center gap-2">
            {viewMode === 'input' && deepResearchStatus === 'idle' ? (
              <div className="relative">
                <button
                  onClick={() => setShowLevelDropdown(!showLevelDropdown)}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-600 text-white shadow-sm flex items-center gap-2"
                >
                  {LEVEL_INFO[selectedLevel].label} ({LEVEL_INFO[selectedLevel].iters}轮)
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {showLevelDropdown && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setShowLevelDropdown(false)} />
                    <div className="absolute right-0 top-full mt-1 w-40 bg-white rounded-lg shadow-lg border border-slate-100 py-1 z-50">
                      {(['standard', 'extended', 'manual'] as ResearchLevel[]).map((level) => (
                        <button
                          key={level}
                          onClick={() => {
                            setSelectedLevel(level);
                            setShowLevelDropdown(false);
                          }}
                          className={`w-full text-left px-3 py-2 text-xs hover:bg-slate-50 flex items-center justify-between ${
                            selectedLevel === level ? 'text-indigo-600 font-medium' : 'text-slate-600'
                          }`}
                        >
                          <span>{LEVEL_INFO[level].label}</span>
                          <span className="text-slate-400">{LEVEL_INFO[level].iters}轮</span>
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            ) : deepResearchStatus !== 'idle' ? (
              <div className="px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-100 text-amber-700">
                深度研究模式
              </div>
            ) : (
              <div className="px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-100 text-indigo-700">
                {LEVEL_INFO[selectedLevel].label} ({LEVEL_INFO[selectedLevel].iters}轮)
              </div>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Input Section */}
          {viewMode === 'input' && deepResearchStatus === 'idle' && (
            <div className="max-w-3xl mx-auto">
              <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
                <div className="p-5">
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    研究主题
                  </label>
                  <textarea
                    ref={textareaRef}
                    value={queryInput}
                    onChange={handleInputChange}
                    onKeyDown={handleKeyDown}
                    placeholder="输入你想深入研究的主题，例如：AI Agent 在软件开发中的最新进展和面临的挑战"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 pr-14 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 resize-none min-h-[100px] custom-scrollbar transition-all text-slate-700 text-sm"
                    disabled={isRunning}
                  />
                </div>
                <div className="px-5 py-4 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
                  <div className="text-xs text-slate-400">
                    输入研究主题，AI 将深度调研并询问跟进问题
                  </div>
                  <button
                    onClick={handleStartDeepResearch}
                    disabled={!queryInput.trim() || deepResearchStatus === 'streaming'}
                    className={`px-5 py-2.5 rounded-xl font-medium text-sm flex items-center gap-2 transition-all shadow-sm ${
                      !queryInput.trim() || deepResearchStatus === 'streaming'
                        ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                        : 'bg-indigo-600 hover:bg-indigo-700 text-white'
                    }`}
                  >
                    {deepResearchStatus === 'streaming' ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        研究中...
                      </>
                    ) : (
                      <>
                        <Search className="w-4 h-4" />
                        开始研究
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Clarify Question */}
          {clarifyQuestion && (
            <div className="max-w-3xl mx-auto">
              <div className="bg-amber-50 border border-amber-200 rounded-2xl p-6 text-center">
                <div className="w-12 h-12 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Search className="w-6 h-6 text-amber-600" />
                </div>
                <h3 className="text-lg font-semibold text-amber-800 mb-2">需要澄清</h3>
                <p className="text-amber-700 mb-4">{clarifyQuestion}</p>
                <button
                  onClick={() => {
                    setClarifyQuestion(null);
                    setQueryInput('');
                    setStatus('');
                  }}
                  className="px-4 py-2 bg-amber-200 hover:bg-amber-300 text-amber-800 rounded-lg text-sm font-medium transition-colors"
                >
                  重新输入
                </button>
              </div>
            </div>
          )}

          {/* Progress */}
          {isRunning && (
            <div className="max-w-3xl mx-auto">
              <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-medium text-slate-700 flex items-center gap-2">
                    {isRunning && <Loader2 className="w-4 h-4 animate-spin text-indigo-500" />}
                    {status || '初始化中...'}
                  </span>
                  <span className="text-xs text-slate-400">
                    {currentIteration} / {maxIterations}
                  </span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded-full transition-all duration-500 ease-out"
                    style={{ width: `${Math.max(progress * 100, 5)}%` }}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="max-w-3xl mx-auto">
              <div className="bg-red-50 border border-red-200 rounded-2xl p-5 text-red-700">
                <p className="font-medium">{error}</p>
                <button
                  onClick={() => {
                    setError(null);
                    setStatus('');
                    setIsRunning(false);
                  }}
                  className="mt-3 px-4 py-2 bg-red-100 hover:bg-red-200 rounded-lg text-sm font-medium transition-colors"
                >
                  重试
                </button>
              </div>
            </div>
          )}

          {/* Running: show notes and queries in real-time */}
          {(isRunning || notes.length > 0) && (
            <div className="max-w-3xl mx-auto">
              <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
                <h4 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-indigo-500" />
                  研究笔记 ({notes.length})
                </h4>
                <div className="space-y-3">
                  {notes.map((note, i) => (
                    <div
                      key={i}
                      className="border-l-2 border-indigo-200 pl-4 py-2 bg-slate-50 rounded-r-lg"
                    >
                      <div className="text-xs text-indigo-500 font-medium mb-1">
                        迭代 {note.iteration}
                      </div>
                      <p className="text-sm text-slate-700 leading-relaxed">
                        {note.content}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Queries during/after research */}
          {queries.length > 0 && (
            <div className="max-w-3xl mx-auto">
              <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
                <h4 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                  <Search className="w-4 h-4 text-indigo-500" />
                  搜索查询 ({queries.length})
                </h4>
                <div className="flex flex-wrap gap-2">
                  {queries.map((q, i) => (
                    <span
                      key={i}
                      className="px-3 py-1.5 bg-slate-100 text-slate-600 rounded-lg text-xs"
                    >
                      {q}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Deep Research Confirmation Loop UI */}
          {deepResearchStatus !== 'idle' && (
            <div className="max-w-3xl mx-auto space-y-4">
              {/* Deep Research Header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${deepResearchStatus === 'streaming' ? 'bg-indigo-500 animate-pulse' : deepResearchStatus === 'waiting_input' ? 'bg-amber-500' : deepResearchStatus === 'complete' ? 'bg-green-500' : 'bg-red-500'}`} />
                  <span className="text-sm font-medium text-slate-600">
                    {deepResearchStatus === 'streaming' && '深度研究中...'}
                    {deepResearchStatus === 'waiting_input' && '等待您的选择'}
                    {deepResearchStatus === 'complete' && '研究完成'}
                    {deepResearchStatus === 'error' && '研究错误'}
                  </span>
                </div>
                {deepResearchStatus !== 'complete' && (
                  <button
                    onClick={() => {
                      setDeepResearchThreadId(null);
                      setDeepResearchStatus('idle');
                      setResearchHistory([]);
                      setCurrentInterrupt(null);
                      setManualInput('');
                      setDeepResearchError(null);
                      handleResetToNew();
                    }}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-100 text-slate-600 hover:bg-slate-200 transition-colors"
                  >
                    停止研究
                  </button>
                )}
              </div>

              {/* Deep Research Error */}
              {deepResearchError && (
                <div className="bg-red-50 border border-red-200 rounded-2xl p-4 text-red-700">
                  <p className="text-sm font-medium">{deepResearchError}</p>
                  <button
                    onClick={() => {
                      setDeepResearchError(null);
                      setDeepResearchStatus('idle');
                    }}
                    className="mt-2 px-3 py-1.5 bg-red-100 hover:bg-red-200 rounded-lg text-xs font-medium transition-colors"
                  >
                    关闭
                  </button>
                </div>
              )}

              {/* Deep Research History */}
              {researchHistory.length > 0 && (
                <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
                  <h4 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                    <MessageSquare className="w-4 h-4 text-indigo-500" />
                    研究进展
                  </h4>
                  <div className="space-y-3 max-h-[400px] overflow-y-auto">
                    {researchHistory.map((content, i) => (
                      <div
                        key={i}
                        className="border-l-2 border-indigo-200 pl-4 py-2 bg-slate-50 rounded-r-lg"
                      >
                        <div className="text-xs text-indigo-500 font-medium mb-1">
                          更新 {i + 1}
                        </div>
                        <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
                          {content}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Interrupt Options Panel */}
              {currentInterrupt && deepResearchStatus === 'waiting_input' && (
                <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5 space-y-4">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-8 h-8 bg-amber-100 rounded-full flex items-center justify-center">
                      <HelpCircle className="w-4 h-4 text-amber-600" />
                    </div>
                    <h3 className="text-sm font-semibold text-amber-800">深度研究问题</h3>
                  </div>

                  <p className="text-amber-700 text-sm">{currentInterrupt.question}</p>

                  {/* Options */}
                  <div className="space-y-2">
                    {currentInterrupt.options.map((option, index) => (
                      <button
                        key={index}
                        onClick={() => handleOptionClick(`option_${index + 1}`)}
                        className="w-full text-left px-4 py-3 bg-white border border-amber-200 rounded-xl hover:bg-amber-100 hover:border-amber-300 transition-colors text-sm text-slate-700"
                      >
                        <span className="font-medium text-amber-600 mr-2">[{index + 1}]</span>
                        {option}
                      </button>
                    ))}
                  </div>

                  {/* Manual Input */}
                  {currentInterrupt.allow_manual_input && (
                    <div className="space-y-2">
                      <textarea
                        value={manualInput}
                        onChange={(e) => setManualInput(e.target.value)}
                        placeholder="或者输入您自己的想法..."
                        className="w-full px-4 py-3 bg-white border border-amber-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 text-sm text-slate-700 resize-none min-h-[80px] custom-scrollbar"
                      />
                      <button
                        onClick={handleManualInputSubmit}
                        disabled={!manualInput.trim()}
                        className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        提交手动输入
                      </button>
                    </div>
                  )}

                  {/* Skip and Confirm Done */}
                  <div className="flex gap-2 pt-2">
                    {currentInterrupt.allow_skip && (
                      <button
                        onClick={handleSkipClick}
                        className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-xl text-sm font-medium transition-colors"
                      >
                        跳过
                      </button>
                    )}
                    {currentInterrupt.allow_confirm_done && (
                      <button
                        onClick={handleConfirmDoneClick}
                        className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-medium transition-colors"
                      >
                        确认完成
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Final Report */}
          {finalReport && viewMode === 'result' && (
            <div className="max-w-3xl mx-auto">
              <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
                {/* Report Header */}
                <div className="px-5 py-4 bg-indigo-50 border-b border-indigo-100 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-indigo-600" />
                    <h4 className="text-sm font-semibold text-indigo-700">
                      {researchTopic || '研究报告'}
                    </h4>
                  </div>
                  <div className="flex items-center gap-2">
                    {/* Delete Dropdown */}
                    {currentReportId && (
                      <div className="relative">
                        <button
                          onClick={() => setShowDeleteMenu(!showDeleteMenu)}
                          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors flex items-center gap-1.5"
                        >
                          <MoreHorizontal className="w-3.5 h-3.5" />
                        </button>
                        {showDeleteMenu && (
                          <>
                            <div className="fixed inset-0 z-40" onClick={() => setShowDeleteMenu(false)} />
                            <div className="absolute right-0 top-full mt-1 w-32 bg-white rounded-lg shadow-lg border border-slate-100 py-1 z-50">
                              <button
                                onClick={() => {
                                  handleDelete();
                                  setShowDeleteMenu(false);
                                }}
                                className="w-full text-left px-3 py-2 text-xs text-red-600 hover:bg-red-50 flex items-center gap-2 transition-colors"
                              >
                                <Trash2 className="w-4 h-4" /> 删除报告
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Report Content */}
                <div className="p-6">
                  <div className="prose prose-sm prose-slate max-w-none prose-p:leading-relaxed prose-pre:bg-slate-800 prose-pre:text-slate-100 prose-a:text-indigo-600 prose-code:text-indigo-600 prose-code:bg-indigo-50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {finalReport}
                    </ReactMarkdown>
                  </div>
                </div>

                {/* Report Footer */}
                <div className="px-5 py-4 bg-slate-50 border-t border-slate-100 flex justify-between items-center">
                  <div className="text-xs text-slate-400">
                    {LEVEL_INFO[selectedLevel].label} · {maxIterations} 次迭代 · {new Date().toLocaleDateString()}
                  </div>
                  <button
                    onClick={handleResetToNew}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
                  >
                    <RotateCcw className="w-4 h-4" />
                    新研究
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
