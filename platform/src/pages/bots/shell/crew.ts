// The crew is state, not a place to go: which bots are ticked, how they work together, and the workspace (a GitHub
// repo and branch) they work in. The server keeps one record per workspace and is asked for it silently
// (`PUT /projects/crew`); until a workspace is chosen, the ticks and settings are kept here in the browser and are
// sent with the first workspace picked. Nothing here is ever named or listed for the person.
import { useCallback, useMemo, useState } from 'react';
import type { Bot } from '@/api/bots';
import { repoName, useProjects, useSetCrew, type CrewSettings, type Effort, type Project } from '@/api/projects';

const KEY = 'glyphh.bots.crew';
/** The most bots the server takes in one crew. */
export const CREW_MAX = 8;

const FIRST: CrewSettings = { runs_on: null, turn_mode: 'wait', orchestrator: null, review: 'each_turn', narrate: false, max_turns: 30, max_spend_cents: null };

type Kept = {
  /** The workspace last used (the server's slug for it). */
  workspace?: string;
  /** The ticked bots' ids, before there is a workspace; none: every bot. */
  members?: string[];
  settings?: Partial<CrewSettings>;
  /** The composer's pills for the crew's next run; none: each bot's own. */
  model?: string | null;
  effort?: Effort | null;
};

function read(): Kept {
  try {
    const kept = JSON.parse(localStorage.getItem(KEY) ?? '{}') as unknown;
    return kept && typeof kept === 'object' ? (kept as Kept) : {};
  } catch {
    return {};
  }
}

const settingsOf = (p: Project): CrewSettings => ({
  runs_on: p.runs_on,
  turn_mode: p.turn_mode,
  orchestrator: p.orchestrator,
  review: p.review,
  narrate: p.narrate,
  max_turns: p.max_turns,
  max_spend_cents: p.max_spend_cents,
});

export type Workspace = { slug: string; repo: string; branch: string; url: string };
const workspaceOf = (p: Project): Workspace => ({ slug: p.slug, repo: repoName(p.repo_url), branch: p.base_branch, url: p.repo_url });

export type Crew = ReturnType<typeof useCrew>;

export function useCrew(bots: Bot[] | undefined) {
  const projects = useProjects();
  const put = useSetCrew();
  const [kept, setKept] = useState<Kept>(read);
  const keep = useCallback((change: Kept) => {
    setKept((was) => {
      const next = { ...was, ...change };
      try {
        localStorage.setItem(KEY, JSON.stringify(next));
      } catch {
        // A browser that keeps nothing: the choice lasts for this visit.
      }
      return next;
    });
  }, []);

  const all = projects.data;
  // The workspace: the one last used, else the one changed last.
  const project = useMemo(() => all?.find((p) => p.slug === kept.workspace) ?? [...(all ?? [])].sort((a, b) => b.updated_at.localeCompare(a.updated_at))[0], [all, kept.workspace]);
  const everyone = useMemo(() => (bots ?? []).slice(0, CREW_MAX).map((b) => b.id), [bots]);
  const known = new Set((bots ?? []).map((b) => b.id));
  const members = (project ? project.members.map((m) => m.id) : (kept.members ?? everyone)).filter((id) => bots === undefined || known.has(id));
  const settings: CrewSettings = project ? settingsOf(project) : { ...FIRST, ...kept.settings };

  /** Sends the crew as it should be now; with no workspace yet it is only kept. */
  const save = (next: { members?: string[]; settings?: Partial<CrewSettings> }, done?: () => void) => {
    const ids = next.members ?? members;
    if (!project) {
      keep({ members: ids, settings: { ...kept.settings, ...next.settings } });
      done?.();
      return;
    }
    put.mutate({ repo: repoName(project.repo_url), branch: project.base_branch, members: ids, ...next.settings }, { onSuccess: done });
  };

  return {
    ready: !projects.isPending,
    /** The server's record of the crew in this workspace; none before one is chosen. */
    project,
    workspace: project ? workspaceOf(project) : undefined,
    /** The workspaces used before, newest first. */
    workspaces: [...(all ?? [])].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).map(workspaceOf),
    members,
    settings,
    model: kept.model ?? null,
    effort: kept.effort ?? null,
    pending: put.isPending,
    error: put.error ?? projects.error,
    /** A bot ticked in or out; the last one stays. */
    toggle: (id: string) => {
      const next = members.includes(id) ? members.filter((x) => x !== id) : [...members, id];
      if (next.length === 0 || next.length > CREW_MAX) return;
      const settingsNext = settings.orchestrator && !next.includes(settings.orchestrator) ? { orchestrator: null } : undefined;
      save({ members: next, settings: settingsNext });
    },
    save,
    /** A workspace used before. */
    open: (slug: string) => keep({ workspace: slug }),
    /** A repo (`owner/name`) and branch to work in: the crew as it is now goes with it. */
    choose: (repo: string, branch: string | undefined, done?: () => void) =>
      put.mutate(
        { repo, branch, members: members.length ? members : everyone, ...settings },
        {
          onSuccess: (p) => {
            keep({ workspace: p.slug });
            done?.();
          },
        },
      ),
    setRun: (change: { model?: string | null; effort?: Effort | null }) => keep(change),
    reset: put.reset,
  };
}
