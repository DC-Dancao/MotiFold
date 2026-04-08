import { Suspense } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import LeftSidebar from "../../components/layout/LeftSidebar";

export default async function WorkspaceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = await cookies();
  const token = cookieStore.get('motifold_token')?.value;

  if (!token) {
    redirect('/login');
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
