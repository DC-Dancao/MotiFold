"use client";

import { Suspense } from "react";
import { OrgProvider } from '../../app/lib/org-context';
import LeftSidebar from '../../components/layout/LeftSidebar';

export default function WorkspaceLayoutClient({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <OrgProvider>
      <div className="bg-slate-50 text-slate-900 h-screen overflow-hidden flex">
        <Suspense fallback={<div className="w-[356px] bg-slate-950 flex flex-shrink-0 z-20"></div>}>
          <LeftSidebar />
        </Suspense>
        <Suspense fallback={<div className="flex-1 bg-white"></div>}>
          {children}
        </Suspense>
      </div>
    </OrgProvider>
  );
}
