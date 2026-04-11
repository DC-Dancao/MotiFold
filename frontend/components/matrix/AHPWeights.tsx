"use client";

import React, { useState } from 'react';
import { BarChart3, Check } from 'lucide-react';

interface Criteria {
  name: string;
  weight: number;
}

interface AHPWeightsProps {
  criteria: Criteria[];
  onWeightsChange: (criteria: Criteria[]) => void;
  onNext: () => void;
}

export default function AHPWeights({ criteria, onWeightsChange, onNext }: AHPWeightsProps) {
  const [localCriteria, setLocalCriteria] = useState(criteria);
  const [error, setError] = useState<string | null>(null);

  const updateWeight = (index: number, newWeight: number) => {
    const updated = [...localCriteria];
    updated[index] = { ...updated[index], weight: newWeight };
    setLocalCriteria(updated);
    setError(null);
  };

  const normalize = () => {
    const total = localCriteria.reduce((sum, c) => sum + c.weight, 0);
    if (total === 0) {
      setError('Weights cannot all be zero');
      return;
    }
    const normalized = localCriteria.map(c => ({
      ...c,
      weight: Math.round((c.weight / total) * 100) / 100
    }));
    setLocalCriteria(normalized);
  };

  const total = localCriteria.reduce((sum, c) => sum + c.weight, 0);
  const isValid = Math.abs(total - 1.0) < 0.01;

  const handleApply = () => {
    if (!isValid) {
      setError('Weights must sum to 1.0');
      return;
    }
    onWeightsChange(localCriteria);
  };

  return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
      <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
        <BarChart3 className="w-5 h-5" />
        AHP Criteria Weights
      </h3>

      <div className="space-y-4 mb-6">
        {localCriteria.map((criterion, idx) => (
          <div key={idx} className="flex items-center gap-4">
            <span className="w-32 text-sm font-medium">{criterion.name}</span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={criterion.weight}
              onChange={e => updateWeight(idx, parseFloat(e.target.value))}
              className="flex-1 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer"
            />
            <input
              type="number"
              min="0"
              max="1"
              step="0.05"
              value={criterion.weight}
              onChange={e => updateWeight(idx, parseFloat(e.target.value) || 0)}
              className="w-20 border border-slate-300 rounded px-2 py-1 text-sm"
            />
            <span className="w-12 text-sm text-slate-500">
              {Math.round(criterion.weight * 100)}%
            </span>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between mb-4">
        <div>
          <span className="text-sm text-slate-600">Total: </span>
          <span className={`font-medium ${isValid ? 'text-green-600' : 'text-red-600'}`}>
            {Math.round(total * 100)}%
          </span>
        </div>
        <button
          onClick={normalize}
          className="text-sm px-3 py-1 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200"
        >
          Normalize to 100%
        </button>
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 p-3 rounded-lg mb-4">{error}</div>
      )}

      <div className="flex gap-3">
        <button
          onClick={handleApply}
          disabled={!isValid}
          className="flex-1 bg-indigo-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 flex items-center justify-center gap-2"
        >
          <Check className="w-4 h-4" />
          Apply Weights & Score
        </button>
      </div>
    </div>
  );
}
