"use client";

import React, { useState, useMemo, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Sparkles, Loader2, RefreshCw, Save, Trash2, FolderOpen, Maximize2, Minimize2, Edit2 } from 'lucide-react';
import ReactECharts from 'echarts-for-react';
import { fetchWithAuth, getApiUrl, streamSSE, SSECancelFn } from '../../app/lib/api';
import Tab4Convergence from './Tab4Convergence';

const subTabs = ['定义问题', '交叉一致性评估', '解空间可视化', '方案收敛'];

interface Parameter {
  name: string;
  states: string[];
}

interface MatrixData {
  [pairId: string]: {
    [statePair: string]: {
      status: 'green' | 'yellow' | 'red';
      type?: 'L' | 'E' | 'N';
      reason?: string;
    };
  };
}

interface SavedAnalysis {
  id: number;
  focus_question: string;
  parameters: Parameter[];
  matrix: MatrixData;
  status: string;
  created_at: string;
  updated_at: string;
}

interface Cluster {
  id: string;
  name: string;
  description: string;
  solution_indices: number[];
}

interface Criteria {
  name: string;
  weight: number;
}

interface RankedSolution {
  rank: number;
  solution_index: number;
  solution: number[];
  score: number;
  ratings: Record<string, number>;
  summary: string;
}

export default function MorphologicalTab() {
  const [currentTab, setCurrentTab] = useState(0);
  const [isMatrixFullscreen, setIsMatrixFullscreen] = useState(false);
  
  const [problemDescription, setProblemDescription] = useState("");
  const [focusQuestion, setFocusQuestion] = useState("");
  const [isExtracting, setIsExtracting] = useState(false);
  const [parameters, setParameters] = useState<Parameter[]>([]);
  const [isGeneratingParams, setIsGeneratingParams] = useState(false);
  const [analysisStatus, setAnalysisStatus] = useState<string>("pending");
  
  const [matrixData, setMatrixData] = useState<MatrixData>({});
  const [isEvaluating, setIsEvaluating] = useState(false);
  
  const [selectedStates, setSelectedStates] = useState<Record<number, number>>({});
  
  const [savedAnalyses, setSavedAnalyses] = useState<SavedAnalysis[]>([]);
  const [isLoadingSaved, setIsLoadingSaved] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [currentAnalysisId, setCurrentAnalysisId] = useState<number | null>(null);
  const [matrixEventSource, setMatrixEventSource] = useState<SSECancelFn | null>(null);
  const [sseRetryCount, setSseRetryCount] = useState(0);
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const [editingCell, setEditingCell] = useState<{pIdx: number, sIdx: number} | null>(null);
  const [editValue, setEditValue] = useState("");

  const maxStatesCount = useMemo(() => {
    return Math.max(...parameters.map(p => p.states.length), 0);
  }, [parameters]);

  const flatCols = useMemo(() => {
    const cols: { pIdx: number, sIdx: number, pName: string, sName: string }[] = [];
    for (let pIdx = 0; pIdx < parameters.length; pIdx++) {
      const p = parameters[pIdx];
      p.states.forEach((s, sIdx) => {
        cols.push({ pIdx, sIdx, pName: p.name, sName: s });
      });
    }
    return cols;
  }, [parameters]);

  const flatRows = useMemo(() => {
    const rows: { pIdx: number, sIdx: number, pName: string, sName: string }[] = [];
    for (let pIdx = 0; pIdx < parameters.length; pIdx++) {
      const p = parameters[pIdx];
      p.states.forEach((s, sIdx) => {
        rows.push({ pIdx, sIdx, pName: p.name, sName: s });
      });
    }
    return rows;
  }, [parameters]);

  const parameterPairs = useMemo(() => {
    const pairs = [];
    for(let i=0; i<parameters.length; i++) {
      for(let j=i+1; j<parameters.length; j++) {
        pairs.push({
          id: `${i}_${j}`,
          p1Idx: i, p2Idx: j,
          p1: parameters[i],
          p2: parameters[j]
        });
      }
    }
    return pairs;
  }, [parameters]);

  const startEditing = (pIdx: number, sIdx: number, currentValue: string) => {
    setEditingCell({ pIdx, sIdx });
    setEditValue(currentValue);
  };

  const saveEdit = () => {
    if (!editingCell) return;
    const { pIdx, sIdx } = editingCell;
    setParameters(prev => prev.map((p, pi) => {
      if (pi !== pIdx) return p;
      return {
        ...p,
        states: p.states.map((s, si) => si === sIdx ? editValue : s)
      };
    }));
    setEditingCell(null);
    // Auto-save
    setTimeout(() => handleSave(), 500);
  };

  const cancelEdit = () => {
    setEditingCell(null);
    setEditValue("");
  };

  const handleExtractQuestion = async () => {
    if (!problemDescription.trim()) return;
    try {
      setIsExtracting(true);
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/matrix/morphological/extract-question`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ problem_description: problemDescription.trim() })
      });
      if (res.ok) {
        const data = await res.json();
        setFocusQuestion(data.focus_question);
      }
    } catch (error) {
      console.error("Failed to extract focus question", error);
    } finally {
      setIsExtracting(false);
    }
  };

  const handleGenerateParams = async () => {
    const problemDesc = problemDescription.trim();
    let effectiveFocusQuestion = focusQuestion.trim();

    // If focusQuestion is not yet set but problemDescription is, extract it first
    if (!effectiveFocusQuestion && problemDesc) {
      setIsExtracting(true);
      try {
        const apiUrl = getApiUrl();
        const res = await fetchWithAuth(`${apiUrl}/matrix/morphological/extract-question`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ problem_description: problemDesc })
        });
        if (res.ok) {
          const data = await res.json();
          effectiveFocusQuestion = data.focus_question;
          setFocusQuestion(effectiveFocusQuestion);
        }
      } catch (error) {
        console.error("Failed to extract focus question", error);
      } finally {
        setIsExtracting(false);
      }
    }

    if (!effectiveFocusQuestion || analysisStatus === 'generating_parameters') return;

    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }

    try {
      setIsGeneratingParams(true);
      const apiUrl = getApiUrl();
      const workspaceIdStr = localStorage.getItem('motifold_active_workspace_id');
      const workspaceId = workspaceIdStr ? parseInt(workspaceIdStr, 10) : null;

      const res = await fetchWithAuth(`${apiUrl}/matrix/morphological/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          focus_question: effectiveFocusQuestion,
          workspace_id: workspaceId
        })
      });

      if (res.ok) {
        const data = await res.json();
        setCurrentAnalysisId(data.id);
        setFocusQuestion(data.focus_question);
        setAnalysisStatus(data.status);
        setParameters([]);
        setMatrixData({}); // reset matrix
        setSelectedStates({});

        // Force refresh the LeftSidebar history list
        window.dispatchEvent(new Event('refresh-morphological-history'));
        // Wait for notification to refresh data
      }
    } catch (error) {
      console.error("Failed to generate parameters", error);
    } finally {
      setIsGeneratingParams(false);
    }
  };

  const handleEvaluate = async () => {
    if (parameters.length === 0 || !currentAnalysisId || analysisStatus === 'evaluating_matrix') return;
    
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }

    try {
      setIsEvaluating(true);
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/matrix/morphological/evaluate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ analysis_id: currentAnalysisId })
      });
      
      if (res.ok) {
        const data = await res.json();
        setAnalysisStatus(data.status);
      }
    } catch (error) {
      console.error("Failed to evaluate consistency", error);
    } finally {
      setIsEvaluating(false);
    }
  };

  const getMatrixValue = (pairId: string, s1Idx: number, s2Idx: number) => {
    if(!matrixData[pairId]) return 'unknown';
    const cell = matrixData[pairId][`${s1Idx}_${s2Idx}`];
    return cell?.status || 'unknown';
  };

  const toggleMatrixValue = (pairId: string, s1Idx: number, s2Idx: number) => {
    const current = getMatrixValue(pairId, s1Idx, s2Idx);
    let next: 'green' | 'yellow' | 'red' = 'green';
    if(current === 'green') next = 'yellow';
    else if(current === 'yellow') next = 'red';

    setMatrixData(prev => ({
      ...prev,
      [pairId]: {
        ...(prev[pairId] || {}),
        [`${s1Idx}_${s2Idx}`]: { status: next }
      }
    }));
  };

  const getColorClass = (val: string) => {
    if(val === 'green') return 'bg-green-500 text-white hover:bg-green-400';
    if(val === 'yellow') return 'bg-yellow-400 text-yellow-900 hover:bg-yellow-300';
    if(val === 'red') return 'bg-red-500 text-white hover:bg-red-400';
    return 'bg-slate-50 text-slate-400 hover:bg-slate-100';
  };

  const getMatrixText = (val: string) => {
    if(val === 'green') return 'V';
    if(val === 'yellow') return '?';
    if(val === 'red') return 'X';
    return '-';
  };

  const toggleSelection = (pIdx: number, sIdx: number) => {
    setSelectedStates(prev => {
      const next = { ...prev };
      if (next[pIdx] === sIdx) {
        delete next[pIdx];
      } else {
        next[pIdx] = sIdx;
      }
      return next;
    });
  };

  const clearSelection = () => {
    setSelectedStates({});
  };

  const getCompatibility = (p1Idx: number, s1Idx: number, p2Idx: number, s2Idx: number) => {
    let pid1 = p1Idx, pid2 = p2Idx, sid1 = s1Idx, sid2 = s2Idx;
    if (p1Idx > p2Idx) {
      pid1 = p2Idx; pid2 = p1Idx;
      sid1 = s2Idx; sid2 = s1Idx;
    }
    const pairId = `${pid1}_${pid2}`;
    const val = getMatrixValue(pairId, sid1, sid2);
    return val === 'unknown' ? 'green' : val;
  };

  const getSolutionCellClass = (pIdx: number, sIdx: number) => {
    if (selectedStates[pIdx] === sIdx) {
      return 'bg-blue-600 text-white shadow-md border-blue-700 font-bold';
    }

    let worstStatus = 'green';
    for (const [selPIdxStr, selSIdx] of Object.entries(selectedStates)) {
      const selPIdx = parseInt(selPIdxStr);
      if (selPIdx === pIdx) continue;
      
      const status = getCompatibility(selPIdx, selSIdx, pIdx, sIdx);
      if (status === 'red') worstStatus = 'red';
      else if (status === 'yellow' && worstStatus !== 'red') worstStatus = 'yellow';
    }

    if (worstStatus === 'red') return 'bg-red-50 text-red-300 border-red-100 opacity-50 cursor-not-allowed';
    if (worstStatus === 'yellow') return 'bg-yellow-50 text-yellow-700 border-yellow-200';
    return 'bg-white text-slate-700 border-slate-200 hover:border-blue-400';
  };

  const chartOption = useMemo(() => {
    if (parameters.length === 0) return {};
    
    const schema = parameters.map((p, i) => ({
      dim: i,
      name: p.name,
      type: 'category',
      data: p.states
    }));

    const data: string[][] = [];
    const maxSolutions = 50;
    const MAX_TOTAL_ITERATIONS = 100000;
    let totalIterations = 0;

    const findOneSolution = (): number[] | null => {
      let result: number[] | null = null;

      const dfs = (currentPath: number[], currentYellows: number) => {
        if (result || totalIterations > MAX_TOTAL_ITERATIONS) return;
        
        const pIdx = currentPath.length;
        if (pIdx === parameters.length) {
          result = [...currentPath];
          return;
        }

        let statesToExplore: number[];
        if (selectedStates[pIdx] !== undefined) {
          statesToExplore = [selectedStates[pIdx]];
        } else {
          statesToExplore = Array.from({ length: parameters[pIdx].states.length }, (_, i) => i);
          statesToExplore.sort(() => Math.random() - 0.5);
        }

        for (const sIdx of statesToExplore) {
          if (result || totalIterations > MAX_TOTAL_ITERATIONS) break;
          totalIterations++;
          
          let isValid = true;
          let newYellows = 0;
          
          for (let prevPIdx = 0; prevPIdx < pIdx; prevPIdx++) {
            const comp = getCompatibility(prevPIdx, currentPath[prevPIdx], pIdx, sIdx);
            if (comp === 'red') {
              isValid = false;
              break;
            } else if (comp === 'yellow') {
              newYellows++;
            }
          }

          if (isValid && (currentYellows + newYellows) <= 2) {
            dfs([...currentPath, sIdx], currentYellows + newYellows);
          }
        }
      };

      dfs([], 0);
      return result;
    };

    const dataSet = new Set<string>();
    let attempts = 0;
    while (data.length < maxSolutions && attempts < 200 && totalIterations < MAX_TOTAL_ITERATIONS) {
      attempts++;
      const sol = findOneSolution();
      if (sol) {
        const solStr = sol.join(',');
        if (!dataSet.has(solStr)) {
          dataSet.add(solStr);
          data.push(sol.map((idx, i) => parameters[i].states[idx]));
        }
      } else {
        // If DFS couldn't find a solution, the space might be empty or too constrained.
        break;
      }
    }

    return {
      parallel: {
        left: '5%',
        right: '15%',
        bottom: '10%',
        top: '20%',
        parallelAxisDefault: {
          type: 'category',
          nameLocation: 'end',
          nameGap: 20,
          nameTextStyle: {
            fontSize: 12
          }
        }
      },
      parallelAxis: schema,
      series: {
        type: 'parallel',
        lineStyle: {
          width: 2,
          opacity: 0.5,
          color: '#3b82f6'
        },
        data: data
      }
    };
  }, [parameters, matrixData, selectedStates]);

  const handleSave = async () => {
    if (parameters.length === 0) return;
    try {
      setIsSaving(true);
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/matrix/morphological`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          id: currentAnalysisId,
          focus_question: focusQuestion,
          parameters,
          matrix: matrixData
        })
      });
      
      if (res.ok) {
        const data = await res.json();
        if (!currentAnalysisId) {
          setCurrentAnalysisId(data.id);
        }
        // Force refresh the LeftSidebar history list
        window.dispatchEvent(new Event('refresh-morphological-history'));
      }
    } catch (error) {
      console.error("Failed to save morphological analysis", error);
    } finally {
      setIsSaving(false);
    }
  };

  // Auto save effect when matrixData or parameters change significantly
  useEffect(() => {
    if (parameters.length > 0 && !isGeneratingParams && !isEvaluating) {
      const timer = setTimeout(() => {
        handleSave();
      }, 2000); // Auto-save after 2 seconds of inactivity
      return () => clearTimeout(timer);
    }
  }, [matrixData, parameters, focusQuestion]);

  // SSE connection for real-time matrix updates
  useEffect(() => {
    if (!currentAnalysisId || (analysisStatus !== 'generating_parameters' && analysisStatus !== 'evaluating_matrix')) {
      return;
    }

    const streamUrl = `/matrix/morphological/${currentAnalysisId}/stream`;
    const es = streamSSE(streamUrl, {
      onMessage: (data) => {
        const eventType = (data.type || data.event || '') as string;

        // Handle rejoin event — load state from SSE
        if (eventType === 'rejoin') {
          if (data.parameters) {
            let parsedParams = data.parameters;
            try {
              if (typeof parsedParams === 'string') {
                parsedParams = JSON.parse(parsedParams);
              }
            } catch (e) {
              console.error("Failed to parse parameters", e);
            }
            setParameters(parsedParams as Parameter[]);
          }
          if (data.matrix) setMatrixData(data.matrix as MatrixData);
          if (data.status) setAnalysisStatus(data.status as string);
          if (data.focus_question) setFocusQuestion(data.focus_question as string);
          return;
        }

        if (eventType === 'status') {
          if (data.status) setAnalysisStatus(data.status as string);
        } else if (eventType === '[DONE]') {
          if (data.parameters) {
            let parsedParams = data.parameters;
            try {
              if (typeof parsedParams === 'string') {
                parsedParams = JSON.parse(parsedParams);
              }
            } catch (e) {
              console.error("Failed to parse parameters", e);
            }
            setParameters(parsedParams as Parameter[]);
          }
          if (data.matrix) setMatrixData(data.matrix as MatrixData);
          if (data.status) setAnalysisStatus(data.status as string);
          if (data.error) {
            console.error("Matrix generation error:", data.error);
          }
          setIsGeneratingParams(false);
          es.cancel();
          setMatrixEventSource(null);
          setSseRetryCount(0);
          window.dispatchEvent(new Event('refresh-morphological-history'));
        } else if (eventType === 'error') {
          console.error("Matrix SSE error:", (data.message || data.error) as string);
          es.cancel();
          setMatrixEventSource(null);
        }
      },
      onDone: () => {
        setMatrixEventSource(null);
        setSseRetryCount(0);
      },
      onError: () => {
        if (retryTimeoutRef.current) {
          clearTimeout(retryTimeoutRef.current);
          retryTimeoutRef.current = null;
        }

        // Retry up to 5 times
        const maxRetries = 5;
        if (sseRetryCount < maxRetries &&
            (analysisStatus === 'generating_parameters' || analysisStatus === 'evaluating_matrix')) {
          const delay = Math.min(1000 * Math.pow(2, sseRetryCount), 30000);
          setSseRetryCount(prev => prev + 1);

          retryTimeoutRef.current = setTimeout(() => {
            setMatrixEventSource(null);
          }, delay);
          return;
        }

        setMatrixEventSource(null);
      },
    });
    setMatrixEventSource(es);

    return () => {
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
        retryTimeoutRef.current = null;
      }
      es.cancel();
      setMatrixEventSource(null);
    };
  }, [currentAnalysisId, analysisStatus, sseRetryCount]);

  // Reset SSE retry count when currentAnalysisId changes
  useEffect(() => {
    setSseRetryCount(0);
  }, [currentAnalysisId]);

  const fetchSavedAnalyses = async () => {
    try {
      setIsLoadingSaved(true);
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/matrix/morphological`);
      if (res.ok) {
        const data = await res.json();
        setSavedAnalyses(data);
      }
    } catch (error) {
      console.error("Failed to fetch saved analyses", error);
    } finally {
      setIsLoadingSaved(false);
    }
  };

  const loadAnalysis = (analysis: SavedAnalysis) => {
    setCurrentAnalysisId(analysis.id);
    setFocusQuestion(analysis.focus_question);
    
    // Parse parameters properly to ensure it matches the schema format exactly
    let parsedParams = analysis.parameters;
    try {
      if (typeof parsedParams === 'string') {
        parsedParams = JSON.parse(parsedParams);
      }
    } catch (e) {
      console.error("Failed to parse parameters", e);
    }
    
    setParameters(parsedParams);
    setMatrixData(analysis.matrix || {});
    setAnalysisStatus(analysis.status || "completed");
    setSelectedStates({});
    setCurrentTab(0); // Switch to first tab to start working on it
  };

  const deleteAnalysis = async (id: number) => {
    try {
      const apiUrl = getApiUrl();
      const res = await fetchWithAuth(`${apiUrl}/matrix/morphological/${id}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        setSavedAnalyses(prev => prev.filter(a => a.id !== id));
      }
    } catch (error) {
      console.error("Failed to delete analysis", error);
    }
  };

  useEffect(() => {
    const handleNewAnalysis = () => {
      setCurrentAnalysisId(null);
      setProblemDescription("");
      setFocusQuestion("");
      setParameters([]);
      setMatrixData({});
      setSelectedStates({});
      setAnalysisStatus("pending");
      setCurrentTab(0);
    };

    const handleDeletedAnalysis = (e: Event) => {
      const customEvent = e as CustomEvent<{ id: number }>;
      if (customEvent.detail.id === currentAnalysisId) {
        handleNewAnalysis();
      }
    };

    window.addEventListener('new-morphological-analysis', handleNewAnalysis);
    window.addEventListener('deleted-morphological-analysis', handleDeletedAnalysis);
    return () => {
      window.removeEventListener('new-morphological-analysis', handleNewAnalysis);
      window.removeEventListener('deleted-morphological-analysis', handleDeletedAnalysis);
    };
  }, [currentAnalysisId]);

  useEffect(() => {
    const handleNotification = (e: Event) => {
      const customEvent = e as CustomEvent;
      const data = customEvent.detail;

      if (data.resource_id === currentAnalysisId && data.resource_type === 'morphological_analysis') {
        if (data.result === 'success') {
          // SSE delivers data directly, just refresh history for sidebar
          window.dispatchEvent(new Event('refresh-morphological-history'));
        } else if (data.result === 'error') {
          // update local status on error from the notification's true status
          if (data.status) {
            setAnalysisStatus(data.status);
          } else {
            setAnalysisStatus(data.task_type === 'generate_parameters' ? 'generate_failed' : 'evaluate_failed');
          }
        }
      }
    };

    window.addEventListener('global-notification', handleNotification);
    return () => {
      window.removeEventListener('global-notification', handleNotification);
    };
  }, [currentAnalysisId]);

  useEffect(() => {
    const handleLoadAnalysis = (e: Event) => {
      const customEvent = e as CustomEvent<{ id: number }>;
      const analysisId = customEvent.detail.id;
      
      const analysisToLoad = savedAnalyses.find(a => a.id === analysisId);
      if (analysisToLoad) {
        loadAnalysis(analysisToLoad);
      } else {
        // If it's not in the currently loaded savedAnalyses, fetch it specifically
        const fetchAndLoad = async () => {
          try {
            const apiUrl = getApiUrl();
            const res = await fetchWithAuth(`${apiUrl}/matrix/morphological/${analysisId}`);
            if (res.ok) {
              const data = await res.json();
              loadAnalysis(data);
            }
          } catch (err) {
            console.error("Failed to fetch specific analysis", err);
          }
        };
        fetchAndLoad();
      }
    };

    window.addEventListener('load-morphological-analysis', handleLoadAnalysis);
    return () => {
      window.removeEventListener('load-morphological-analysis', handleLoadAnalysis);
    };
  }, [savedAnalyses]);

  useEffect(() => {
    if (currentTab === 3) {
      fetchSavedAnalyses();
    }
  }, [currentTab]);

  useEffect(() => {
    if (!isMatrixFullscreen) return;

    const previousOverflow = document.body.style.overflow;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsMatrixFullscreen(false);
      }
    };

    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isMatrixFullscreen]);

  const renderCrossConsistencyMatrix = (fullscreen = false) => {
    if (parameters.length === 0) {
      return <div className="text-center py-10 text-slate-500">请先在第一步提取参数。</div>;
    }

    const displayCols = flatCols.filter(col => col.pIdx < parameters.length - 1);
    const displayRows = flatRows.filter(row => row.pIdx > 0);

    return (
      <div
        className={`overflow-auto rounded-2xl border border-slate-200 bg-white ${fullscreen ? 'flex-1 min-h-0 shadow-inner' : ''}`}
        style={fullscreen ? undefined : { maxHeight: 'calc(100vh - 20rem)' }}
      >
        <table className="border-collapse text-sm text-center w-max min-w-full">
          <thead>
            <tr>
              <th colSpan={2} className="border-0 min-w-[10rem] bg-white sticky top-0 left-0 z-30"></th>
              {parameters.slice(0, -1).map((p, pIdx) => (
                <th
                  key={'col-p-' + pIdx}
                  colSpan={p.states.length}
                  className="h-11 border border-slate-200 bg-slate-50 px-2 py-2 font-semibold sticky top-0 z-20 shadow-sm text-xs text-slate-700"
                >
                  {p.name}
                </th>
              ))}
            </tr>
            <tr>
              <th colSpan={2} className="border-0 min-w-[10rem] bg-white sticky top-11 left-0 z-30"></th>
              {displayCols.map((col, cIdx) => (
                <th
                  key={'col-s-' + cIdx}
                  className="border border-slate-200 bg-slate-50/60 px-1 py-2 font-medium sticky top-11 z-20 min-w-9 w-9 h-32 align-bottom shadow-sm"
                >
                  <div
                    style={{ writingMode: 'vertical-rl' }}
                    className="mx-auto text-[11px] leading-4 max-h-28 overflow-hidden text-ellipsis text-slate-600"
                  >
                    {col.sName}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayRows.map((row, rIdx) => (
              <tr key={'row-' + rIdx}>
                {row.sIdx === 0 && (
                  <th
                    rowSpan={parameters[row.pIdx].states.length}
                    className="border border-slate-200 bg-slate-50 px-2 py-3 font-semibold whitespace-nowrap sticky left-0 z-20 w-10 min-w-10 align-middle shadow-sm"
                  >
                    <div
                      style={{ writingMode: 'vertical-rl' }}
                      className="mx-auto text-[11px] leading-4 max-h-40 overflow-hidden text-ellipsis text-slate-700 rotate-180"
                    >
                      {row.pName}
                    </div>
                  </th>
                )}
                <th className="border border-slate-200 bg-slate-50/60 px-3 py-2 font-medium text-right whitespace-nowrap sticky left-10 z-20 text-xs w-30 min-w-[7.5rem] shadow-sm text-slate-600">
                  {row.sName}
                </th>

                {displayCols.filter(col => col.pIdx < row.pIdx).map((col, cIdx) => {
                  const pairId = `${col.pIdx}_${row.pIdx}`;
                  const val = getMatrixValue(pairId, col.sIdx, row.sIdx);
                  return (
                    <td
                      key={'cell-' + rIdx + '-' + cIdx}
                      className={`border border-slate-200 p-0 cursor-pointer transition-colors ${getColorClass(val)}`}
                      onClick={() => toggleMatrixValue(pairId, col.sIdx, row.sIdx)}
                    >
                      <div className="w-full h-full min-w-9 min-h-9 flex items-center justify-center font-bold text-xs">
                        {getMatrixText(val)}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  if (!currentAnalysisId && analysisStatus !== 'generating_parameters') {
    return (
      <div className="flex flex-col items-center justify-center min-h-[70vh] max-w-3xl mx-auto animate-fade-in text-center">
        <div className="bg-indigo-50 w-20 h-20 rounded-2xl flex items-center justify-center mb-6 shadow-sm border border-indigo-100">
          <Sparkles className="w-10 h-10 text-indigo-600" />
        </div>
        <h1 className="text-3xl font-bold text-slate-800 mb-4">开始新的形态分析</h1>
        <p className="text-slate-500 mb-8 text-lg max-w-xl">
          输入你想要探索或解决的复杂问题描述。AI 将自动为你提取核心焦点问题，并基于 7×7 法则生成多维度的形态学参数和状态。
        </p>

        <div className="w-full bg-white p-6 rounded-2xl shadow-sm border border-slate-200 text-left">
          <label className="block text-sm font-medium text-slate-700 mb-2">问题描述 (Problem Description)</label>
          <textarea
            value={problemDescription}
            onChange={e => setProblemDescription(e.target.value)}
            className="w-full border border-slate-200 rounded-xl p-4 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-slate-800 resize-none mb-4 min-h-[120px] transition-all"
            placeholder="例如：我们需要设计一款面向未来战争的侦察和控制系统，需要考虑哪些核心维度和可能的技术状态..."
          />
          
          <div className="flex justify-end mb-6">
            <button 
              onClick={handleExtractQuestion}
              disabled={isExtracting || !problemDescription.trim()}
              className="bg-indigo-50 text-indigo-700 px-4 py-2 rounded-xl font-medium hover:bg-indigo-100 transition flex items-center shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isExtracting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
              {isExtracting ? '正在提取...' : '提取 Focus Question'}
            </button>
          </div>

          {focusQuestion !== "" && (
             <div className="animate-fade-in mb-6">
               <label className="block text-sm font-medium text-slate-700 mb-2">核心问题 (Focus Question)</label>
               <input 
                 type="text"
                 value={focusQuestion}
                 onChange={e => setFocusQuestion(e.target.value)}
                 className="w-full border border-slate-200 rounded-xl p-3 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-slate-800 transition-all"
               />
               <p className="text-xs text-slate-500 mt-2">你可以直接修改上述问题，确认无误后点击下方按钮生成形态分析。</p>
             </div>
          )}

          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-500 flex items-center gap-1.5">
               遵循 7×7 法则，限制参数和状态数量
            </span>
            <button 
              onClick={handleGenerateParams}
              disabled={isExtracting || isGeneratingParams || (!focusQuestion.trim() && !problemDescription.trim())}
              className="bg-indigo-600 text-white px-6 py-3 rounded-xl font-medium hover:bg-indigo-700 transition flex items-center shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isExtracting || isGeneratingParams ? <Loader2 className="w-5 h-5 mr-2 animate-spin" /> : null}
              {isExtracting ? '正在提取...' : isGeneratingParams ? '正在生成...' : '生成形态分析'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5 xl:space-y-6">
      <div className="flex flex-col gap-4 2xl:flex-row 2xl:items-center 2xl:justify-between">
        <nav className="flex flex-wrap gap-3">
          {subTabs.map((tab, index) => (
            <button key={index}
              onClick={() => setCurrentTab(index)}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                currentTab === index ? 'bg-indigo-600 text-white shadow' : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
              }`}>
              {index + 1}. {tab}
            </button>
          ))}
        </nav>
        
        <div className="flex items-center gap-2 self-start text-sm">
          {isSaving ? (
            <span className="flex items-center gap-1.5 text-slate-400">
              <Loader2 className="w-4 h-4 animate-spin" /> 保存中...
            </span>
          ) : parameters.length > 0 ? (
            <span className="flex items-center gap-1.5 text-emerald-500">
              <Save className="w-4 h-4" /> 已自动保存
            </span>
          ) : null}
        </div>
      </div>

      {/* Tab 1: 问题定义 */}
      {currentTab === 0 && (
        <div className="space-y-6 animate-fade-in">
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
            <h2 className="text-xl font-semibold mb-4">Focus Question & Parameters</h2>
            <div className="mb-4">
              <label className="block text-sm font-medium text-slate-700 mb-1">核心问题 (Focus Question)</label>
              <input 
                type="text" 
                value={focusQuestion}
                onChange={e => setFocusQuestion(e.target.value)}
                disabled={analysisStatus === 'generating_parameters'}
                className="w-full border border-slate-200 rounded-lg p-3 focus:ring-2 focus:ring-indigo-500 outline-none text-slate-800 disabled:bg-slate-50 disabled:text-slate-500" 
                placeholder="正在由 LLM 提取..."
              />
            </div>
            
            <div className="flex items-center space-x-4 mb-4">
              <button 
                onClick={handleGenerateParams}
                disabled={isExtracting || isGeneratingParams || analysisStatus === 'generating_parameters' || (!focusQuestion.trim() && !problemDescription.trim())}
                className="bg-indigo-50 text-indigo-700 px-4 py-2.5 rounded-lg font-medium hover:bg-indigo-100 transition flex items-center disabled:opacity-50"
              >
                {isExtracting || isGeneratingParams || analysisStatus === 'generating_parameters' ? <Loader2 className="w-5 h-5 mr-2 animate-spin" /> : <Sparkles className="w-5 h-5 mr-2" />}
                {isExtracting ? '正在提取核心问题...' : analysisStatus === 'generating_parameters' ? '正在后台生成参数与状态...' : '利用 LLM 重新提取'}
              </button>
              <span className="text-sm text-slate-500">遵循 7×7 经验法则，限制参数和状态数量</span>
            </div>
          </div>

          {analysisStatus === 'generating_parameters' && parameters.length === 0 && (
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 overflow-x-auto animate-pulse">
              <h2 className="text-xl font-semibold mb-4 text-slate-400">正在生成形态学矩阵...</h2>
              <div className="w-full space-y-4">
                <div className="flex gap-4">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="h-10 bg-slate-100 rounded flex-1"></div>
                  ))}
                </div>
                {Array.from({ length: 4 }).map((_, r) => (
                  <div key={r} className="flex gap-4">
                    {Array.from({ length: 5 }).map((_, c) => (
                      <div key={c} className="h-10 bg-slate-50 rounded flex-1"></div>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}

          {parameters.length > 0 && (
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 overflow-x-auto">
              <h2 className="text-xl font-semibold mb-4">形态学矩阵 (Morphological Table)</h2>
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr>
                    {parameters.map((p, pIdx) => (
                      <th key={pIdx} className="border border-slate-200 bg-slate-50 p-3 text-left font-semibold text-slate-700 w-1/5">
                        {p.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Array.from({ length: maxStatesCount }).map((_, rowIdx) => (
                    <tr key={rowIdx}>
                      {parameters.map((p, pIdx) => (
                        <td key={pIdx} className="border border-slate-200 p-3 align-top">
                          {p.states[rowIdx] && (
                            editingCell?.pIdx === pIdx && editingCell?.sIdx === rowIdx ? (
                              <div className="flex gap-1">
                                <input
                                  type="text"
                                  value={editValue}
                                  onChange={e => setEditValue(e.target.value)}
                                  onBlur={saveEdit}
                                  onKeyDown={e => {
                                    if (e.key === 'Enter') saveEdit();
                                    if (e.key === 'Escape') cancelEdit();
                                  }}
                                  className="border border-indigo-300 rounded px-2 py-1 text-sm w-full"
                                  maxLength={50}
                                  autoFocus
                                />
                              </div>
                            ) : (
                              <div
                                className="bg-indigo-50 text-indigo-800 px-3 py-2 rounded-lg border border-indigo-100/50 shadow-sm font-medium flex items-center justify-between group cursor-pointer"
                                onClick={() => startEditing(pIdx, rowIdx, p.states[rowIdx])}
                              >
                                <span className="flex-1">{p.states[rowIdx]}</span>
                                <button className="opacity-0 group-hover:opacity-100 text-indigo-400 hover:text-indigo-600 ml-2">
                                  <Edit2 className="w-3 h-3" />
                                </button>
                              </div>
                            )
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: 交叉一致性评估 */}
      {currentTab === 1 && (
        <div className="space-y-6">
          <div className="bg-white p-4 sm:p-6 xl:p-7 rounded-2xl shadow-sm border border-slate-200">
            <div className="flex flex-col gap-4 mb-5 lg:flex-row lg:items-start lg:justify-between">
              <div className="space-y-2">
                <h2 className="text-xl font-semibold text-slate-800">交叉一致性矩阵 (Cross-Consistency Matrix)</h2>
                <p className="text-slate-600 text-sm">点击单元格可手动修改状态兼容性。绿色=完全兼容，黄色=可能/待定，红色=逻辑/经验/规范矛盾。</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={() => setIsMatrixFullscreen(prev => !prev)}
                  disabled={parameters.length === 0}
                  className="px-4 py-2.5 bg-slate-100 text-slate-700 rounded-lg font-medium hover:bg-slate-200 transition flex items-center gap-2 disabled:opacity-50"
                >
                  {isMatrixFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
                  {isMatrixFullscreen ? '退出全屏' : '全屏查看'}
                </button>
                <button 
                  onClick={handleEvaluate}
                  disabled={isEvaluating || parameters.length === 0 || analysisStatus === 'evaluating_matrix'}
                  className="bg-purple-50 text-purple-700 px-4 py-2.5 rounded-lg font-medium hover:bg-purple-100 transition flex items-center disabled:opacity-50"
                >
                  {isEvaluating || analysisStatus === 'evaluating_matrix' ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-2" />}
                  {analysisStatus === 'evaluating_matrix' ? '后台预评估中...' : '批量预评估 (LLM)'}
                </button>
              </div>
            </div>
            {renderCrossConsistencyMatrix()}
          </div>
        </div>
      )}

      {/* Tab 3: 解空间可视化 */}
      {currentTab === 2 && (
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
            <h2 className="text-xl font-semibold mb-4 text-slate-800">交互式解空间探索</h2>
            <p className="text-slate-600 mb-6 text-sm">点击选择某个状态，查看其与其他参数状态的兼容性。</p>
            
            <div className="flex space-x-4 mb-4">
              <button onClick={clearSelection} className="bg-slate-100 text-slate-700 px-4 py-2 rounded-lg hover:bg-slate-200 font-medium text-sm transition">清除选择</button>
            </div>

            {parameters.length > 0 ? (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-7 gap-4">
                {parameters.map((p, pIdx) => (
                  <div key={pIdx} className="border border-slate-200 rounded-xl overflow-hidden shadow-sm">
                    <div className="bg-slate-50 p-3 text-center font-semibold border-b border-slate-200 text-sm truncate text-slate-700" title={p.name}>
                      {p.name}
                    </div>
                    <div className="p-2 space-y-2 bg-white">
                      {p.states.map((s, sIdx) => {
                        const cellClass = getSolutionCellClass(pIdx, sIdx);
                        const isRed = cellClass.includes('cursor-not-allowed');
                        return (
                          <div key={sIdx}
                            onClick={() => !isRed && toggleSelection(pIdx, sIdx)}
                            className={`p-2 rounded-lg border text-sm text-center transition-all ${cellClass} ${!isRed ? 'cursor-pointer' : ''}`}>
                            {s}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-10 text-slate-500">请先在第一步提取参数。</div>
            )}
          </div>

          {parameters.length > 0 && (
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
              <h2 className="text-xl font-semibold mb-4 text-slate-800">平行坐标图 (Parallel Coordinates)</h2>
              <div className="w-full h-96">
                <ReactECharts option={chartOption} style={{ height: '100%', width: '100%' }} />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 4: 方案收敛 */}
      {currentTab === 3 && currentAnalysisId && (
        <div className="animate-fade-in">
          <Tab4Convergence
            analysisId={currentAnalysisId}
            parameters={parameters}
            matrixData={matrixData}
          />
        </div>
      )}

      {currentTab === 1 && isMatrixFullscreen && createPortal(
        <div className="fixed inset-0 z-50">
          <button
            type="button"
            aria-label="关闭全屏视图"
            onClick={() => setIsMatrixFullscreen(false)}
            className="absolute inset-0 bg-slate-950/55"
          />
          <div className="relative z-10 m-3 flex h-[calc(100vh-1.5rem)] flex-col overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-2xl sm:m-6 sm:h-[calc(100vh-3rem)]">
            <div className="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
              <div>
                <h3 className="text-lg font-semibold text-slate-800">交叉一致性矩阵全屏视图</h3>
                <p className="text-sm text-slate-500">按 Esc 可退出，全屏模式下可更方便地横向与纵向浏览矩阵。</p>
              </div>
              <div className="flex items-center gap-2">
                <button 
                    onClick={handleEvaluate}
                    disabled={isEvaluating || parameters.length === 0 || analysisStatus === 'evaluating_matrix'}
                    className="bg-purple-50 text-purple-700 px-4 py-2.5 rounded-lg font-medium hover:bg-purple-100 transition flex items-center disabled:opacity-50"
                  >
                    {isEvaluating || analysisStatus === 'evaluating_matrix' ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-2" />}
                    {analysisStatus === 'evaluating_matrix' ? '后台预评估中...' : '批量预评估'}
                  </button>
                <button
                  onClick={() => setIsMatrixFullscreen(false)}
                  className="px-4 py-2.5 bg-slate-100 text-slate-700 rounded-lg font-medium hover:bg-slate-200 transition flex items-center gap-2"
                >
                  <Minimize2 className="w-4 h-4" />
                  退出全屏
                </button>
              </div>
            </div>
            <div className="flex-1 min-h-0 overflow-auto p-3 sm:p-5">
              {renderCrossConsistencyMatrix(true)}
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
