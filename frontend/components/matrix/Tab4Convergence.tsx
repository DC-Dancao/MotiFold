"use client";

import React, { useState, useEffect } from 'react';
import { Loader2, FolderTree, BarChart3, Sparkles } from 'lucide-react';
import { fetchWithAuth, getApiUrl } from '../../app/lib/api';
import SolutionClusters from './SolutionClusters';
import AHPWeights from './AHPWeights';
import SolutionRanking from './SolutionRanking';

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

interface Tab4ConvergenceProps {
  analysisId: number;
  parameters: Parameter[];
  matrixData: MatrixData;
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
  solution: string[];
  score: number;
  ratings: Record<string, number>;
  summary: string;
}

export default function Tab4Convergence({ analysisId, parameters, matrixData }: Tab4ConvergenceProps) {
  const [solutions, setSolutions] = useState<number[][]>([]);
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [weights, setWeights] = useState<Criteria[]>([]);
  const [rankedSolutions, setRankedSolutions] = useState<RankedSolution[]>([]);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<'enumerate' | 'cluster' | 'weights' | 'rank'>('enumerate');
  const [error, setError] = useState<string | null>(null);

  const enumerateSolutions = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWithAuth(`${getApiUrl()}/matrix/morphological/solutions/${analysisId}`, {
        method: 'GET'
      });
      if (res.ok) {
        const data = await res.json();
        setSolutions(data.solutions);
        setStep('cluster');
      }
    } catch (e) {
      setError('Failed to enumerate solutions');
    } finally {
      setLoading(false);
    }
  };

  const runClustering = async () => {
    setLoading(true);
    try {
      const res = await fetchWithAuth(`${getApiUrl()}/matrix/morphological/cluster`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ analysis_id: analysisId, max_clusters: 5 })
      });
      if (res.ok) {
        const data = await res.json();
        setClusters(data.clusters);
        setStep('weights');
      }
    } catch (e) {
      setError('Failed to cluster solutions');
    } finally {
      setLoading(false);
    }
  };

  const suggestWeights = async () => {
    setLoading(true);
    try {
      const res = await fetchWithAuth(`${getApiUrl()}/matrix/morphological/ahp-suggest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ analysis_id: analysisId })
      });
      if (res.ok) {
        const data = await res.json();
        setWeights(data.criteria);
      }
    } catch (e) {
      setWeights([
        { name: 'Cost', weight: 0.30 },
        { name: 'Time', weight: 0.20 },
        { name: 'Risk', weight: 0.25 },
        { name: 'Performance', weight: 0.25 }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const runScoring = async () => {
    setLoading(true);
    try {
      const res = await fetchWithAuth(`${getApiUrl()}/matrix/morphological/score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ analysis_id: analysisId, weights })
      });
      if (res.ok) {
        const data = await res.json();
        setRankedSolutions(data.ranked_solutions);
        setStep('rank');
      }
    } catch (e) {
      setError('Failed to score solutions');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
        <h2 className="text-xl font-semibold mb-4">Solution Convergence</h2>
        <p className="text-slate-600 mb-6">
          Enumerate valid solutions, group them into clusters, and rank using multi-criteria analysis.
        </p>

        {/* Progress Steps */}
        <div className="flex items-center gap-2 mb-6">
          {['enumerate', 'cluster', 'weights', 'rank'].map((s, i) => (
            <React.Fragment key={s}>
              <button
                onClick={() => {
                  if (s === 'enumerate') enumerateSolutions();
                  else if (s === 'cluster' && solutions.length > 0) runClustering();
                  else if (s === 'weights' && clusters.length > 0) suggestWeights();
                  else if (s === 'rank' && weights.length > 0) runScoring();
                }}
                disabled={
                  (s === 'enumerate' && solutions.length > 0) ||
                  (s === 'cluster' && clusters.length > 0) ||
                  (s === 'weights' && weights.length > 0) ||
                  (s === 'rank' && rankedSolutions.length > 0)
                }
                className={`px-4 py-2 rounded-lg font-medium transition ${
                  step === s ? 'bg-indigo-600 text-white' :
                  solutions.length > 0 || clusters.length > 0 || weights.length > 0 || rankedSolutions.length > 0
                    ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-600'
                }`}
              >
                {i + 1}. {s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
              {i < 3 && <span className="text-slate-300">→</span>}
            </React.Fragment>
          ))}
        </div>

        {loading && (
          <div className="flex items-center justify-center py-10">
            <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
            <span className="ml-2 text-slate-600">Processing...</span>
          </div>
        )}

        {error && (
          <div className="bg-red-50 text-red-700 p-4 rounded-lg">{error}</div>
        )}

        {!loading && step === 'enumerate' && solutions.length === 0 && (
          <button
            onClick={enumerateSolutions}
            className="bg-indigo-600 text-white px-6 py-3 rounded-xl font-medium hover:bg-indigo-700 flex items-center"
          >
            <Sparkles className="w-5 h-5 mr-2" />
            Enumerate All Solutions
          </button>
        )}

        {solutions.length > 0 && (
          <div className="bg-green-50 text-green-800 p-4 rounded-lg mb-4">
            Found {solutions.length.toLocaleString()} valid solutions
          </div>
        )}
      </div>

      {!loading && clusters.length > 0 && (
        <SolutionClusters
          clusters={clusters}
          parameters={parameters}
          solutions={solutions}
          onClustersChange={setClusters}
        />
      )}

      {!loading && weights.length > 0 && (
        <AHPWeights
          criteria={weights}
          onWeightsChange={setWeights}
          onNext={runScoring}
        />
      )}

      {!loading && rankedSolutions.length > 0 && (
        <SolutionRanking
          rankedSolutions={rankedSolutions}
          parameters={parameters}
        />
      )}
    </div>
  );
}
