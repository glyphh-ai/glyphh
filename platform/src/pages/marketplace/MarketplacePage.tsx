import { Link } from 'react-router';
import { ADD_MARKETPLACE, contents, MARKETPLACE_REPO, MARKETPLACE_URL, useMarketplace, type MarketPlugin } from '@/api/marketplace';
import { NoMatch, Pager, SearchField, useSearchPaging } from '@/components/SearchPaged';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { ButtonLink, Chip, CodeBlock, EmptyState, Icon, LoadingCard } from '@/ui';
import styles from './marketplace.module.css';

/** Whether a plugin fits what was typed: its name, what it says of itself, who made it, or anything it holds. */
const matches = (plugin: MarketPlugin, q: string) =>
  [
    plugin.name,
    plugin.description,
    plugin.author?.name,
    plugin.category,
    ...plugin.keywords,
    ...[...plugin.skills, ...plugin.commands, ...plugin.agents, ...plugin.connectors].map((item) => item.name),
  ].some((value) => value?.toLowerCase().includes(q));

/** A link out to GitHub, opened beside the platform. */
export function GitHubLink({ href, children }: { href: string; children: string }) {
  return (
    <ButtonLink href={href} target="_blank" rel="noreferrer noopener">
      <Icon name="github" size={16} />
      {children}
    </ButtonLink>
  );
}

/**
 * The Marketplace: the plugins in github.com/glyphh-ai/plugins, shown as Claude's own plugin browser shows them. A
 * search and a card each; a plugin is installed in Claude, never here.
 */
export function MarketplacePage() {
  const market = useMarketplace();
  const paged = useSearchPaging(market.data?.plugins, matches);
  const plugins = market.data?.plugins;

  return (
    <>
      <PageHeader
        title="Marketplace"
        description="Plugins for Claude: skills, commands and connectors that put Ada to work. Install them in Claude."
        actions={<GitHubLink href={market.data?.url ?? MARKETPLACE_URL}>View on GitHub</GitHubLink>}
      />

      {market.isPending && <LoadingCard lines={4} />}

      {market.isError && (
        <EmptyState icon="external" title="The marketplace could not be loaded">
          It is still there. <a href={MARKETPLACE_URL}>Open it on GitHub</a>
        </EmptyState>
      )}

      {plugins?.length === 0 && (
        <EmptyState
          icon="layers"
          title="The marketplace is being stocked"
          action={
            <div className={styles.emptyStep}>
              <CodeBlock code={ADD_MARKETPLACE} label="the line that adds the marketplace" />
            </div>
          }
        >
          Nothing is published yet. It lives at <a href={MARKETPLACE_URL}>github.com/{MARKETPLACE_REPO}</a>, and you can add it to Claude Code with this line.
        </EmptyState>
      )}

      {plugins && plugins.length > 0 && (
        <>
          <SearchField typed={paged.typed} onChange={paged.setTyped} placeholder="Plugin, skill or author" />
          {paged.total === 0 && <NoMatch q={paged.q} noun="plugin" />}
          <ul className={styles.grid} aria-label="Plugins">
            {paged.shown.map((plugin) => (
              <li key={plugin.name}>
                <PluginCard plugin={plugin} />
              </li>
            ))}
          </ul>
          <Pager page={paged.page} total={paged.total} from={paged.from} to={paged.to} last={paged.last} onPage={paged.setPage} />
        </>
      )}
    </>
  );
}

/** One plugin: its name, who made it, what it does, and what it holds. The whole card opens it. */
function PluginCard({ plugin }: { plugin: MarketPlugin }) {
  const held = contents(plugin);
  return (
    <Link to={`/marketplace/${encodeURIComponent(plugin.name)}`} className={styles.card} aria-label={plugin.name}>
      <span className={styles.cardHead}>
        <span className={styles.cardIcon}>
          <Icon name="layers" size={18} />
        </span>
        <span className={styles.cardTitle}>
          <span className={styles.name}>{plugin.name}</span>
          {plugin.author && <span className={styles.by}>by {plugin.author.name}</span>}
        </span>
      </span>
      {plugin.description && <span className={styles.description}>{plugin.description}</span>}
      <span className={styles.cardFoot}>
        <span className={styles.chips}>
          {held.map((kind) => (
            <Chip key={kind.label}>{`${kind.count} ${kind.label}`}</Chip>
          ))}
        </span>
        {plugin.version && <span className={styles.version}>v{plugin.version.replace(/^v/i, '')}</span>}
      </span>
    </Link>
  );
}
