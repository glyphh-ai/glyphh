import { useState, type FormEvent } from 'react';
import { useParams, useSearchParams } from 'react-router';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { NotFoundPage } from '@/pages/flows/ResultPages';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { Button, Card, Dialog, EmptyState, LoadingCard, Select, Tabs, TextField } from '@/ui';
import { useGameRead, type Args } from './api';
import { useActionRunner } from './ActionDialog';
import { catalogOf, type Row, type View } from './catalog';
import { columnsOf, Facts, rowsOf, Table } from './DataView';
import styles from './games.module.css';

/** One game's admin: a tab for each of its lists, each with the actions that game's own tools offer. */
export function GamePage() {
  const { id } = useParams();
  const catalog = catalogOf(id);
  const [search, setSearch] = useSearchParams();
  if (!catalog) return <NotFoundPage />;
  const view = catalog.views.find((v) => v.id === search.get('tab')) ?? catalog.views[0]!;
  const choose = (tab: string) => setSearch({ tab }, { replace: true });
  return (
    <div className={styles.page}>
      <PageHeader title={catalog.name} />
      <div className={styles.tabsBox}>
        <Tabs label={catalog.name} tabs={catalog.views.map((v) => ({ id: v.id, label: v.label }))} value={view.id} onChange={choose} />
      </div>
      <div role="tabpanel" id={`panel-${view.id}`} aria-labelledby={`tab-${view.id}`} className={styles.page}>
        <ViewPanel key={view.id} game={catalog.id} view={view} />
      </div>
    </div>
  );
}

function ViewPanel({ game, view }: { game: string; view: View }) {
  const [typed, setTyped] = useState('');
  const [q, setQ] = useState('');
  const [state, setState] = useState(view.states?.[0]?.value ?? '');
  const [inputs, setInputs] = useState<Record<string, string>>(() => Object.fromEntries((view.inputs ?? []).map((f) => [f.name, f.options?.[0]?.value ?? ''])));
  const [page, setPage] = useState<number>(view.paging ?? 0);
  const [opened, setOpened] = useState<Row | null>(null);
  const runner = useActionRunner(game);

  const chosen = view.states?.find((s) => s.value === state);
  const args: Args = { ...view.args, ...(chosen?.value ? chosen.args : {}), ...inputs };
  if (view.search && q) args.q = q;
  if (view.paging !== undefined) args.page = page;
  const read = useGameRead(game, view.tool, args);

  const find = (event: FormEvent) => {
    event.preventDefault();
    setQ(typed.trim());
    setPage(view.paging ?? 0);
  };

  const data = read.data as Record<string, any> | undefined;
  const rows = data === undefined ? null : rowsOf(data, view.list);
  const filters = view.search || view.states || view.inputs;
  return (
    <>
      {(filters || view.tabActions) && (
        <div className={styles.bar}>
          {filters && (
            <form className={styles.filters} onSubmit={find} role="search" aria-label={view.label}>
              {view.search && <TextField label="Search" value={typed} onChange={(e) => setTyped(e.target.value)} />}
              {view.states && (
                <Select
                  label="Show"
                  options={view.states}
                  value={state}
                  onChange={(e) => {
                    setState(e.target.value);
                    setPage(view.paging ?? 0);
                  }}
                />
              )}
              {view.inputs?.map((f) => (
                <Select
                  key={f.name}
                  label={f.label}
                  options={f.options ?? []}
                  value={inputs[f.name] ?? ''}
                  onChange={(e) => {
                    setInputs((v) => ({ ...v, [f.name]: e.target.value }));
                    setPage(view.paging ?? 0);
                  }}
                />
              ))}
              {view.search && (
                <Button type="submit" icon="search">
                  Search
                </Button>
              )}
            </form>
          )}
          {view.tabActions && (
            <div className={styles.actions}>
              {view.tabActions.map((a) => (
                <Button key={a.label} icon="plus" variant={a.danger ? 'danger' : 'secondary'} onClick={() => runner.start(a, null)}>
                  {a.label}
                </Button>
              ))}
            </div>
          )}
        </div>
      )}
      {read.isPending && <LoadingCard lines={4} />}
      <ApiErrorNotice error={read.error} />
      {data !== undefined && rows === null && <Facts data={data} />}
      {rows !== null && rows.length === 0 && <EmptyState icon="logs" title="Nothing here" />}
      {rows !== null && rows.length > 0 && (
        <Card>
          <Table
            rows={rows}
            columns={columnsOf(rows, view.columns)}
            name={view.label}
            extra={
              view.open || view.rowActions
                ? (row) => (
                    <div className={styles.rowButtons}>
                      {view.open && (
                        <Button size="sm" variant="ghost" onClick={() => setOpened(row)}>
                          Open
                        </Button>
                      )}
                      {view.rowActions
                        ?.filter((a) => !a.when || a.when(row))
                        .map((a) => (
                          <Button key={a.label} size="sm" variant={a.danger ? 'danger' : 'secondary'} disabled={runner.pending} onClick={() => runner.start(a, row)}>
                            {a.label}
                          </Button>
                        ))}
                    </div>
                  )
                : undefined
            }
          />
          {view.paging !== undefined && typeof data?.pages === 'number' && data.pages > 1 && (
            <div className={styles.pager}>
              <span>{`Page ${data.page - view.paging + 1} of ${data.pages}${typeof data.total === 'number' ? `, ${data.total.toLocaleString('en-GB')} in all` : ''}`}</span>
              <div className={styles.actions}>
                <Button size="sm" disabled={page <= view.paging} onClick={() => setPage((p) => p - 1)}>
                  Previous
                </Button>
                <Button size="sm" disabled={data.page - view.paging + 1 >= data.pages} onClick={() => setPage((p) => p + 1)}>
                  Next
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}
      {runner.dialog}
      {view.open && opened && <Opened game={game} tool={view.open.tool} args={view.open.args(opened)} onClose={() => setOpened(null)} />}
    </>
  );
}

/** A row's own page (a player, a league, a carol), as the game answers it. */
function Opened({ game, tool, args, onClose }: { game: string; tool: string; args: Args; onClose: () => void }) {
  const read = useGameRead(game, tool, args);
  return (
    <Dialog
      open
      size="wide"
      onClose={onClose}
      title="Details"
      actions={
        <Button variant="ghost" onClick={onClose}>
          Close
        </Button>
      }
    >
      {read.isPending && <LoadingCard lines={4} />}
      <ApiErrorNotice error={read.error} />
      {read.data !== undefined && (
        <div className={styles.opened}>
          <Facts data={read.data} depth={1} />
        </div>
      )}
    </Dialog>
  );
}
