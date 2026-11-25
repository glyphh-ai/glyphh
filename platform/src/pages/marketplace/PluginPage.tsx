import type { ReactNode } from 'react';
import { Link, useParams } from 'react-router';
import { ADD_MARKETPLACE, contents, MARKETPLACE_REPO, MARKETPLACE_URL, useMarketplace, type MarketItem, type Marketplace, type MarketPlugin, type MarketSkill } from '@/api/marketplace';
import { Markdown } from '@/components/Markdown';
import { Card, Chip, CodeBlock, EmptyState, Icon, LoadingCard } from '@/ui';
import { GitHubLink } from './MarketplacePage';
import styles from './marketplace.module.css';

const Back = () => (
  <Link to="/marketplace" className={styles.back}>
    <Icon name="arrowLeft" size={14} />
    Marketplace
  </Link>
);

/** One plugin of the Marketplace: what it is, how to install it in Claude, and everything it holds. */
export function PluginPage() {
  const { plugin: name = '' } = useParams();
  const market = useMarketplace();
  const plugin = market.data?.plugins.find((p) => p.name === name);

  return (
    <>
      <Back />
      {market.isPending && <LoadingCard lines={5} />}
      {market.isError && (
        <EmptyState icon="external" title="The marketplace could not be loaded">
          It is still there. <a href={MARKETPLACE_URL}>Open it on GitHub</a>
        </EmptyState>
      )}
      {market.data && !plugin && (
        <EmptyState icon="search" title="No such plugin">
          The marketplace has no plugin named “{name}”. <Link to="/marketplace">See them all</Link>
        </EmptyState>
      )}
      {market.data && plugin && <Plugin plugin={plugin} market={market.data} />}
    </>
  );
}

function Plugin({ plugin, market }: { plugin: MarketPlugin; market: Marketplace }) {
  const held = contents(plugin);
  const facts = [plugin.author && `by ${plugin.author.name}`, plugin.version && `v${plugin.version.replace(/^v/i, '')}`, plugin.license].filter(Boolean);
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.headerText}>
          <h1 className={styles.title}>{plugin.name}</h1>
          {facts.length > 0 && <p className={styles.facts}>{facts.join(' · ')}</p>}
          {plugin.description && <p className={styles.lead}>{plugin.description}</p>}
          {(plugin.category || plugin.keywords.length > 0 || held.length > 0) && (
            <div className={styles.chips}>
              {plugin.category && <Chip tone="violet">{plugin.category}</Chip>}
              {held.map((kind) => (
                <Chip key={kind.label}>{`${kind.count} ${kind.label}`}</Chip>
              ))}
              {plugin.keywords.map((word) => (
                <Chip key={word}>{word}</Chip>
              ))}
            </div>
          )}
        </div>
        <GitHubLink href={plugin.url}>View on GitHub</GitHubLink>
      </header>

      <Card aria-label="Install in Claude">
        <h2 className={styles.sectionTitle}>Install in Claude</h2>
        <ol className={styles.steps}>
          <li>
            <span className={styles.step}>In Claude Code, add the marketplace.</span>
            <CodeBlock code={ADD_MARKETPLACE} label="the line that adds the marketplace" />
          </li>
          <li>
            <span className={styles.step}>Then install the plugin.</span>
            <CodeBlock code={`/plugin install ${plugin.name}@${market.name}`} label="the line that installs the plugin" />
          </li>
        </ol>
        <p className={styles.note}>
          In the Claude desktop app, add it under Customize → Plugins → Add marketplace → <span className={styles.mono}>{MARKETPLACE_REPO}</span>.
        </p>
      </Card>

      {plugin.external && <p className={styles.note}>This plugin is kept in its own repository, so what it holds is listed there.</p>}

      <Items title="Skills" items={plugin.skills} render={(skill) => <Skill skill={skill} />} />
      <Items title="Commands" items={plugin.commands} render={(command) => <Item item={command} name={`/${command.name.replace(/^\//, '')}`} />} />
      <Items title="Agents" items={plugin.agents} render={(agent) => <Item item={agent} name={agent.name} />} />
      <Items title="Connectors" items={plugin.connectors} render={(connector) => <Item item={connector} name={connector.name} />} />

      {plugin.readme && (
        <section aria-labelledby="about" className={styles.section}>
          <h2 id="about" className={styles.sectionTitle}>
            About
          </h2>
          <Card>
            <Markdown text={plugin.readme} label="About this plugin" />
          </Card>
        </section>
      )}
    </div>
  );
}

/** One kind of thing a plugin holds, as a list; nothing when it holds none. */
function Items<T extends MarketItem>({ title, items, render }: { title: string; items: T[]; render: (item: T) => ReactNode }) {
  if (items.length === 0) return null;
  const id = `plugin-${title.toLowerCase()}`;
  return (
    <section aria-labelledby={id} className={styles.section}>
      <h2 id={id} className={styles.sectionTitle}>
        {title} <span className={styles.count}>{items.length}</span>
      </h2>
      <ul className={styles.items} aria-label={title}>
        {items.map((item) => (
          <li key={item.name} className={styles.item}>
            {render(item)}
          </li>
        ))}
      </ul>
    </section>
  );
}

const Source = ({ item }: { item: MarketItem }) => (
  <a href={item.url} className={styles.source} target="_blank" rel="noreferrer noopener" aria-label={`${item.name} on GitHub`}>
    <Icon name="external" size={14} />
  </a>
);

function Item({ item, name }: { item: MarketItem; name: string }) {
  return (
    <div className={styles.itemHead}>
      <div className={styles.itemText}>
        <span className={styles.itemName}>{name}</span>
        {item.description && <span className={styles.itemAbout}>{item.description}</span>}
      </div>
      <Source item={item} />
    </div>
  );
}

/** A skill: its name and what it is for, and its instructions to open. */
function Skill({ skill }: { skill: MarketSkill }) {
  if (!skill.body) return <Item item={skill} name={skill.name} />;
  return (
    <details className={styles.skill}>
      <summary className={styles.itemHead}>
        <span className={styles.chevron}>
          <Icon name="chevronRight" size={14} />
        </span>
        <span className={styles.itemText}>
          <span className={styles.itemName}>{skill.name}</span>
          {skill.description && <span className={styles.itemAbout}>{skill.description}</span>}
        </span>
        <Source item={skill} />
      </summary>
      <div className={styles.skillBody}>
        <Markdown text={skill.body} label={`${skill.name} instructions`} />
      </div>
    </details>
  );
}
