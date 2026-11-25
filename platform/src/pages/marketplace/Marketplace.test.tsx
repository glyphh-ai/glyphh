import { screen, waitFor, within } from '@testing-library/react';
import { blocks } from '@/components/Markdown';
import { manyPlugins, marketplace, resumeScreener } from '@/test/marketplace';
import { renderApp } from '@/test/render';
import { apiError, http, marketplaceHandler, server } from '@/test/server';

const repo = 'https://github.com/glyphh-ai/plugins';
const cards = () => within(screen.getByRole('list', { name: 'Plugins' })).getAllByRole('link');

describe('The Marketplace', () => {
  it('is one entry in the sidebar, and shows a card per plugin with who made it, what it holds and its version', async () => {
    renderApp('/marketplace');
    expect(await screen.findByRole('heading', { name: 'Marketplace', level: 1 })).toBeInTheDocument();
    const rail = screen.getByRole('complementary', { name: 'Main' });
    expect(await within(rail).findAllByRole('link', { name: 'Marketplace' })).toHaveLength(1);
    expect(screen.getByRole('link', { name: 'View on GitHub' })).toHaveAttribute('href', repo);

    const card = await screen.findByRole('link', { name: 'resume-screener' });
    expect(card).toHaveAttribute('href', '/marketplace/resume-screener');
    expect(within(card).getByText('by Glyphh')).toBeInTheDocument();
    expect(within(card).getByText('Screens résumés against a role the way your team has decided before.')).toBeInTheDocument();
    for (const chip of ['2 Skills', '1 Command', '1 Agent', '1 Hook', '1 Connector']) expect(within(card).getByText(chip)).toBeInTheDocument();
    expect(within(card).getByText('v1.2.0')).toBeInTheDocument();

    // A plugin kept elsewhere: its name, its maker and its words, with nothing counted.
    const other = screen.getByRole('link', { name: 'ticket-router' });
    expect(within(other).getByText('by Acme')).toBeInTheDocument();
    expect(within(other).queryByText(/Skill|Connector/)).not.toBeInTheDocument();
  });

  it('searches by a plugin’s name, its words or anything it holds, with the query in the URL', async () => {
    const { user, router } = renderApp('/marketplace');
    await screen.findByRole('link', { name: 'resume-screener' });
    expect(cards()).toHaveLength(2);
    await user.type(screen.getByRole('searchbox', { name: 'Search' }), 'explain-decision');
    await waitFor(() => expect(cards()).toHaveLength(1));
    expect(cards()[0]).toHaveAccessibleName('resume-screener');
    await waitFor(() => expect(router.state.location.search).toBe('?q=explain-decision'));
    await user.clear(screen.getByRole('searchbox', { name: 'Search' }));
    await user.type(screen.getByRole('searchbox', { name: 'Search' }), 'nothing like it');
    expect(await screen.findByText('Nothing matches')).toBeInTheDocument();
  });

  it('pages a long list', async () => {
    server.use(marketplaceHandler(marketplace(manyPlugins)));
    const { user } = renderApp('/marketplace');
    await screen.findByRole('link', { name: 'plugin-1' });
    expect(cards()).toHaveLength(24);
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(cards()).toHaveLength(6));
  });

  it('says it is being stocked while the repository is empty, with the way to add it to Claude and no alarm', async () => {
    server.use(marketplaceHandler(marketplace([])));
    renderApp('/marketplace');
    expect(await screen.findByRole('heading', { name: 'The marketplace is being stocked' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'github.com/glyphh-ai/plugins' })).toHaveAttribute('href', repo);
    expect(screen.getByText('/plugin marketplace add glyphh-ai/plugins')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy the line that adds the marketplace' })).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument();
  });

  it('says quietly when it could not be loaded, with the way to GitHub', async () => {
    server.use(http.get('*/api/marketplace', () => apiError(502, 'E_MARKETPLACE', 'The marketplace could not be loaded from GitHub.')));
    renderApp('/marketplace');
    expect(await screen.findByRole('heading', { name: 'The marketplace could not be loaded' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open it on GitHub' })).toHaveAttribute('href', repo);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('uses none of the words kept off Glyphh’s screens, in any state', async () => {
    for (const answer of [marketplace([{ ...resumeScreener, description: '', readme: null, skills: [], keywords: [] }]), marketplace([])]) {
      server.use(marketplaceHandler(answer));
      const { unmount } = renderApp('/marketplace');
      await screen.findByRole('heading', { name: 'Marketplace', level: 1 });
      await waitFor(() => expect(screen.queryByLabelText('Loading')).not.toBeInTheDocument());
      expect(screen.getByRole('main')).not.toHaveTextContent(/\b(bots?|loops?|gates?|json|engines?)\b|coming soon/i);
      unmount();
    }
  });
});

describe('A plugin’s page', () => {
  it('opens from its card, with its name in the breadcrumb, who made it, its version and its keywords', async () => {
    const { user, router } = renderApp('/marketplace');
    await user.click(await screen.findByRole('link', { name: 'resume-screener' }));
    expect(await screen.findByRole('heading', { name: 'resume-screener', level: 1 })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/marketplace/resume-screener');
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent('Marketplaceresume-screener');
    expect(screen.getByText('by Glyphh · v1.2.0 · MIT')).toBeInTheDocument();
    for (const chip of ['recruiting', 'hiring', 'ada']) expect(screen.getByText(chip)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'View on GitHub' })).toHaveAttribute('href', `${repo}/tree/HEAD/plugins/resume-screener`);
  });

  it('says how to install it in Claude, each line to copy, with the marketplace’s own name', async () => {
    renderApp('/marketplace/resume-screener');
    const install = await screen.findByRole('region', { name: 'Install in Claude' });
    expect(within(install).getByText('/plugin marketplace add glyphh-ai/plugins')).toBeInTheDocument();
    expect(within(install).getByText('/plugin install resume-screener@glyphh')).toBeInTheDocument();
    expect(within(install).getByRole('button', { name: 'Copy the line that adds the marketplace' })).toBeInTheDocument();
    expect(within(install).getByRole('button', { name: 'Copy the line that installs the plugin' })).toBeInTheDocument();
    expect(install).toHaveTextContent('In the Claude desktop app, add it under Customize → Plugins → Add marketplace → glyphh-ai/plugins.');
  });

  it('lists its skills, commands, agents and connectors, each with a link to its file', async () => {
    const { user } = renderApp('/marketplace/resume-screener');
    const skills = await screen.findByRole('list', { name: 'Skills' });
    expect([...skills.children].map((li) => li.querySelector('span[class*="itemName"]')?.textContent)).toEqual(['screen-resume', 'explain-decision']);
    expect(within(skills).getByText('Use when someone asks to screen a résumé for a role.')).toBeInTheDocument();
    expect(within(skills).getByRole('link', { name: 'screen-resume on GitHub' })).toHaveAttribute('href', `${repo}/blob/HEAD/plugins/resume-screener/skills/screen-resume/SKILL.md`);

    // A skill opens to its instructions.
    const body = within(skills).getByLabelText('screen-resume instructions');
    expect(body.closest('details')).not.toHaveAttribute('open');
    await user.click(within(skills).getByText('screen-resume'));
    expect(body.closest('details')).toHaveAttribute('open');
    expect(within(body).getByText('Read the résumé.')).toBeInTheDocument();

    expect(within(screen.getByRole('list', { name: 'Commands' })).getByText('/screen')).toBeInTheDocument();
    expect(within(screen.getByRole('list', { name: 'Agents' })).getByText('Works through a stack of résumés.')).toBeInTheDocument();
    const connectors = screen.getByRole('list', { name: 'Connectors' });
    expect(within(connectors).getByText('glyphh')).toBeInTheDocument();
    expect(within(connectors).getByRole('link', { name: 'glyphh on GitHub' })).toHaveAttribute('href', `${repo}/blob/HEAD/plugins/resume-screener/.mcp.json`);
  });

  it('shows its README as text: its markup read, and nothing in it run', async () => {
    renderApp('/marketplace/resume-screener');
    const about = await screen.findByLabelText('About this plugin');
    expect(within(about).getByRole('heading', { name: 'Resume screener' })).toBeInTheDocument();
    expect(within(about).getByText('Ada').tagName).toBe('STRONG');
    expect(within(about).getByRole('link', { name: 'Docs' })).toHaveAttribute('href', 'https://docs.glyphh.ai');
    // A tag in the file is the characters it is.
    expect(about.querySelector('script')).toBeNull();
    expect(within(about).getByText('<script>alert(1)</script>')).toBeInTheDocument();
  });

  it('shows a plugin kept elsewhere from what the list says of it, with a link to its own repository', async () => {
    renderApp('/marketplace/ticket-router');
    expect(await screen.findByRole('heading', { name: 'ticket-router', level: 1 })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'View on GitHub' })).toHaveAttribute('href', 'https://github.com/acme/ticket-router');
    expect(screen.getByText('/plugin install ticket-router@glyphh')).toBeInTheDocument();
    expect(screen.getByText(/kept in its own repository/)).toBeInTheDocument();
    for (const name of ['Skills', 'Commands', 'Agents', 'Connectors']) expect(screen.queryByRole('list', { name })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'About' })).not.toBeInTheDocument();
  });

  it('says when there is no such plugin, and when the marketplace could not be loaded', async () => {
    const first = renderApp('/marketplace/nope');
    expect(await screen.findByRole('heading', { name: 'No such plugin' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'See them all' })).toHaveAttribute('href', '/marketplace');
    first.unmount();

    server.use(http.get('*/api/marketplace', () => apiError(502, 'E_MARKETPLACE', 'The marketplace could not be loaded from GitHub.')));
    renderApp('/marketplace/resume-screener');
    expect(await screen.findByRole('link', { name: 'Open it on GitHub' })).toHaveAttribute('href', repo);
  });
});

describe('Markdown', () => {
  it('reads headings, lists, tables, code, quotes and rules, and drops comments', () => {
    const text = ['# Title', '<!-- note -->', 'One', 'two', '', '- a', '  more', '- b', '', '1. x', '', '| A | B |', '|---|---|', '| 1 | 2 |', '', '```sh', '# not a heading', '```', '> said', '---'].join('\n');
    expect(blocks(text).map((b) => [b.kind, b.lines.join('/')])).toEqual([
      ['h', 'Title'],
      ['p', 'One/two'],
      ['ul', 'a more/b'],
      ['ol', 'x'],
      ['table', '| A | B |/| 1 | 2 |'],
      ['code', '# not a heading'],
      ['quote', 'said'],
      ['rule', ''],
    ]);
  });
});
