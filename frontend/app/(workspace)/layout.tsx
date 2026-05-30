import WorkspaceLayoutClient from "./layout-client";

// Auth is enforced in `proxy.ts` for every workspace route; no need to
// re-check the cookie here (it would add a second redirect hop on logout
// or expired sessions).
export default function WorkspaceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <WorkspaceLayoutClient>
      {children}
    </WorkspaceLayoutClient>
  );
}
