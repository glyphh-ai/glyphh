import { useMutation, useQuery } from '@tanstack/react-query';
import { api, ApiError } from './client';

/**
 * The Glyphh GitHub App on the person's own GitHub account (the server's /v1/github): the crew's turns commit and
 * open pull requests through it, with a token the server mints for that turn and that repo alone. Installing it goes
 * through the browser: `POST /github/install` answers a link to open, GitHub asks which repos, and the server records
 * the installation. No GitHub token is ever typed or kept here.
 */
export type GitHubRepo = { full_name: string; url: string; private: boolean; default_branch: string };
/** The repos the person's installation covers; no installation yet: an empty `account_login` and no repos. */
export type GitHubRepos = { account_login: string; manage_url: string; repos: GitHubRepo[] };
export type GitHubBranches = { default_branch: string; branches: string[] };

export const githubKeys = {
  all: ['github'] as const,
  repos: ['github', 'repos'] as const,
  branches: (repo: string) => ['github', 'branches', repo] as const,
};

export const useGitHubRepos = (enabled = true) => useQuery({ queryKey: githubKeys.repos, enabled, queryFn: () => api.get<GitHubRepos>('/github/repos') });
/** A repo's branches (`owner/name`), asked for only while there is a repo to ask about. */
export const useGitHubBranches = (repo: string | undefined, enabled = true) =>
  useQuery({
    queryKey: githubKeys.branches(repo ?? ''),
    enabled: enabled && Boolean(repo),
    retry: false,
    staleTime: 60_000,
    queryFn: () => api.get<GitHubBranches>(`/github/repos/${repo!.split('/').map(encodeURIComponent).join('/')}/branches`),
  });
/** A link to GitHub's install page for the App, good for ten minutes. */
export const useGitHubInstallLink = () => useMutation({ mutationFn: async () => (await api.post<{ url: string }>('/github/install')).url });

/** A refusal that Connect GitHub answers: the App is not on that repo (`github_app_missing`). The link the server sent with it. */
export function installUrl(error: unknown): string | undefined {
  if (!(error instanceof ApiError)) return undefined;
  const { reason, install_url: url } = error.detail;
  return reason === 'github_app_missing' && typeof url === 'string' ? url : undefined;
}
