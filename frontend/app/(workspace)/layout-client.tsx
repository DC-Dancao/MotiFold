"use client";

import { Suspense } from "react";
import { OrgProvider, useOrg } from '../../app/lib/org-context';
import LeftSidebar from '../../components/layout/LeftSidebar';

function WorkspaceLayoutContent({ children }: { children: React.ReactNode }) {
  const { isLoading, currentOrg } = useOrg();

  if (isLoading || !currentOrg) {
    return (
      <div className="bg-slate-50 text-slate-900 h-screen overflow-hidden flex items-center justify-center">
        <div className="text-slate-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="bg-slate-50 text-slate-900 h-screen overflow-hidden flex">
      <Suspense fallback={<div className="w-[356px] bg-slate-950 flex flex-shrink-0 z-20"></div>}>
        <LeftSidebar />
      </Suspense>
      <Suspense fallback={<div className="flex-1 bg-white"></div>}>
        {children}
      </Suspense>
    </div>
  );
}

export default function WorkspaceLayoutClient({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <OrgProvider>
      <WorkspaceLayoutContent>{children}</WorkspaceLayoutContent>
    </OrgProvider>
  );
}
