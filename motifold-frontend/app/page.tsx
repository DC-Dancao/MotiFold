import { Suspense } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import LeftSidebar from "./components/LeftSidebar";
import ChatArea from "./components/ChatArea";
import MatrixArea from "./components/MatrixArea";
import BlackboardArea from "./components/BlackboardArea";

type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

export default async function Home(props: { searchParams: SearchParams }) {
  const cookieStore = await cookies();
  const token = cookieStore.get('motifold_token')?.value;

  if (!token) {
    redirect('/login');
  }

  const searchParams = await props.searchParams;
  const view = searchParams.view || 'chat';

  return (
    <div className="bg-slate-50 text-slate-900 h-screen overflow-hidden flex">
      <Suspense fallback={<div className="w-[356px] bg-slate-950 flex flex-shrink-0 z-20"></div>}>
        <LeftSidebar />
      </Suspense>
      <Suspense fallback={<div className="flex-1 bg-white"></div>}>
        {view === 'matrix' ? <MatrixArea /> : view === 'blackboard' ? <BlackboardArea /> : <ChatArea />}
      </Suspense>
    </div>
  );
}
