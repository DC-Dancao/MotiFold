"use client";

import React, { useState } from 'react';
import { FolderTree, Edit2, Check, X, Plus } from 'lucide-react';

interface Parameter {
  name: string;
  states: string[];
}

interface Cluster {
  id: string;
  name: string;
  description: string;
  solution_indices: number[];
}

interface SolutionClustersProps {
  clusters: Cluster[];
  parameters: Parameter[];
  solutions: number[][];
  onClustersChange: (clusters: Cluster[]) => void;
}

export default function SolutionClusters({ clusters, parameters, solutions, onClustersChange }: SolutionClustersProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');

  const renameCluster = (id: string, newName: string) => {
    onClustersChange(clusters.map(c => c.id === id ? { ...c, name: newName } : c));
    setEditingId(null);
  };

  const deleteCluster = (id: string) => {
    onClustersChange(clusters.filter(c => c.id !== id));
  };

  const getSolutionLabel = (sol: number[]) => {
    return sol.map((sIdx, pIdx) => parameters[pIdx]?.states[sIdx]).filter(Boolean).slice(0, 3).join(', ');
  };

  return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <FolderTree className="w-5 h-5" />
          Solution Clusters
        </h3>
        <button
          onClick={() => {
            const newCluster = {
              id: `custom-${Date.now()}`,
              name: 'New Cluster',
              description: '',
              solution_indices: []
            };
            onClustersChange([...clusters, newCluster]);
          }}
          className="text-sm px-3 py-1 bg-indigo-50 text-indigo-700 rounded-lg hover:bg-indigo-100 flex items-center gap-1"
        >
          <Plus className="w-4 h-4" />
          Add Cluster
        </button>
      </div>

      <div className="space-y-3">
        {clusters.map(cluster => (
          <div key={cluster.id} className="border border-slate-200 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              {editingId === cluster.id ? (
                <div className="flex items-center gap-2">
                  <input
                    value={editName}
                    onChange={e => setEditName(e.target.value)}
                    className="border border-slate-300 rounded px-2 py-1"
                    autoFocus
                  />
                  <button onClick={() => renameCluster(cluster.id, editName)} className="text-green-600">
                    <Check className="w-4 h-4" />
                  </button>
                  <button onClick={() => setEditingId(null)} className="text-red-600">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <>
                  <h4 className="font-medium">{cluster.name}</h4>
                  <div className="flex gap-2">
                    <button
                      onClick={() => { setEditingId(cluster.id); setEditName(cluster.name); }}
                      className="text-slate-400 hover:text-slate-600"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => deleteCluster(cluster.id)}
                      className="text-red-400 hover:text-red-600"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </>
              )}
            </div>

            {cluster.description && (
              <p className="text-sm text-slate-500 mb-3">{cluster.description}</p>
            )}

            <div className="flex flex-wrap gap-2">
              {cluster.solution_indices.slice(0, 5).map(idx => (
                <span key={idx} className="text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded">
                  {getSolutionLabel(solutions[idx] || [])}
                </span>
              ))}
              {cluster.solution_indices.length > 5 && (
                <span className="text-xs text-slate-400">
                  +{cluster.solution_indices.length - 5} more
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
