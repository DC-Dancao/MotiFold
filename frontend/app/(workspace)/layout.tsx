import { Suspense } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import WorkspaceLayoutClient from "./layout-client";

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
    <WorkspaceLayoutClient>
      {children}
    </WorkspaceLayoutClient>
  );
}
