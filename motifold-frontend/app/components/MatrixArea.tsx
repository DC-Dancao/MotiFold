"use client";

import React from 'react';
import MorphologicalTab from './MorphologicalTab';

export default function MatrixArea() {
  return (
    <main className="flex-1 flex bg-white min-w-0 relative">
      {/* Background Pattern */}
      <div 
        className="absolute inset-0 z-0 opacity-[0.02] pointer-events-none" 
        style={{ backgroundImage: 'radial-gradient(#000 1px, transparent 1px)', backgroundSize: '20px 20px' }}
      ></div>

      {/* Matrix Content Area */}
      <div className="flex-1 flex flex-col z-10 h-full overflow-hidden">
        {/* Header */}
        <div className="h-16 border-b border-slate-100 flex items-center px-5 md:px-6 xl:px-8 bg-white/80 backdrop-blur-sm sticky top-0 flex-shrink-0">
          <h3 className="font-bold text-slate-800 text-lg">
            形态分析
          </h3>
          <p className="text-slate-400 text-sm ml-4 border-l border-slate-200 pl-4">
            基于 LLM 的复杂问题降维与解空间探索
          </p>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6 xl:p-8 bg-slate-100/60">
          <div className="w-full space-y-6 max-w-none">
            <MorphologicalTab />
          </div>
        </div>
      </div>
    </main>
  );
}
