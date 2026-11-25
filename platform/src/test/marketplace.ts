import type { Marketplace, MarketPlugin } from '@/api/marketplace';

/** The Marketplace as `GET /api/marketplace` answers it, for the page tests and the local fake. */

const repo = 'https://github.com/glyphh-ai/plugins';

export const resumeScreener: MarketPlugin = {
  name: 'resume-screener',
  description: 'Screens résumés against a role the way your team has decided before.',
  version: '1.2.0',
  author: { name: 'Glyphh', url: 'https://glyphh.ai' },
  category: 'recruiting',
  keywords: ['hiring', 'ada'],
  license: 'MIT',
  homepage: null,
  url: `${repo}/tree/HEAD/plugins/resume-screener`,
  external: false,
  readme: '# Resume screener\n\nReads each résumé and asks **Ada** what your team decided for ones like it.\n\n- Works from a folder\n- [Docs](https://docs.glyphh.ai)\n\n<script>alert(1)</script>',
  skills: [
    {
      name: 'screen-resume',
      description: 'Use when someone asks to screen a résumé for a role.',
      url: `${repo}/blob/HEAD/plugins/resume-screener/skills/screen-resume/SKILL.md`,
      body: '## Steps\n\n1. Read the résumé.\n2. Ask Ada.',
    },
    {
      name: 'explain-decision',
      description: 'Use to say why a résumé was passed or held.',
      url: `${repo}/blob/HEAD/plugins/resume-screener/skills/explain-decision/SKILL.md`,
      body: '',
    },
  ],
  commands: [{ name: 'screen', description: 'Screen the résumés in a folder.', url: `${repo}/blob/HEAD/plugins/resume-screener/commands/screen.md` }],
  agents: [{ name: 'screener', description: 'Works through a stack of résumés.', url: `${repo}/blob/HEAD/plugins/resume-screener/agents/screener.md` }],
  hooks: ['SessionStart'],
  connectors: [{ name: 'glyphh', description: '', url: `${repo}/blob/HEAD/plugins/resume-screener/.mcp.json` }],
};

/** A plugin kept in its own repository: known from the marketplace's list alone. */
export const elsewhere: MarketPlugin = {
  name: 'ticket-router',
  description: 'Routes support tickets to the queue that took ones like them.',
  version: null,
  author: { name: 'Acme', url: null },
  category: null,
  keywords: [],
  license: null,
  homepage: null,
  url: 'https://github.com/acme/ticket-router',
  external: true,
  readme: null,
  skills: [],
  commands: [],
  agents: [],
  hooks: [],
  connectors: [],
};

export const marketplace = (plugins: MarketPlugin[] = [resumeScreener, elsewhere]): Marketplace => ({
  name: 'glyphh',
  owner: 'Glyphh',
  description: 'Plugins for Claude from Glyphh.',
  version: '1.0.0',
  repo: 'glyphh-ai/plugins',
  url: repo,
  plugins,
  fetched_at: '2026-11-24T09:00:00.000Z',
  stale: false,
});

/** Thirty plugins, "plugin-1" to "plugin-30", for the pages. */
export const manyPlugins: MarketPlugin[] = Array.from({ length: 30 }, (_, i) => ({
  ...elsewhere,
  name: `plugin-${i + 1}`,
  description: `Plugin number ${i + 1}.`,
}));
