"use client";

import React, { useState, useRef, useCallback } from 'react';
import { Search, Loader2, FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { fetchWithAuth, getApiUrl } from '../../app/lib/api';

type ResearchLevel = 'standard' | 'extended' | 'manual';

interface Note {
  iteration: number;
  content: string;
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

  const stopResearch = useCallback(() => {
    if (eventSource) {
      eventSource.close();
      setEventSource(null);
    }
    setIsRunning(false);
  }, [eventSource]);

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

    try {
      const apiUrl = getApiUrl();
      const level = selectedLevel;
      const { iters, results } = LEVEL_INFO[level];
      setMaxIterations(iters);

      // Start research task
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
          // SSE data format: data: {json}
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

            case 'start':
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
              // Silent progress updates
              break;

            case 'note':
              if (eventData.content) {
                setNotes(prev => [
                  ...prev,
                  {
                    iteration: eventData.iteration ?? notes.length,
                    content: eventData.content,
                  },
                ]);
              }
              break;

            case 'done':
              if (eventData.report) {
                setFinalReport(eventData.report);
              }
              setStatus('完成');
              setProgress(1);
              setIsRunning(false);
              es.close();
              setEventSource(null);
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

          {/* Level Selector */}
          <div className="ml-auto flex items-center gap-2">
            {(['standard', 'extended', 'manual'] as ResearchLevel[]).map((level) => (
              <button
                key={level}
                onClick={() => !isRunning && setSelectedLevel(level)}
                disabled={isRunning}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  selectedLevel === level
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                } ${isRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                {LEVEL_INFO[level].label}
                <span className="ml-1 text-[10px] opacity-70">
                  ({LEVEL_INFO[level].iters}轮)
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Input Section */}
          {!finalReport && !clarifyQuestion && (
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
                    {LEVEL_INFO[selectedLevel].iters} 次迭代 · 最多 {LEVEL_INFO[selectedLevel].results} 个搜索结果
                  </div>
                  <button
                    onClick={handleStartResearch}
                    disabled={!queryInput.trim() || isRunning}
                    className={`px-5 py-2.5 rounded-xl font-medium text-sm flex items-center gap-2 transition-all shadow-sm ${
                      !queryInput.trim() || isRunning
                        ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                        : 'bg-indigo-600 hover:bg-indigo-700 text-white'
                    }`}
                  >
                    {isRunning ? (
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

          {/* Queries */}
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

          {/* Notes */}
          {notes.length > 0 && (
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

          {/* Final Report */}
          {finalReport && (
            <div className="max-w-3xl mx-auto">
              <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
                <div className="px-5 py-4 bg-indigo-50 border-b border-indigo-100 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-indigo-600" />
                  <h4 className="text-sm font-semibold text-indigo-700">最终报告</h4>
                </div>
                <div className="p-6">
                  <div className="prose prose-sm prose-slate max-w-none prose-p:leading-relaxed prose-pre:bg-slate-800 prose-pre:text-slate-100 prose-a:text-indigo-600 prose-code:text-indigo-600 prose-code:bg-indigo-50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {finalReport}
                    </ReactMarkdown>
                  </div>
                </div>
                <div className="px-5 py-4 bg-slate-50 border-t border-slate-100 flex justify-end">
                  <button
                    onClick={() => {
                      setFinalReport(null);
                      setNotes([]);
                      setQueries([]);
                      setQueryInput('');
                      setStatus('');
                      setProgress(0);
                      setCurrentIteration(0);
                    }}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
                  >
                    <Search className="w-4 h-4" />
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
