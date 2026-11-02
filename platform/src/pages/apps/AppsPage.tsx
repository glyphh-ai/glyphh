import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router';
import { useApproveApp, useApps, useMe, useRejectApp, useRetireApp } from '@/api/queries';
import type { App, AppState, AppType } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { date } from '@/lib/format';
import { Button, ButtonLink, Chip, Dialog, EmptyState, LoadingCard, panelId, Select, tabId, Tabs, TextField, useToast } from '@/ui';
import styles from './AppsPage.module.css';

const PER_PAGE = 24;
const SEARCH_DELAY_MS = 300;

type Tab = 'approved' | 'draft' | 'rejected';
const tabs: ReadonlyArray<{ id: Tab; label: string }> = [
  { id: 'approved', label: 'Published' },
  { id: 'draft', label: 'Awaiting review' },
  { id: 'rejected', label: 'Rejected' },
];

/** The six types, in the filter's order: the chip's word for one, the filter's word for many. */
const types: ReadonlyArray<{ id: AppType; one: string; many: string }> = [
  { id: 'page', one: 'Page', many: 'Pages' },
  { id: 'dashboard', one: 'Dashboard', many: 'Dashboards' },
  { id: 'doc', one: 'Doc', many: 'Docs' },
  { id: 'diagram', one: 'Diagram', many: 'Diagrams' },
  { id: 'deck', one: 'Deck', many: 'Decks' },
  { id: 'design', one: 'Design', many: 'Designs' },
];
const typeOptions = [{ value: '', label: 'All types' }, ...types.map((t) => ({ value: t.id, label: t.many }))];
const isType = (value: string | null): value is AppType => types.some((t) => t.id === value);
const typeLabel = (type: AppType): string => types.find((t) => t.id === type)?.one ?? 'Page';

const empty: Record<Tab, { title: string; text: string }> = {
  approved: { title: 'Nothing published yet', text: 'Ask Claude to publish what it made to your org.' },
  draft: { title: 'Nothing awaiting review', text: 'An app Claude publishes to one of your rrotors shows here until it is reviewed.' },
  rejected: { title: 'Nothing rejected', text: 'An app a reviewer turned down shows here with the reason.' },
};

/**
 * Apps, in Runtimes & licences: what Claude made and published to the org's rrotors, from the catalogue
 * (`GET /v1/apps`), as cards with Open; a reviewer sees the ones awaiting review and the rejected ones too, and
 * approves, rejects (with a reason) or retires. The search, the type and the page live in the URL.
 */
export function AppsPage() {
  const [params, setParams] = useSearchParams();
  const me = useMe();
  const reviewer = me.data?.reviewer === true;
  const q = params.get('q') ?? '';
  const page = Math.max(1, Number(params.get('page')) || 1);
  const asked = params.get('state');
  const tab: Tab = reviewer && (asked === 'draft' || asked === 'rejected') ? asked : 'approved';
  const state: AppState = tab;
  const askedType = params.get('type');
  const type = isType(askedType) ? askedType : undefined;
  const apps = useApps({ q, page, state, type });

  const setParam = (changes: Record<string, string | null>, replace = false) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        for (const [key, value] of Object.entries(changes)) {
          if (value === null || value === '') next.delete(key);
          else next.set(key, value);
        }
        return next;
      },
      { replace },
    );

  // What is typed reaches the URL (and the server) once typing pauses. A `q` from elsewhere (a link, Back) replaces
  // what is typed; our own landing never does, or keystrokes made while it was landing would be lost.
  const [typed, setTyped] = useState(q);
  const committed = useRef(q);
  useEffect(() => {
    if (q !== committed.current) {
      committed.current = q;
      setTyped(q);
    }
  }, [q]);
  useEffect(() => {
    if (typed === q) return;
    const timer = setTimeout(() => {
      committed.current = typed;
      setParam({ q: typed, page: null }, true);
    }, SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [typed, q]); // eslint-disable-line react-hooks/exhaustive-deps

  const total = apps.data?.total ?? 0;
  const from = total === 0 ? 0 : (page - 1) * PER_PAGE + 1;
  const to = Math.min(page * PER_PAGE, total);
  const last = Math.max(1, Math.ceil(total / PER_PAGE));

  const nothing = q
    ? { title: 'Nothing matches', text: `No app matches “${q}”.` }
    : type
      ? { title: 'Nothing matches', text: `No ${types.find((t) => t.id === type)!.many.toLowerCase()} match.` }
      : empty[tab];

  const list = (
    <>
      {apps.isPending && <LoadingCard />}
      {apps.error && <ApiErrorNotice error={apps.error} />}
      {apps.data && apps.data.apps.length === 0 && (
        <EmptyState icon="layers" title={nothing.title}>
          {nothing.text}
        </EmptyState>
      )}
      {apps.data && apps.data.apps.length > 0 && (
        <ul className={styles.grid} aria-label="Apps">
          {apps.data.apps.map((app) => (
            <AppCard key={app.id} app={app} reviewer={reviewer} />
          ))}
        </ul>
      )}
      {apps.data && total > PER_PAGE && (
        <nav className={styles.pager} aria-label="Pages">
          <span>
            {from}–{to} of {total}
          </span>
          <div className={styles.pagerButtons}>
            <Button size="sm" disabled={page <= 1} onClick={() => setParam({ page: String(page - 1) })}>
              Previous
            </Button>
            <Button size="sm" disabled={page >= last} onClick={() => setParam({ page: String(page + 1) })}>
              Next
            </Button>
          </div>
        </nav>
      )}
    </>
  );

  return (
    <>
      <PageHeader title="Apps" description="What Claude made and published to your org’s rrotors. Open one at the rrotor it lives on." />
      <div className={styles.stack}>
        <div className={styles.toolbar}>
          <TextField
            className={styles.search}
            label="Search"
            type="search"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder="Title, description or name"
          />
          <div className={styles.type}>
            <Select label="Type" options={typeOptions} value={type ?? ''} onChange={(e) => setParam({ type: e.target.value || null, page: null }, true)} />
          </div>
        </div>
        {reviewer ? (
          <>
            <Tabs label="Apps" tabs={tabs} value={tab} onChange={(id) => setParam({ state: id === 'approved' ? null : id, page: null }, true)} />
            <div role="tabpanel" id={panelId(tab)} aria-labelledby={tabId(tab)} className={styles.stack}>
              {list}
            </div>
          </>
        ) : (
          list
        )}
      </div>
    </>
  );
}

function who(by: App['submitted_by']): string {
  return by?.name ?? by?.email ?? 'someone';
}

function AppCard({ app, reviewer }: { app: App; reviewer: boolean }) {
  const toast = useToast();
  const approve = useApproveApp();
  const reject = useRejectApp();
  const retire = useRetireApp();
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState('');
  const [retiring, setRetiring] = useState(false);

  const submitReject = (event: FormEvent) => {
    event.preventDefault();
    reject.mutate(
      { id: app.id, reason: reason.trim() },
      {
        onSuccess: () => {
          setRejecting(false);
          setReason('');
          toast.show(`${app.title} is rejected.`);
        },
      },
    );
  };

  return (
    <li className={styles.card} aria-label={app.title}>
      <div className={styles.head}>
        <div className={styles.title}>{app.title}</div>
        <Chip>{typeLabel(app.type)}</Chip>
      </div>
      {app.description && <p className={styles.description}>{app.description}</p>}
      <div className={styles.meta}>
        {app.runtime_name} · v{app.version}
      </div>
      <div className={styles.chips}>
        {app.roles.length === 0 ? <Chip>Everyone</Chip> : app.roles.map((role) => <Chip key={role} tone="blue">{role}</Chip>)}
      </div>
      <div className={styles.meta}>
        Published by {who(app.submitted_by)} · {date(app.submitted_at)}
      </div>
      {app.state === 'rejected' && app.reason && (
        <p className={styles.reason}>
          Rejected{app.reviewed_by ? ` by ${who(app.reviewed_by)}` : ''}: {app.reason}
        </p>
      )}
      <div className={styles.actions}>
        <ButtonLink href={app.url} target="_blank" rel="noopener noreferrer" size="sm" variant="primary">
          Open
        </ButtonLink>
        {reviewer && app.state === 'draft' && (
          <>
            <Button size="sm" loading={approve.isPending} onClick={() => approve.mutate(app.id, { onSuccess: () => toast.show(`${app.title} is published.`) })}>
              Approve
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setRejecting(true)}>
              Reject
            </Button>
          </>
        )}
        {reviewer && app.state === 'approved' && (
          <Button size="sm" variant="ghost" onClick={() => setRetiring(true)}>
            Retire
          </Button>
        )}
      </div>
      <ApiErrorNotice error={approve.error} />

      <Dialog
        open={rejecting}
        onClose={() => {
          reject.reset();
          setRejecting(false);
        }}
        title={`Reject ${app.title}?`}
        description="The person who published it sees the reason."
        actions={
          <>
            <Button
              onClick={() => {
                reject.reset();
                setRejecting(false);
              }}
            >
              Cancel
            </Button>
            <Button type="submit" form={`reject-${app.id}`} variant="danger" loading={reject.isPending} disabled={!reason.trim()}>
              Reject
            </Button>
          </>
        }
      >
        <form id={`reject-${app.id}`} className={styles.form} onSubmit={submitReject}>
          <TextField label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} autoFocus required />
          <ApiErrorNotice error={reject.error} />
        </form>
      </Dialog>

      <ConfirmDialog
        open={retiring}
        title={`Retire ${app.title}?`}
        description="It is no longer served or listed. Publishing a new version brings it back for review."
        confirmLabel="Retire"
        pending={retire.isPending}
        error={retire.error}
        onConfirm={() =>
          retire.mutate(app.id, {
            onSuccess: () => {
              setRetiring(false);
              toast.show(`${app.title} is retired.`);
            },
          })
        }
        onClose={() => {
          retire.reset();
          setRetiring(false);
        }}
      />
    </li>
  );
}
