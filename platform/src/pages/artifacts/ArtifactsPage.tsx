import { useEffect, useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router';
import { useApproveArtifact, useArtifacts, useMe, useRejectArtifact, useRetireArtifact } from '@/api/queries';
import type { Artifact, ArtifactState } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { date } from '@/lib/format';
import { Button, ButtonLink, Chip, Dialog, EmptyState, LoadingCard, panelId, tabId, Tabs, TextField, useToast } from '@/ui';
import styles from './ArtifactsPage.module.css';

const PER_PAGE = 24;
const SEARCH_DELAY_MS = 300;

type Tab = 'approved' | 'draft' | 'rejected';
const tabs: ReadonlyArray<{ id: Tab; label: string }> = [
  { id: 'approved', label: 'Published' },
  { id: 'draft', label: 'Awaiting review' },
  { id: 'rejected', label: 'Rejected' },
];

const empty: Record<Tab, { title: string; text: string }> = {
  approved: { title: 'Nothing published yet', text: 'Ask Claude to publish an artifact to your org.' },
  draft: { title: 'Nothing awaiting review', text: 'A page Claude publishes to one of your rrotors shows here until it is reviewed.' },
  rejected: { title: 'Nothing rejected', text: 'A page a reviewer turned down shows here with the reason.' },
};

/**
 * Artifacts, in Runtimes & licences: the pages Claude published to the org's rrotors, from the catalogue
 * (`GET /v1/artifacts`), as cards with Open; a reviewer sees the ones awaiting review and the rejected ones too,
 * and approves, rejects (with a reason) or retires. The search and the page live in the URL.
 */
export function ArtifactsPage() {
  const [params, setParams] = useSearchParams();
  const me = useMe();
  const reviewer = me.data?.reviewer === true;
  const q = params.get('q') ?? '';
  const page = Math.max(1, Number(params.get('page')) || 1);
  const asked = params.get('state');
  const tab: Tab = reviewer && (asked === 'draft' || asked === 'rejected') ? asked : 'approved';
  const state: ArtifactState = tab;
  const artifacts = useArtifacts({ q, page, state });

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

  // What is typed reaches the URL (and the server) once typing pauses.
  const [typed, setTyped] = useState(q);
  useEffect(() => setTyped(q), [q]);
  useEffect(() => {
    if (typed === q) return;
    const timer = setTimeout(() => setParam({ q: typed, page: null }, true), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [typed, q]); // eslint-disable-line react-hooks/exhaustive-deps

  const total = artifacts.data?.total ?? 0;
  const from = total === 0 ? 0 : (page - 1) * PER_PAGE + 1;
  const to = Math.min(page * PER_PAGE, total);
  const last = Math.max(1, Math.ceil(total / PER_PAGE));

  const list = (
    <>
      {artifacts.isPending && <LoadingCard />}
      {artifacts.error && <ApiErrorNotice error={artifacts.error} />}
      {artifacts.data && artifacts.data.artifacts.length === 0 && (
        <EmptyState icon="layers" title={q ? 'Nothing matches' : empty[tab].title}>
          {q ? `No artifact matches “${q}”.` : empty[tab].text}
        </EmptyState>
      )}
      {artifacts.data && artifacts.data.artifacts.length > 0 && (
        <ul className={styles.grid} aria-label="Artifacts">
          {artifacts.data.artifacts.map((artifact) => (
            <ArtifactCard key={artifact.id} artifact={artifact} reviewer={reviewer} />
          ))}
        </ul>
      )}
      {artifacts.data && total > PER_PAGE && (
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
      <PageHeader title="Artifacts" description="The pages Claude published to your org’s rrotors. Open one at the rrotor it lives on." />
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
        </div>
        {reviewer ? (
          <>
            <Tabs label="Artifacts" tabs={tabs} value={tab} onChange={(id) => setParam({ state: id === 'approved' ? null : id, page: null }, true)} />
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

function who(by: Artifact['submitted_by']): string {
  return by?.name ?? by?.email ?? 'someone';
}

function ArtifactCard({ artifact, reviewer }: { artifact: Artifact; reviewer: boolean }) {
  const toast = useToast();
  const approve = useApproveArtifact();
  const reject = useRejectArtifact();
  const retire = useRetireArtifact();
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState('');
  const [retiring, setRetiring] = useState(false);

  const submitReject = (event: FormEvent) => {
    event.preventDefault();
    reject.mutate(
      { id: artifact.id, reason: reason.trim() },
      {
        onSuccess: () => {
          setRejecting(false);
          setReason('');
          toast.show(`${artifact.title} is rejected.`);
        },
      },
    );
  };

  return (
    <li className={styles.card} aria-label={artifact.title}>
      <div className={styles.title}>{artifact.title}</div>
      {artifact.description && <p className={styles.description}>{artifact.description}</p>}
      <div className={styles.meta}>
        {artifact.runtime_name} · v{artifact.version}
      </div>
      <div className={styles.chips}>
        {artifact.roles.length === 0 ? <Chip>Everyone</Chip> : artifact.roles.map((role) => <Chip key={role} tone="blue">{role}</Chip>)}
      </div>
      <div className={styles.meta}>
        Published by {who(artifact.submitted_by)} · {date(artifact.submitted_at)}
      </div>
      {artifact.state === 'rejected' && artifact.reason && (
        <p className={styles.reason}>
          Rejected{artifact.reviewed_by ? ` by ${who(artifact.reviewed_by)}` : ''}: {artifact.reason}
        </p>
      )}
      <div className={styles.actions}>
        <ButtonLink href={artifact.url} target="_blank" rel="noopener noreferrer" size="sm" variant="primary">
          Open
        </ButtonLink>
        {reviewer && artifact.state === 'draft' && (
          <>
            <Button size="sm" loading={approve.isPending} onClick={() => approve.mutate(artifact.id, { onSuccess: () => toast.show(`${artifact.title} is published.`) })}>
              Approve
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setRejecting(true)}>
              Reject
            </Button>
          </>
        )}
        {reviewer && artifact.state === 'approved' && (
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
        title={`Reject ${artifact.title}?`}
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
            <Button type="submit" form={`reject-${artifact.id}`} variant="danger" loading={reject.isPending} disabled={!reason.trim()}>
              Reject
            </Button>
          </>
        }
      >
        <form id={`reject-${artifact.id}`} className={styles.form} onSubmit={submitReject}>
          <TextField label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} autoFocus required />
          <ApiErrorNotice error={reject.error} />
        </form>
      </Dialog>

      <ConfirmDialog
        open={retiring}
        title={`Retire ${artifact.title}?`}
        description="It is no longer served or listed. Publishing a new version brings it back for review."
        confirmLabel="Retire"
        pending={retire.isPending}
        error={retire.error}
        onConfirm={() =>
          retire.mutate(artifact.id, {
            onSuccess: () => {
              setRetiring(false);
              toast.show(`${artifact.title} is retired.`);
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
