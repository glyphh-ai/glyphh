// What every work panel needs first: the machine's workspaces (the repositories the crew worked in there) and the
// one being read. A panel draws its own contents only once there is one; until then it says, in the app's empty
// state, what is missing.
import { useQuery } from '@tanstack/react-query';
import { useEffect, type ReactNode } from 'react';
import type { WorkClient, Workspace } from '@/api/work';
import { useWork, useWorkActions } from './store';

export function useWorkspaces() {
  const work = useWorkActions();
  const place = useWork((s) => s.place);
  const tick = useWork((s) => s.tick);
  const chosen = useWork((s) => s.ws);
  const found = useQuery({
    queryKey: ['work', place ?? '', 'workspaces', tick],
    queryFn: () => work.client!.workspaces(),
    enabled: Boolean(place && work.client),
    retry: false,
    staleTime: 15_000,
  });
  const list = found.data;
  useEffect(() => {
    if (list && list.length > 0 && !list.some((w) => w.id === chosen)) work.pickWorkspace(list[0]!.id);
  }, [list, chosen, work]);
  const workspace = list?.find((w) => w.id === chosen);
  return { ...found, list: list ?? [], workspace };
}

/** A panel's contents once the machine has a workspace to read; else why there is nothing to show. */
export function Ready({ children }: { children: (client: WorkClient, workspace: Workspace) => ReactNode }) {
  const work = useWorkActions();
  const { workspace, error, isPending, list } = useWorkspaces();
  if (error)
    return (
      <div className="empty">
        <b>This machine could not be read</b>
        <p>{error.message}</p>
        <button type="button" className="btn wk-again" onClick={work.refresh}>
          Try again
        </button>
      </div>
    );
  if (isPending) return <p className="dim pad">Reading the machine…</p>;
  if (!work.client || list.length === 0)
    return (
      <div className="empty">
        <b>Nothing here yet</b>
        <p>The crew has not worked in a repository on this machine yet.</p>
      </div>
    );
  if (!workspace) return <p className="dim pad">Reading the machine…</p>;
  return <>{children(work.client, workspace)}</>;
}

/** Which of the machine's repositories the panels read, when there is more than one. */
export function WorkspacePick() {
  const work = useWorkActions();
  const { list, workspace } = useWorkspaces();
  if (list.length < 2 || !workspace) return null;
  return (
    <select className="wk-pick" aria-label="Repository" value={workspace.id} onChange={(e) => work.pickWorkspace(e.target.value)}>
      {list.map((w) => (
        <option key={w.id} value={w.id}>
          {w.name}
        </option>
      ))}
    </select>
  );
}
