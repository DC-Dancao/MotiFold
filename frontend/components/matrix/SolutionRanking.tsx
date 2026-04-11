"use client";

import React, { useState } from 'react';
import { Trophy, ChevronDown, ChevronUp } from 'lucide-react';

interface Parameter {
  name: string;
  states: string[];
}

interface RankedSolution {
  rank: number;
  solution_index: number;
  solution: string[];
  score: number;
  ratings: Record<string, number>;
  summary: string;
}

interface SolutionRankingProps {
  rankedSolutions: RankedSolution[];
  parameters: Parameter[];
}

export default function SolutionRanking({ rankedSolutions, parameters }: SolutionRankingProps) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(0);

  const getSolutionDisplay = (sol: string[]) => {
    return sol.map((stateName, pIdx) => ({
      param: parameters[pIdx]?.name || `Param ${pIdx}`,
      state: stateName
    }));
  };

  return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
      <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
        <Trophy className="w-5 h-5 text-yellow-500" />
        Top Recommended Solutions
      </h3>

      <div className="space-y-4">
        {rankedSolutions.slice(0, 5).map((item) => {
          const display = getSolutionDisplay(item.solution);
          const isExpanded = expandedIdx === item.rank - 1;

          return (
            <div key={item.rank} className="border border-slate-200 rounded-xl overflow-hidden">
              <div
                className="flex items-center justify-between p-4 cursor-pointer hover:bg-slate-50"
                onClick={() => setExpandedIdx(isExpanded ? null : item.rank - 1)}
              >
                <div className="flex items-center gap-4">
                  <span className={`w-8 h-8 rounded-full flex items-center justify-center font-bold ${
                    item.rank === 1 ? 'bg-yellow-100 text-yellow-700' :
                    item.rank === 2 ? 'bg-slate-200 text-slate-700' :
                    item.rank === 3 ? 'bg-orange-100 text-orange-700' :
                    'bg-slate-100 text-slate-600'
                  }`}>
                    {item.rank}
                  </span>
                  <div>
                    <div className="font-medium">
                      Score: {(item.score * 100).toFixed(1)}%
                    </div>
                    <div className="text-sm text-slate-500">
                      {display.slice(0, 3).map(d => d.state).join(', ')}
                    </div>
                  </div>
                </div>
                <button className="text-slate-400">
                  {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
                </button>
              </div>

              {isExpanded && (
                <div className="border-t border-slate-200 p-4 bg-slate-50">
                  <div className="mb-4">
                    <h4 className="text-sm font-medium mb-2">Solution Details</h4>
                    <div className="grid grid-cols-2 gap-2">
                      {display.map((d, i) => (
                        <div key={i} className="text-sm">
                          <span className="text-slate-500">{d.param}: </span>
                          <span className="font-medium">{d.state}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="mb-4">
                    <h4 className="text-sm font-medium mb-2">Criteria Ratings</h4>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(item.ratings).map(([criterion, rating]) => (
                        <span key={criterion} className="text-xs bg-white border border-slate-200 px-2 py-1 rounded">
                          {criterion}: {rating}/5
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="text-sm text-slate-600">
                    <h4 className="text-sm font-medium mb-1">Summary</h4>
                    <p>{item.summary}</p>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
