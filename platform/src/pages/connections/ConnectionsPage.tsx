import { useMemo } from 'react';
import { Link, useSearchParams } from 'react-router';
import { connectionsOff, useConnections } from '@/api/bots';
import { byApp, useAppCatalog, type ConnectedApp } from '@/api/connections';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { useUrlSearch } from '@/components/SearchPaged';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { date } from '@/lib/format';
import { Button, EmptyState, Icon, Menu, MenuLabel, MenuRadioItem, Skeleton, Tabs, TextField } from '@/ui';
import { AppIcon } from './AppIcon';
import styles from './connections.module.css';

type View = 'yours' | 'catalog';
type Show = 'all' | 'connected' | 'not';
type Sort = 'name' | 'newest';
const TABS = [
  { id: 'yours', label: 'Yours' },
  { id: 'catalog', label: 'Catalog' },
] as const;
const SHOW: Record<Show, string> = { all: 'All apps', connected: 'Connected', not: 'Not connected' };
const SORT: Record<Sort, string> = { name: 'Name', newest: 'Recently connected' };

/** Rows standing in for what is loading, so nothing jumps when it lands. */
function Placeholders({ count }: { count: number }) {
  return (
    <>
      {Array.from({ length: count }, (_, i) => (
        <li key={i} className={styles.row} aria-hidden="true">
          <Skeleton height={32} width={32} />
          <div className={styles.rowText}>
            <Skeleton height={14} width="40%" />
            <Skeleton height={12} width="70%" />
          </div>
        </li>
      ))}
    </>
  );
}

function Yours({ apps, q, sort }: { apps: ConnectedApp[] | undefined; q: string; sort: Sort }) {
  const needle = q.trim().toLowerCase();
  const shown = useMemo(() => {
    const found = (apps ?? []).filter((a) => !needle || a.name.toLowerCase().includes(needle) || a.accounts.some((c) => c.label?.toLowerCase().includes(needle)));
    const newest = (a: ConnectedApp) => Math.max(...a.accounts.map((c) => Date.parse(c.created_at)));
    return sort === 'newest' ? [...found].sort((a, b) => newest(b) - newest(a)) : found;
  }, [apps, needle, sort]);

  if (apps === undefined)
    return (
      <ul className={styles.list} aria-busy="true" aria-label="Loading">
        <Placeholders count={4} />
      </ul>
    );
  if (apps.length === 0)
    return (
      <EmptyState
        icon="external"
        title="No connections yet"
        action={
          <Link to="?tab=catalog" className={styles.inlineLink}>
            Browse the catalog
          </Link>
        }
      >
        Connect an app, such as Gmail or Slack, for your bots to use.
      </EmptyState>
    );
  if (shown.length === 0)
    return (
      <EmptyState icon="search" title="Nothing matches">
        None of your connections matches “{q}”.
      </EmptyState>
    );
  return (
    <ul className={styles.list} aria-label="Your connections">
      {shown.map((a) => (
        <li key={a.app}>
          <Link to={`/connections/${encodeURIComponent(a.app)}`} className={styles.row}>
            <AppIcon icon={a.icon} name={a.name} />
            <div className={styles.rowText}>
              <span className={styles.rowName}>{a.name}</span>
              <span className={styles.muted}>
                {a.accounts.length === 1 ? (a.accounts[0]!.label ?? 'One account') : `${a.accounts.length} accounts`} · Connected {date(a.accounts[0]!.created_at)}
              </span>
            </div>
            <Icon name="chevronRight" size={16} />
          </Link>
        </li>
      ))}
    </ul>
  );
}

function Catalog({ q, show, connected }: { q: string; show: Show; connected: Set<string> }) {
  const catalog = useAppCatalog(q.trim());
  const apps = (catalog.data?.pages ?? []).flatMap((p) => p.apps).filter((a) => show === 'all' || (show === 'connected') === connected.has(a.slug));
  const nothing = !catalog.isPending && apps.length === 0;

  return (
    <>
      <ApiErrorNotice error={catalog.error} />
      {nothing && !catalog.error ? (
        <EmptyState icon="search" title="Nothing matches">
          {q ? `No app matches “${q}”.` : 'No app here.'}
        </EmptyState>
      ) : (
        <ul className={styles.grid} aria-label="Catalog" aria-busy={catalog.isFetching || undefined}>
          {apps.map((a) => (
            <li key={a.slug}>
              <Link to={`/connections/${encodeURIComponent(a.slug)}`} state={{ app: a }} className={styles.row}>
                <AppIcon icon={a.icon} name={a.name} />
                <div className={styles.rowText}>
                  <span className={styles.rowName}>
                    {a.name}
                    {connected.has(a.slug) && (
                      <span className={styles.added}>
                        <Icon name="check" size={12} /> Added
                      </span>
                    )}
                  </span>
                  <span className={styles.oneLine}>{a.description || 'Connector'}</span>
                </div>
              </Link>
            </li>
          ))}
          {(catalog.isPending || catalog.isFetchingNextPage) && <Placeholders count={6} />}
        </ul>
      )}
      {catalog.hasNextPage && (
        <div className={styles.more}>
          <Button onClick={() => catalog.fetchNextPage()} loading={catalog.isFetchingNextPage}>
            Show more
          </Button>
        </div>
      )}
    </>
  );
}

/**
 * Connections, as Claude shows its connectors: the org's own and the whole catalog as two tabs under one search, with
 * a filter. An app opens its own page, where it is connected and its tools are chosen.
 */
export function ConnectionsPage() {
  const connections = useConnections();
  const search = useUrlSearch();
  const [params] = useSearchParams();
  const view: View = params.get('tab') === 'catalog' ? 'catalog' : 'yours';
  const show = (params.get('show') as Show | null) ?? 'all';
  const sort = (params.get('sort') as Sort | null) ?? 'name';
  const off = connectionsOff(connections.error);
  const apps = useMemo(() => (connections.data ? byApp(connections.data) : undefined), [connections.data]);
  const connected = useMemo(() => new Set((apps ?? []).map((a) => a.app)), [apps]);

  const filter = (
    <Menu
      label="Filter"
      trigger={({ toggle, open, id }) => (
        <Button variant="ghost" icon="layers" onClick={toggle} aria-expanded={open} aria-controls={id} aria-label="Filter">
          {view === 'catalog' ? SHOW[show] : SORT[sort]}
        </Button>
      )}
    >
      {view === 'catalog' ? (
        <>
          <MenuLabel>Show</MenuLabel>
          {(Object.keys(SHOW) as Show[]).map((s) => (
            <MenuRadioItem key={s} checked={show === s} onSelect={() => search.setParam({ show: s === 'all' ? null : s })}>
              {SHOW[s]}
            </MenuRadioItem>
          ))}
        </>
      ) : (
        <>
          <MenuLabel>Sort by</MenuLabel>
          {(Object.keys(SORT) as Sort[]).map((s) => (
            <MenuRadioItem key={s} checked={sort === s} onSelect={() => search.setParam({ sort: s === 'name' ? null : s })}>
              {SORT[s]}
            </MenuRadioItem>
          ))}
        </>
      )}
    </Menu>
  );

  return (
    <div className={styles.page}>
      <PageHeader title="Connections" description="Apps your organisation connects for its bots. Each bot is given only the tools you choose." />
      {off ? (
        <EmptyState icon="external" title="Connections are not set up">
          The server has no Pipedream project yet, so no app can be connected.
        </EmptyState>
      ) : (
        <>
          <div className={styles.toolbar}>
            <TextField
              className={styles.search}
              label="Search"
              type="search"
              placeholder={view === 'catalog' ? 'Search the catalog' : 'Search your connections'}
              value={search.typed}
              onChange={(e) => search.setTyped(e.target.value)}
            />
            <Tabs label="Connections" tabs={TABS} value={view} onChange={(tab) => search.setParam({ tab: tab === 'yours' ? null : tab, show: null, sort: null })} />
            {filter}
          </div>
          <ApiErrorNotice error={connections.error} />
          <div className={styles.panel} role="tabpanel" id={`panel-${view}`} aria-labelledby={`tab-${view}`}>
            {view === 'yours' ? <Yours apps={apps} q={search.q} sort={sort} /> : <Catalog q={search.q} show={show} connected={connected} />}
          </div>
        </>
      )}
    </div>
  );
}
