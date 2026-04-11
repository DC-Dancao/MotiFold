"use client";

import React, { useState, useMemo } from 'react';
import { Maximize2, Minimize2, Grid3X3, MousePointer } from 'lucide-react';

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

export default function HeatmapPage() {
  const [viewMode, setViewMode] = useState<'selection' | 'browse'>('selection');
  const [selectedStates, setSelectedStates] = useState<Record<number, number>>({});
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Get data from localStorage or parent context
  const [parameters, setParameters] = useState<Parameter[]>([]);
  const [matrixData, setMatrixData] = useState<MatrixData>({});

  // Load from localStorage on mount
  React.useEffect(() => {
    // Try localStorage first
    const stored = localStorage.getItem('morphological_current');
    if (stored) {
      try {
        const data = JSON.parse(stored);
        if (data.parameters) setParameters(data.parameters);
        if (data.matrix) setMatrixData(data.matrix);
      } catch (e) {
        console.error('Failed to load morphological data', e);
      }
    }
  }, []);

  // Helper function for other components to set data
  if (typeof window !== 'undefined') {
    (window as any).setMorphologicalData = (params: Parameter[], matrix: MatrixData) => {
      setParameters(params);
      setMatrixData(matrix);
      localStorage.setItem('morphological_current', JSON.stringify({ parameters: params, matrix }));
    };
  }

  const getCompatibility = (p1Idx: number, s1Idx: number, p2Idx: number, s2Idx: number) => {
    if (p1Idx === p2Idx) return 'green';
    const pid1 = Math.min(p1Idx, p2Idx);
    const pid2 = Math.max(p1Idx, p2Idx);
    const pairId = `${pid1}_${pid2}`;
    const key = p1Idx < p2Idx ? `${s1Idx}_${s2Idx}` : `${s2Idx}_${s1Idx}`;
    return matrixData[pairId]?.[key]?.status || 'green';
  };

  const getCellColor = (status: string) => {
    if (status === 'green') return 'bg-green-500';
    if (status === 'yellow') return 'bg-yellow-400';
    if (status === 'red') return 'bg-red-500';
    return 'bg-slate-200';
  };

  const toggleSelection = (pIdx: number, sIdx: number) => {
    setSelectedStates(prev => {
      if (prev[pIdx] === sIdx) {
        const next = { ...prev };
        delete next[pIdx];
        return next;
      }
      return { ...prev, [pIdx]: sIdx };
    });
  };

  // Selection mode - 7 cards like Tab 3
  const renderSelectionMode = () => (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-4">
      {parameters.map((p, pIdx) => (
        <div key={pIdx} className="border border-slate-200 rounded-xl overflow-hidden">
          <div className="bg-slate-50 p-3 text-center font-semibold border-b border-slate-200 text-sm truncate">
            {p.name}
          </div>
          <div className="p-2 space-y-2 bg-white">
            {p.states.map((s, sIdx) => {
              const isSelected = selectedStates[pIdx] === sIdx;

              // Check compatibility with other selected states
              let worstStatus = 'green';
              for (const [otherPIdx, otherSIdx] of Object.entries(selectedStates)) {
                if (parseInt(otherPIdx) === pIdx) continue;
                const compat = getCompatibility(parseInt(otherPIdx), otherSIdx, pIdx, sIdx);
                if (compat === 'red') worstStatus = 'red';
                else if (compat === 'yellow' && worstStatus !== 'red') worstStatus = 'yellow';
              }

              return (
                <div
                  key={sIdx}
                  onClick={() => toggleSelection(pIdx, sIdx)}
                  className={`p-2 rounded-lg border text-sm text-center cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-blue-600 text-white border-blue-700 font-bold'
                      : worstStatus === 'red'
                      ? 'bg-red-50 text-red-300 border-red-100 opacity-50 cursor-not-allowed'
                      : worstStatus === 'yellow'
                      ? 'bg-yellow-50 text-yellow-700 border-yellow-200'
                      : 'bg-white text-slate-700 border-slate-200 hover:border-blue-400'
                  }`}
                >
                  {s}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );

  // Browse mode - full heatmap matrix
  const renderBrowseMode = () => (
    <div className="overflow-auto rounded-xl border border-slate-200">
      <table className="border-collapse">
        <thead>
          <tr>
            <th className="border border-slate-200 bg-slate-50 p-2 sticky top-0 left-0 z-20"></th>
            {parameters.flatMap((p, pIdx) =>
              p.states.map((s, sIdx) => (
                <th
                  key={`${pIdx}-${sIdx}`}
                  className="border border-slate-200 bg-slate-50 p-1 min-w-10 text-xs font-normal"
                  style={{ writingMode: 'vertical-rl' }}
                >
                  {p.name}/{s}
                </th>
              ))
            )}
          </tr>
        </thead>
        <tbody>
          {parameters.flatMap((p1, p1Idx) =>
            p1.states.map((s1, s1Idx) => (
              <tr key={`${p1Idx}-${s1Idx}`}>
                <th className="border border-slate-200 bg-slate-50 p-1 text-xs font-normal sticky left-0">
                  {p1.name}/{s1}
                </th>
                {parameters.flatMap((p2, p2Idx) =>
                  p2.states.map((s2, s2Idx) => {
                    const compat = getCompatibility(p1Idx, s1Idx, p2Idx, s2Idx);
                    return (
                      <td
                        key={`${p1Idx}-${s1Idx}-${p2Idx}-${s2Idx}`}
                        className={`border border-slate-100 p-0 ${getCellColor(compat)}`}
                        title={`${p1.name}/${s1} vs ${p2.name}/${s2}: ${compat}`}
                      >
                        <div className="w-10 h-10"></div>
                      </td>
                    );
                  })
                )}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className={`flex flex-col h-full ${isFullscreen ? 'fixed inset-0 z-50 bg-white' : ''}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-200 bg-white">
        <div>
          <h2 className="text-xl font-semibold">Compatibility Heatmap</h2>
          <p className="text-sm text-slate-500">Interactive state compatibility visualization</p>
        </div>
        <div className="flex items-center gap-3">
          {/* View Mode Toggle */}
          <div className="flex rounded-lg border border-slate-200 overflow-hidden">
            <button
              onClick={() => setViewMode('selection')}
              className={`px-3 py-1.5 text-sm flex items-center gap-1 ${
                viewMode === 'selection' ? 'bg-indigo-600 text-white' : 'bg-white text-slate-600'
              }`}
            >
              <MousePointer className="w-4 h-4" />
              Selection
            </button>
            <button
              onClick={() => setViewMode('browse')}
              className={`px-3 py-1.5 text-sm flex items-center gap-1 ${
                viewMode === 'browse' ? 'bg-indigo-600 text-white' : 'bg-white text-slate-600'
              }`}
            >
              <Grid3X3 className="w-4 h-4" />
              Browse
            </button>
          </div>

          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="p-2 hover:bg-slate-100 rounded-lg"
          >
            {isFullscreen ? <Minimize2 className="w-5 h-5" /> : <Maximize2 className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {parameters.length === 0 ? (
          <div className="text-center py-20 text-slate-500">
            No morphological data loaded. Please create or load an analysis first.
          </div>
        ) : viewMode === 'selection' ? (
          renderSelectionMode()
        ) : (
          renderBrowseMode()
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 p-4 border-t border-slate-200 bg-white">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-green-500 rounded"></div>
          <span className="text-sm text-slate-600">Compatible</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-yellow-400 rounded"></div>
          <span className="text-sm text-slate-600">Conditional</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-red-500 rounded"></div>
          <span className="text-sm text-slate-600">Incompatible</span>
        </div>
      </div>
    </div>
  );
}