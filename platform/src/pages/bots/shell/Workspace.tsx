// The top bar's workspace pill (glyphh-bot App.tsx, the folder chip): the GitHub repo and branch the crew works in.
// Its menu: the workspaces used before, Connect GitHub (Glyphh's GitHub App: sign in there and choose its repos; no
// token is ever pasted), a repo picker and a branch field.
import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { githubKeys, installUrl, useGitHubBranches, useGitHubInstallLink, useGitHubRepos } from '@/api/github';
import { useEscape } from './bits';
import type { Crew } from './crew';
import { Icon, ICON } from './icons';

/** GitHub's mark, drawn: one path, the colour of the words beside it. */
export function GitHubMark({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M8 0a8 8 0 0 0-2.53 15.59c.4.07.55-.17.55-.38v-1.33c-2.23.48-2.7-1.07-2.7-1.07-.36-.93-.89-1.17-.89-1.17-.73-.5.05-.49.05-.49.8.06 1.23.83 1.23.83.72 1.22 1.88.87 2.33.66.07-.52.28-.87.5-1.07-1.77-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.6 7.6 0 0 1 4 0c1.53-1.03 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.28.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48v2.19c0 .21.15.46.55.38A8 8 0 0 0 8 0Z" />
    </svg>
  );
}

/**
 * Opens GitHub's install page for the Glyphh App in a new tab. The tab is opened at the click (a browser blocks one
 * opened later) and sent on once the server answers the link; a refusal closes it and is said in place.
 */
function useConnectGitHub() {
  const link = useGitHubInstallLink();
  const open = () => {
    const tab = window.open('', '_blank');
    link.mutate(undefined, {
      onSuccess: (url) => {
        if (tab) {
          tab.opener = null;
          tab.location.href = url;
        } else window.location.assign(url);
      },
      onError: () => tab?.close(),
    });
  };
  return { open, pending: link.isPending, error: link.error };
}

/** Back from GitHub's tab: which repos the App is on is read again. */
function useRefreshOnReturn(on: boolean) {
  const client = useQueryClient();
  useEffect(() => {
    if (!on) return;
    const again = () => {
      if (!document.hidden) void client.invalidateQueries({ queryKey: githubKeys.all });
    };
    window.addEventListener('focus', again);
    return () => window.removeEventListener('focus', again);
  }, [client, on]);
}

const REPO = /^[\w.-]+\/[\w.-]+$/;

function Menu({ crew, onClose }: { crew: Crew; onClose: () => void }) {
  const repos = useGitHubRepos();
  const connect = useConnectGitHub();
  const here = crew.workspace;
  const branches = useGitHubBranches(here?.repo);
  const [q, setQ] = useState('');
  const [branch, setBranch] = useState(here?.branch ?? '');
  useRefreshOnReturn(true);
  useEffect(() => setBranch(here?.branch ?? ''), [here?.branch, here?.repo]);

  const connected = Boolean(repos.data?.account_login);
  const needle = q.trim().toLowerCase();
  const listed = (repos.data?.repos ?? []).filter((r) => r.full_name.toLowerCase().includes(needle));
  // A repo of an organisation is not in the person's own list: its owner/name can be typed.
  const typed = REPO.test(q.trim()) && !listed.some((r) => r.full_name.toLowerCase() === needle) ? q.trim() : '';
  const failed = crew.error ?? connect.error ?? repos.error;
  const install = installUrl(crew.error);
  const pick = (repo: string, at?: string) => {
    crew.reset();
    crew.choose(repo, at, onClose);
  };
  const setBranchNow = () => {
    const next = branch.trim();
    if (here && next && next !== here.branch) pick(here.repo, next);
  };

  return (
    <div className="menu wsmenu-panel" role="dialog" aria-label="Workspace">
      {crew.workspaces.length > 0 && (
        <>
          <div className="rlabel">Workspaces</div>
          {crew.workspaces.map((w) => (
            <button
              key={w.slug}
              type="button"
              className={w.slug === here?.slug ? 'on' : ''}
              aria-current={w.slug === here?.slug ? 'true' : undefined}
              onClick={() => {
                crew.open(w.slug);
                onClose();
              }}
            >
              <Icon d={ICON.folder} size={14} /> <span className="wsname">{w.repo}</span> <span className="branch">{w.branch}</span>
            </button>
          ))}
          <hr />
        </>
      )}

      <div className="rlabel">
        <GitHubMark size={11} /> GitHub
      </div>
      {repos.isPending ? (
        <p className="dim pad">Reading…</p>
      ) : !connected ? (
        <>
          <button type="button" className="btn primary wsconnect" disabled={connect.pending} onClick={connect.open}>
            <GitHubMark /> Connect GitHub
          </button>
          <p className="dim pad">Sign in to GitHub and choose the repositories the crew may work in. There is nothing to paste.</p>
        </>
      ) : (
        <>
          <p className="dim pad wsline">
            Connected as <b>{repos.data!.account_login}</b>
            {repos.data!.manage_url && (
              <a href={repos.data!.manage_url} target="_blank" rel="noreferrer">
                Change repositories
              </a>
            )}
          </p>
          <input aria-label="Find a repository" placeholder="Find a repository, or type owner/name" value={q} spellCheck={false} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && typed && pick(typed)} />
          <div className="wsrepos" role="listbox" aria-label="Repositories">
            {listed.map((r) => (
              <button key={r.full_name} type="button" role="option" aria-selected={r.full_name === here?.repo} className={r.full_name === here?.repo ? 'on' : ''} disabled={crew.pending} onClick={() => pick(r.full_name, r.default_branch)}>
                <span className="wsname">{r.full_name}</span>
                <span className="branch">{r.private ? 'private' : 'public'}</span>
              </button>
            ))}
            {typed && (
              <button type="button" role="option" aria-selected={false} disabled={crew.pending} onClick={() => pick(typed)}>
                <span className="wsname">Use {typed}</span>
              </button>
            )}
            {listed.length === 0 && !typed && <p className="dim pad">{needle ? 'No repository by that name.' : 'The App is on no repository yet: add one on GitHub.'}</p>}
          </div>
        </>
      )}

      {here && (
        <>
          <hr />
          <label className="wsbranch">
            <span className="rlabel">Branch</span>
            <span className="row">
              <input aria-label="Branch" list="ws-branches" value={branch} spellCheck={false} onChange={(e) => setBranch(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && setBranchNow()} />
              <button type="button" className="btn sm" disabled={crew.pending || !branch.trim() || branch.trim() === here.branch} onClick={setBranchNow}>
                Use
              </button>
            </span>
            <datalist id="ws-branches">
              {(branches.data?.branches ?? []).map((b) => (
                <option key={b} value={b} />
              ))}
            </datalist>
          </label>
        </>
      )}

      {failed && (
        <p className="err pad" role="alert">
          {failed.message}{' '}
          {install && (
            <a href={install} target="_blank" rel="noreferrer">
              Connect GitHub
            </a>
          )}
        </p>
      )}
    </div>
  );
}

export function WorkspacePill({ crew }: { crew: Crew }) {
  const [open, setOpen] = useState(false);
  useEscape(() => setOpen(false), open);
  const here = crew.workspace;
  return (
    <div className="wsmenu">
      <button type="button" className={`chip ${open ? 'on' : ''}`} title="The repository and branch the crew works in" aria-label="Workspace" aria-expanded={open} onClick={() => setOpen(!open)}>
        <Icon d={ICON.folder} size={14} />
        <span className="chiptext">{here ? here.repo.split('/').pop() : 'Choose a workspace'}</span>
        {here && <span className="branch">{here.branch}</span>}
      </button>
      {open && (
        <>
          <div className="veil clear" onMouseDown={() => setOpen(false)} />
          <Menu crew={crew} onClose={() => setOpen(false)} />
        </>
      )}
    </div>
  );
}
