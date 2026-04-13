"use client";

import React, { useEffect, useState, useRef } from 'react';
import { fetchWithAuth, getApiUrl } from '../../app/lib/api';
import { Loader2, ChevronLeft, ChevronRight, Presentation, Send } from 'lucide-react';

interface Block {
  id: string;
  type: string;
  content: string;
  x: number;
  y: number;
  rot: number;
  highlight: boolean;
}

interface Step {
  title: string;
  note: string;
  boardState: Block[];
}

export default function BlackboardArea() {
  const [activeBlackboardId, setActiveBlackboardId] = useState<number | 'new'>('new');
  const [topicInput, setTopicInput] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [status, setStatus] = useState<string>('pending');
  
  const [stepsData, setStepsData] = useState<Step[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [topicInput]);

  useEffect(() => {
    const handleNew = () => setActiveBlackboardId('new');
    const handleLoad = (e: Event) => {
      const customEvent = e as CustomEvent<{ id: number }>;
      setActiveBlackboardId(customEvent.detail.id);
    };
    const handleDelete = (e: Event) => {
      const customEvent = e as CustomEvent<{ id: number }>;
      if (activeBlackboardId === customEvent.detail.id) {
        setActiveBlackboardId('new');
      }
    };

    window.addEventListener('new-blackboard', handleNew);
    window.addEventListener('load-blackboard', handleLoad);
    window.addEventListener('deleted-blackboard', handleDelete);

    return () => {
      window.removeEventListener('new-blackboard', handleNew);
      window.removeEventListener('load-blackboard', handleLoad);
      window.removeEventListener('deleted-blackboard', handleDelete);
    };
  }, [activeBlackboardId]);

  // Listen for SSE notifications
  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    const connect = async () => {
      try {
        const response = await fetch('/notifications/stream', {
          credentials: 'include',
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (!cancelled) {
          const { done, value } = await reader.read();
          if (done) {
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const events = buffer.split('\n\n');
          buffer = events.pop() || '';

          for (const event of events) {
            const dataLine = event
              .split('\n')
              .find(line => line.startsWith('data:'));

            if (!dataLine) {
              continue;
            }

            try {
              const data = JSON.parse(dataLine.slice(5).trim());
              if (data.type === 'blackboard_updated' && activeBlackboardId === data.blackboard_id) {
                if ((data.status === 'completed' || data.status === 'failed') && typeof activeBlackboardId === 'number') {
                  fetchBlackboardData(activeBlackboardId);
                }
              }
            } catch (error) {
              console.warn('Failed to parse blackboard notification', error);
            }
          }
        }
      } catch (error) {
        if (!cancelled) {
          console.error('Blackboard notification stream failed', error);
        }
      }
    };

    connect();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [activeBlackboardId]);

  const fetchBlackboardData = async (id: number) => {
    try {
      setIsLoading(true);
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/blackboard/${id}`);
      if (res.ok) {
        const data = await res.json();
        setStatus(data.status);
        if (data.status === 'completed') {
          const parsedContent = JSON.parse(data.content_json);
          setStepsData(parsedContent);
          setCurrentIndex(0);
        } else {
          setStepsData([]);
        }
      }
    } catch (error) {
      console.error("Failed to fetch blackboard data", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (activeBlackboardId !== 'new') {
      fetchBlackboardData(activeBlackboardId);
    } else {
      setStepsData([]);
      setStatus('pending');
      setTopicInput('');
    }
  }, [activeBlackboardId]);

  const handleSubmit = async () => {
    if (!topicInput.trim() || isSubmitting) return;

    try {
      setIsSubmitting(true);
      const apiUrl = getApiUrl();
      const wsId = localStorage.getItem('motifold_active_workspace_id');
      
      const res = await fetchWithAuth(`${apiUrl}/blackboard/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          topic: topicInput.trim(),
          workspace_id: wsId ? parseInt(wsId) : null
        })
      });

      if (res.ok) {
        const data = await res.json();
        setActiveBlackboardId(data.id);
        window.dispatchEvent(new Event('refresh-history'));
      }
    } catch (error) {
      console.error("Failed to create blackboard task", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDownInput = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handlePrev = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  };

  const handleNext = () => {
    if (currentIndex < stepsData.length - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  };

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') handleNext();
      if (e.key === 'ArrowLeft') handlePrev();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentIndex, stepsData.length]);

  if (isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-slate-50 h-full">
        <Loader2 className="w-8 h-8 text-indigo-500 animate-spin mb-4" />
        <p className="text-slate-500 font-medium">正在加载数据...</p>
      </div>
    );
  }

  if (activeBlackboardId === 'new') {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-slate-50 h-full p-8">
        <div className="max-w-2xl w-full bg-white rounded-3xl shadow-sm border border-slate-100 p-10 flex flex-col items-center">
          <div className="w-16 h-16 bg-indigo-50 rounded-2xl flex items-center justify-center mb-6">
            <Presentation className="w-8 h-8 text-indigo-600" />
          </div>
          <h2 className="text-2xl font-bold text-slate-800 mb-2">AI 黑板讲解</h2>
          <p className="text-slate-500 text-center mb-8">
            输入你想了解的概念、题目或流程，AI 老师将为你生成逐步的黑板板书讲解。
          </p>
          
          <div className="w-full relative">
            <textarea
              ref={textareaRef}
              value={topicInput}
              onChange={(e) => setTopicInput(e.target.value)}
              onKeyDown={handleKeyDownInput}
              placeholder="例如：解释一下什么是鱼香肉丝的做法，或者讲解一下快速排序算法..."
              className="w-full bg-slate-50 border border-slate-200 rounded-2xl px-5 py-4 pr-14 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 resize-none min-h-[120px] custom-scrollbar transition-all text-slate-700"
              disabled={isSubmitting}
            />
            <button
              onClick={handleSubmit}
              disabled={!topicInput.trim() || isSubmitting}
              className="absolute right-3 bottom-3 p-2 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
            >
              {isSubmitting ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (status === 'generating') {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-slate-50 h-full p-8">
        <div className="max-w-md w-full bg-white rounded-3xl shadow-sm border border-slate-100 p-10 flex flex-col items-center text-center">
          <div className="relative mb-8">
            <div className="absolute inset-0 bg-indigo-100 rounded-full animate-ping opacity-75"></div>
            <div className="relative w-16 h-16 bg-indigo-50 rounded-full flex items-center justify-center border-2 border-indigo-100">
              <Presentation className="w-8 h-8 text-indigo-600 animate-pulse" />
            </div>
          </div>
          <h2 className="text-xl font-bold text-slate-800 mb-3">AI 老师正在备课...</h2>
          <p className="text-slate-500 text-sm leading-relaxed">
            这可能需要 20-40 秒的时间。AI 正在拆解步骤，并为你准备精美的黑板板书和讲解讲义。
          </p>
        </div>
      </div>
    );
  }

  if (status === 'failed') {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-50 h-full text-red-500 font-medium">
        生成失败，请重试。
      </div>
    );
  }

  if (stepsData.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-50 h-full text-slate-500">
        暂无数据
      </div>
    );
  }

  const currentStep = stepsData[currentIndex];

  return (
    <div className="flex-1 flex overflow-hidden h-full">
      {/* 左侧：Teacher's Note (讲解区) */}
      <aside className="w-[360px] bg-white border-r border-slate-200 p-8 flex flex-col relative shadow-[4px_0_24px_rgba(0,0,0,0.02)] z-10 flex-shrink-0">
        <div className="mb-6 inline-flex items-center px-3 py-1.5 rounded-full bg-indigo-50 text-indigo-600 text-xs font-semibold border border-indigo-100 self-start">
          <Presentation className="w-3.5 h-3.5 mr-1.5" />
          AI 老师讲解
        </div>
        
        <h2 
          className="text-2xl font-bold text-slate-800 mb-4 transition-all duration-300"
          key={`title-${currentIndex}`} // Trigger re-render animation
          style={{ animation: 'fadeIn 0.3s ease-in-out' }}
        >
          {currentStep.title}
        </h2>
        
        <div className="relative flex-1 overflow-y-auto pr-2 custom-scrollbar">
          <div className="bg-slate-50 rounded-2xl rounded-tl-none p-5 border border-slate-100 shadow-sm relative text-slate-600 leading-relaxed">
            <p 
              key={`note-${currentIndex}`} // Trigger re-render animation
              style={{ animation: 'fadeIn 0.3s ease-in-out' }}
            >
              {currentStep.note}
            </p>
          </div>
        </div>

        {/* 控制器 */}
        <div className="mt-6 pt-5 border-t border-slate-100 flex items-center justify-between">
          <button 
            onClick={handlePrev} 
            disabled={currentIndex === 0}
            className="flex items-center px-4 py-2.5 rounded-xl font-medium transition-all text-slate-600 bg-slate-100 hover:bg-slate-200 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <ChevronLeft className="w-5 h-5 mr-1" />
            上一步
          </button>
          
          <div className="text-sm font-bold text-indigo-600 bg-indigo-50 px-3 py-1.5 rounded-lg border border-indigo-100">
            {currentIndex + 1} / {stepsData.length}
          </div>

          <button 
            onClick={handleNext} 
            disabled={currentIndex === stepsData.length - 1}
            className="flex items-center px-4 py-2.5 rounded-xl font-medium transition-all text-white bg-indigo-600 hover:bg-indigo-700 shadow-md shadow-indigo-200 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            下一步
            <ChevronRight className="w-5 h-5 ml-1" />
          </button>
        </div>
      </aside>

      {/* 右侧：Blackboard (黑板区) */}
      <section className="flex-1 bg-[#1e1e1e] p-8 overflow-y-auto relative shadow-inner flex flex-col"
               style={{
                 backgroundImage: 'radial-gradient(#333 1px, transparent 1px)',
                 backgroundSize: '20px 20px'
               }}
      >
        <div className="flex items-center text-slate-400 mb-4 border-b border-slate-700/50 pb-4">
          <Presentation className="w-5 h-5 mr-2" />
          <span className="text-sm font-mono tracking-wider uppercase">Freeform Canvas</span>
        </div>
        
        {/* Block 挂载点 (Freeform 画布) */}
        <div className="relative w-full flex-1 min-h-[600px] border border-slate-700/30 rounded-xl overflow-hidden bg-[#222]">
          {currentStep.boardState.map((block) => {
            // Apply different styles based on block type and highlight state
            const isText = block.type === 'text';
            const isResult = block.type === 'result';
            
            let baseStyle = "absolute transition-all duration-500 ease-out px-4 py-2 rounded-lg flex items-center whitespace-nowrap ";
            
            // Type-specific styles
            if (isText) {
              baseStyle += "text-xl font-bold text-slate-100 bg-transparent shadow-none ";
            } else if (isResult) {
              baseStyle += "font-bold text-green-400 border-2 border-dashed border-green-400/50 bg-green-400/5 ";
            } else {
              baseStyle += "text-lg text-sky-200 bg-white/5 border border-white/5 shadow-md ";
            }

            // Highlight styles
            if (block.highlight) {
              baseStyle += "bg-yellow-500/15 border-yellow-500/50 text-yellow-200 shadow-[0_0_20px_4px_rgba(234,179,8,0.25)] z-10 ";
            } else {
              baseStyle += "z-0 ";
            }

            return (
              <div
                key={block.id}
                className={baseStyle + " block-enter"}
                style={{
                  left: `${block.x}%`,
                  top: `${block.y}%`,
                  fontFamily: '"Comic Sans MS", "Chalkboard SE", cursive, sans-serif',
                  transform: `rotate(${block.rot}deg) scale(${block.highlight ? 1.05 : 1})`,
                  transformOrigin: 'center center'
                }}
              >
                {block.content}
              </div>
            );
          })}
        </div>
      </section>

      <style dangerouslySetInnerHTML={{__html: `
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(5px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes popIn {
          0% { opacity: 0; }
          100% { opacity: 1; }
        }
        .block-enter {
          animation: popIn 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
      `}} />
    </div>
  );
}