"use client";

import React, { useState, useEffect } from 'react';
import { BookOpen, Search, Loader2, FileText, X, ChevronDown, Send, Trash2 } from 'lucide-react';
import { fetchWithAuth, getApiUrl } from '../../app/lib/api';

interface ResearchReport {
  id: number;
  query: string;
  research_topic: string;
  level: string;
  status: 'running' | 'done' | 'error';
  created_at: string;
  task_id?: string;
}

interface RAGResult {
  id: string;
  content: string;
  memory_type: string;
  similarity: number;
  source?: string;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  results?: RAGResult[];
}

export default function RAGArea() {
  const [researchReports, setResearchReports] = useState<ResearchReport[]>([]);
  const [selectedReport, setSelectedReport] = useState<ResearchReport | null>(null);
  const [isLoadingReports, setIsLoadingReports] = useState(true);
  const [isIngesting, setIsIngesting] = useState(false);
  const [isIngested, setIsIngested] = useState(false);
  const [ingestError, setIngestError] = useState<string | null>(null);

  // Query state
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<RAGResult[]>([]);
  const [isQuerying, setIsQuerying] = useState(false);
  const [queryError, setQueryError] = useState<string | null>(null);

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  // Dropdown state
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  // Workspace ID from localStorage
  const workspaceIdFromStorage = typeof window !== 'undefined'
    ? parseInt(localStorage.getItem('motifold_active_workspace_id') || '0', 10)
    : 0;
  const workspaceId = isNaN(workspaceIdFromStorage) ? 0 : workspaceIdFromStorage;

  useEffect(() => {
    loadResearchReports();
  }, []);

  // Listen for workspace changes from sidebar
  useEffect(() => {
    const handleWorkspaceChanged = (e: CustomEvent) => {
      if (e.detail?.workspaceId) {
        setSelectedReport(null);
        setIsIngested(false);
        setMessages([]);
        setResults([]);
        loadResearchReports();
      }
    };
    window.addEventListener('workspace-changed', handleWorkspaceChanged as EventListener);
    return () => {
      window.removeEventListener('workspace-changed', handleWorkspaceChanged as EventListener);
    };
  }, []);

  const loadResearchReports = async () => {
    if (!workspaceId) return;

    setIsLoadingReports(true);
    try {
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/research/history`);
      if (res.ok) {
        const data = await res.json();
        // Filter to only done reports
        const doneReports = data.filter((r: ResearchReport) => r.status === 'done');
        setResearchReports(doneReports);
      }
    } catch (err) {
      console.error('Failed to load research reports:', err);
    } finally {
      setIsLoadingReports(false);
    }
  };

  const handleIngest = async () => {
    if (!selectedReport || !workspaceId) return;

    setIsIngesting(true);
    setIngestError(null);
    try {
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/memory/${workspaceId}/rag/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report_id: selectedReport.id }),
      });

      if (res.ok) {
        setIsIngested(true);
      } else {
        const err = await res.json();
        setIngestError(err.detail || 'Failed to ingest document');
      }
    } catch (err) {
      setIngestError('Failed to ingest document');
    } finally {
      setIsIngesting(false);
    }
  };

  const handleQuery = async () => {
    if (!query.trim() || !workspaceId) return;

    setIsQuerying(true);
    setQueryError(null);

    // Add user message to chat
    const userMessage: ChatMessage = { role: 'user', content: query };
    setMessages(prev => [...prev, userMessage]);

    const queryText = query;
    setQuery('');

    try {
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/memory/${workspaceId}/rag/query?query=${encodeURIComponent(queryText)}`, {
        method: 'POST',
      });

      if (res.ok) {
        const data = await res.json();
        const assistantMessage: ChatMessage = {
          role: 'assistant',
          content: `Found ${data.results?.length || 0} relevant sections:`,
          results: data.results || [],
        };
        setMessages(prev => [...prev, assistantMessage]);
        setResults(data.results || []);
      } else {
        const err = await res.json();
        setQueryError(err.detail || 'Failed to query');
        const errorMessage: ChatMessage = {
          role: 'assistant',
          content: `Error: ${err.detail || 'Failed to query'}`,
        };
        setMessages(prev => [...prev, errorMessage]);
      }
    } catch (err) {
      setQueryError('Failed to query');
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: 'Error: Failed to query',
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsQuerying(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleQuery();
    }
  };

  const clearChat = () => {
    setMessages([]);
    setResults([]);
  };

  const selectedReportLabel = selectedReport
    ? `${selectedReport.research_topic || selectedReport.query.slice(0, 30)}...`
    : 'Select research document';

  return (
    <div className="flex flex-col h-full bg-slate-50">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-6 py-4">
        <div className="flex items-center gap-3">
          <BookOpen className="w-5 h-5 text-indigo-600" />
          <h1 className="text-lg font-semibold text-slate-800">RAG 检索</h1>
        </div>
        <p className="text-sm text-slate-500 mt-1">
          选择研究报告，使用向量检索进行问答
        </p>
      </div>

      <div className="flex-1 overflow-hidden flex">
        {/* Left Panel - Document Selection */}
        <div className="w-80 bg-white border-r border-slate-200 flex flex-col">
          <div className="p-4 border-b border-slate-100">
            <label className="block text-sm font-medium text-slate-700 mb-2">
              选择研究报告
            </label>

            {isLoadingReports ? (
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading...
              </div>
            ) : researchReports.length === 0 ? (
              <div className="text-sm text-slate-500">
                No completed research reports found.
              </div>
            ) : (
              <div className="relative">
                <button
                  onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                  className="w-full flex items-center justify-between px-3 py-2 border border-slate-200 rounded-lg text-sm text-left hover:bg-slate-50"
                >
                  <span className="truncate text-slate-700">{selectedReportLabel}</span>
                  <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${isDropdownOpen ? 'rotate-180' : ''}`} />
                </button>

                {isDropdownOpen && (
                  <div className="absolute z-10 mt-1 w-[272px] bg-white border border-slate-200 rounded-lg shadow-lg max-h-64 overflow-y-auto">
                    {researchReports.map((report) => (
                      <button
                        key={report.id}
                        onClick={() => {
                          setSelectedReport(report);
                          setIsDropdownOpen(false);
                          setIsIngested(false);
                          setMessages([]);
                          setResults([]);
                        }}
                        className={`w-full px-3 py-2 text-left text-sm hover:bg-slate-50 ${
                          selectedReport?.id === report.id ? 'bg-indigo-50 text-indigo-700' : 'text-slate-700'
                        }`}
                      >
                        <div className="font-medium truncate">
                          {report.research_topic || report.query.slice(0, 30)}
                        </div>
                        <div className="text-xs text-slate-400 mt-0.5">
                          {new Date(report.created_at).toLocaleDateString()}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Ingest Button */}
          {selectedReport && !isIngested && (
            <div className="p-4">
              <button
                onClick={handleIngest}
                disabled={isIngesting}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isIngesting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Ingesting...
                  </>
                ) : (
                  <>
                    <FileText className="w-4 h-4" />
                    Index Document for RAG
                  </>
                )}
              </button>
              {ingestError && (
                <p className="text-xs text-red-500 mt-2">{ingestError}</p>
              )}
            </div>
          )}

          {isIngested && (
            <div className="p-4">
              <div className="flex items-center gap-2 text-sm text-green-600 bg-green-50 px-3 py-2 rounded-lg">
                <div className="w-2 h-2 bg-green-500 rounded-full" />
                Document indexed
              </div>
            </div>
          )}

          {/* Selected Report Preview */}
          {selectedReport && (
            <div className="flex-1 overflow-y-auto p-4 border-t border-slate-100">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
                Document Preview
              </h3>
              <div className="text-sm text-slate-600">
                <div className="font-medium text-slate-800 mb-1">
                  {selectedReport.research_topic || 'Untitled'}
                </div>
                <div className="text-xs text-slate-400 mb-2">
                  Query: {selectedReport.query}
                </div>
                <div className="text-xs text-slate-400">
                  Level: {selectedReport.level}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Panel - Chat Interface */}
        <div className="flex-1 flex flex-col">
          {/* Chat Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && !selectedReport && (
              <div className="flex flex-col items-center justify-center h-full text-slate-400">
                <BookOpen className="w-12 h-12 mb-4 opacity-50" />
                <p className="text-sm">Select a research document to start</p>
              </div>
            )}

            {messages.length === 0 && selectedReport && !isIngested && (
              <div className="flex flex-col items-center justify-center h-full text-slate-400">
                <FileText className="w-12 h-12 mb-4 opacity-50" />
                <p className="text-sm">Index the document first to start querying</p>
              </div>
            )}

            {messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[70%] rounded-2xl px-4 py-3 ${
                    msg.role === 'user'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-white border border-slate-200 text-slate-800'
                  }`}
                >
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>

                  {/* RAG Results */}
                  {msg.results && msg.results.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {msg.results.map((result, rIdx) => (
                        <div
                          key={rIdx}
                          className="bg-slate-50 rounded-lg p-3 text-xs"
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-medium text-slate-700">
                              {result.memory_type}
                            </span>
                            <span className="text-slate-400">
                              {(result.similarity * 100).toFixed(1)}% match
                            </span>
                          </div>
                          <p className="text-slate-600 whitespace-pre-wrap">
                            {result.content}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {isQuerying && (
              <div className="flex justify-start">
                <div className="bg-white border border-slate-200 rounded-2xl px-4 py-3">
                  <div className="flex items-center gap-2 text-sm text-slate-500">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Searching...
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Input Area */}
          {selectedReport && isIngested && (
            <div className="p-4 border-t border-slate-200 bg-white">
              <div className="flex gap-2">
                {messages.length > 0 && (
                  <button
                    onClick={clearChat}
                    className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg"
                    title="Clear chat"
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                )}
                <div className="flex-1 relative">
                  <textarea
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask a question about the document..."
                    className="w-full resize-none rounded-xl border border-slate-200 px-4 py-3 pr-12 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    rows={1}
                  />
                  <button
                    onClick={handleQuery}
                    disabled={!query.trim() || isQuerying}
                    className="absolute right-2 bottom-2 p-1.5 text-indigo-600 hover:bg-indigo-50 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </div>
              </div>
              {queryError && (
                <p className="text-xs text-red-500 mt-2">{queryError}</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
