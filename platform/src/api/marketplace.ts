import { useQuery } from '@tanstack/react-query';
import { request } from './client';

/**
 * The Marketplace: what is in the public repository github.com/glyphh-ai/plugins, as the platform's own route
 * handler read it (`GET /api/marketplace`, server/marketplace.ts). The browser never calls GitHub.
 */
export type MarketItem = { name: string; description: string; url: string };
export type MarketSkill = MarketItem & { body: string };
export type MarketPlugin = {
  name: string;
  description: string;
  version: string | null;
  author: { name: string; url: string | null } | null;
  category: string | null;
  keywords: string[];
  license: string | null;
  homepage: string | null;
  /** The plugin's folder in the repository, or its own repository when it lives elsewhere. */
  url: string;
  external: boolean;
  readme: string | null;
  skills: MarketSkill[];
  commands: MarketItem[];
  agents: MarketItem[];
  hooks: string[];
  /** Its MCP servers, by name. */
  connectors: MarketItem[];
};
export type Marketplace = {
  /** The marketplace's name, as `/plugin install <plugin>@<name>` takes it. */
  name: string;
  owner: string | null;
  description: string | null;
  version: string | null;
  repo: string;
  url: string;
  plugins: MarketPlugin[];
  fetched_at: string;
  stale: boolean;
};

/** Where the marketplace is, for the links a page shows before (or without) an answer. */
export const MARKETPLACE_REPO = 'glyphh-ai/plugins';
export const MARKETPLACE_URL = `https://github.com/${MARKETPLACE_REPO}`;
/** The line that adds the marketplace in Claude Code. */
export const ADD_MARKETPLACE = `/plugin marketplace add ${MARKETPLACE_REPO}`;

export const useMarketplace = () =>
  useQuery({
    queryKey: ['marketplace'],
    queryFn: () => request<Marketplace>('GET', '/marketplace', undefined, '/api'),
    // The route handler keeps its answer ten minutes; asking it more often changes nothing.
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

/** What a plugin holds, in the order it is shown: the name of each kind and how many. */
export function contents(plugin: MarketPlugin): Array<{ label: string; count: number }> {
  const all = [
    { one: 'Skill', many: 'Skills', count: plugin.skills.length },
    { one: 'Command', many: 'Commands', count: plugin.commands.length },
    { one: 'Agent', many: 'Agents', count: plugin.agents.length },
    { one: 'Hook', many: 'Hooks', count: plugin.hooks.length },
    { one: 'Connector', many: 'Connectors', count: plugin.connectors.length },
  ];
  return all.filter((kind) => kind.count > 0).map((kind) => ({ label: kind.count === 1 ? kind.one : kind.many, count: kind.count }));
}
