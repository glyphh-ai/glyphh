import { useState } from 'react';
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router';
import { connectionsOff, useConnections, useRemoveConnection, type Connection, type ConnectorApp } from '@/api/bots';
import { byApp, useCatalogApp } from '@/api/connections';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { date } from '@/lib/format';
import { Button, Card, EmptyState, Icon, LoadingCard, Tabs, useToast } from '@/ui';
import { AppIcon } from './AppIcon';
import { ToolsPanel } from './ToolsPanel';
import { useConnect } from './useConnect';
import styles from './connections.module.css';

type View = 'overview' | 'tools';
const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'tools', label: 'Tools' },
] as const;

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className={styles.fact}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function Accounts({ accounts, onRemove }: { accounts: Connection[]; onRemove: (c: Connection) => void }) {
  return (
    <Card>
      <ul className={styles.accounts} aria-label="Accounts">
        {accounts.map((c) => (
          <li key={c.id} className={styles.account}>
            <div className={styles.rowText}>
              <span className={styles.rowName}>{c.label ?? 'Account'}</span>
              <span className={styles.muted}>Connected {date(c.created_at)}</span>
            </div>
            <span className={styles.added}>
              <Icon name="check" size={12} /> Connected
            </span>
            <Button variant="ghost" size="sm" icon="trash" onClick={() => onRemove(c)} aria-label={`Remove ${c.label ?? c.app_name}`}>
              Remove
            </Button>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** One app, as Claude shows a connector: what it is and its accounts (Overview), and the tools bots may be given (Tools). */
export function ConnectionPage() {
  const slug = useParams().name ?? '';
  const passed = (useLocation().state as { app?: ConnectorApp } | null)?.app;
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const connections = useConnections();
  const mine = connections.data ? byApp(connections.data).find((a) => a.app === slug) : undefined;
  const listed = useCatalogApp(slug, connections.isSuccess && !mine && !passed);
  const { connect, connecting, error, dialog } = useConnect();
  const remove = useRemoveConnection();
  const [removing, setRemoving] = useState<Connection | null>(null);

  const app: ConnectorApp | null | undefined = passed ?? (mine ? { slug, name: mine.name, description: null, icon: mine.icon } : listed.data);
  const view: View = params.get('tab') === 'tools' && mine ? 'tools' : 'overview';
  const off = connectionsOff(connections.error);

  const back = (
    <Link to="/connections" className={styles.back}>
      <Icon name="arrowLeft" size={14} /> Connections
    </Link>
  );
  if (off || connections.error) return <>{back}<ApiErrorNotice error={connections.error} /></>;
  if (connections.isPending || (app === undefined && listed.isPending))
    return (
      <>
        {back}
        <LoadingCard lines={4} />
      </>
    );
  if (!app)
    return (
      <>
        {back}
        <EmptyState icon="search" title="No such app">
          The catalog has no app called “{slug}”.
        </EmptyState>
      </>
    );

  const connectButton = (
    <Button variant={mine ? 'secondary' : 'primary'} icon="plus" loading={connecting === app.slug} onClick={() => connect(app)}>
      {mine ? 'Add another account' : 'Connect'}
    </Button>
  );

  return (
    <div className={styles.page}>
      {back}
      <div className={styles.hero}>
        <AppIcon icon={app.icon} name={app.name} large />
        <div className={styles.heroText}>
          <h1 className={styles.title}>{app.name}</h1>
          <p className={styles.muted}>{mine ? `${mine.accounts.length === 1 ? 'One account' : `${mine.accounts.length} accounts`} · Through Pipedream` : (app.description ?? 'Connector · Through Pipedream')}</p>
        </div>
        <div className={styles.heroActions}>
          {mine && (
            <span className={styles.addedChip}>
              <Icon name="check" size={14} /> Added
            </span>
          )}
          {connectButton}
        </div>
      </div>
      <ApiErrorNotice error={error} />
      <Tabs label={app.name} tabs={TABS} value={view} onChange={(tab) => setParams(tab === 'overview' ? {} : { tab }, { replace: true })} />
      <div className={styles.panel} role="tabpanel" id={`panel-${view}`} aria-labelledby={`tab-${view}`}>
        {view === 'tools' && mine ? (
          <ToolsPanel connection={mine.accounts[0]!} />
        ) : (
          <div className={styles.layout}>
            <div className={styles.sections}>
              <p className={styles.lede}>
                {app.description ? `${app.description} ` : ''}Connect {app.name} and your bots can use the tools you allow, as your organisation. You sign in to {app.name} itself; Glyphh never sees your password.
              </p>
              <h2 className={styles.sectionTitle}>Accounts</h2>
              {mine ? (
                <Accounts accounts={mine.accounts} onRemove={setRemoving} />
              ) : (
                <EmptyState icon="external" title={`${app.name} is not connected`} action={connectButton}>
                  Connect it to see its tools and give them to your bots.
                </EmptyState>
              )}
            </div>
            <dl className={styles.facts}>
              <Fact label="Connects through">Pipedream Connect</Fact>
              <Fact label="Sign-in">Required, on {app.name}’s own page</Fact>
              <Fact label="Used as">Your organisation</Fact>
              <Fact label="Tools">{mine ? <Link to="?tab=tools">Choose which tools bots may use</Link> : 'Shown once connected'}</Fact>
            </dl>
          </div>
        )}
      </div>
      {dialog}
      <ConfirmDialog
        open={removing !== null}
        title={`Remove ${removing?.label ?? removing?.app_name ?? 'this account'}?`}
        description="Bots that use it lose its tools. You can connect it again later."
        confirmLabel="Remove"
        pending={remove.isPending}
        error={remove.error}
        onConfirm={() =>
          removing &&
          remove.mutate(removing.id, {
            onSuccess: () => {
              toast.show(`${removing.label ?? removing.app_name} is removed.`);
              setRemoving(null);
              if (mine?.accounts.length === 1) navigate('/connections');
            },
          })
        }
        onClose={() => {
          remove.reset();
          setRemoving(null);
        }}
      />
    </div>
  );
}
