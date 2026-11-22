import { useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';
import { useBotPlaces } from '@/api/bots';
import {
  swarmGoing,
  useCancelSwarmRun,
  useDeleteSwarm,
  useRunSwarm,
  useSwarm,
  useSwarmRun,
  useSwarmRuns,
  useUpdateSwarm,
  type Swarm,
  type SwarmRun,
  type SwarmTurn,
} from '@/api/swarms';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { ago, stamp } from '@/lib/format';
import { Button, Card, EmptyState, Icon, LoadingCard, panelId, tabId, Tabs, useToast, type Tab } from '@/ui';
import { TextArea } from '../bots/parts';
import { PullRequestCard, SwarmRunChip, TurnChip } from './parts';
import { SwarmEditor } from './SwarmEditor';
import cs from '../connections/connections.module.css';
import bs from '../bots/bots.module.css';
import styles from './swarms.module.css';

type TabId = 'runs' | 'settings';
const tabs: ReadonlyArray<Tab<TabId>> = [
  { id: 'runs', label: 'Runs' },
  { id: 'settings', label: 'Settings' },
];

/** One turn on the timeline: the bot, its round, what became of it, and its pull request (merged or rejected here while it waits). */
function Turn({ turn, run }: { turn: SwarmTurn; run: SwarmRun }) {
  const waiting = run.status === 'needs_input' && turn.status === 'open';
  const hasPr = turn.pr_url !== null || turn.files.length > 0;
  return (
    <li className={styles.turn} aria-label={`Turn ${turn.n}: ${turn.bot_name}`}>
      <div className={styles.turnHead}>
        <span className={styles.turnName}>
          {turn.n}. {turn.bot_name}
        </span>
        <TurnChip status={turn.status} />
        {turn.done && <span className={bs.muted}>said DONE</span>}
        <span className={bs.muted}>
          round {turn.round} · {ago(turn.created_at)}
        </span>
      </div>
      {hasPr ? (
        <PullRequestCard pr={turn} runId={run.id} waiting={waiting} />
      ) : (
        turn.said && <p className={styles.said}>{turn.said}</p>
      )}
      {turn.status === 'running' && <span className={bs.muted}>Working on branch {turn.branch}…</span>}
      {turn.error && <p className={styles.error}>{turn.error}</p>}
    </li>
  );
}

/** A run in full: its task, how it stands, its turns in order (each pull request merged or rejected in place), cancel. */
function RunView({ id, place }: { id: string; place: (id: string | null) => string }) {
  const run = useSwarmRun(id);
  const cancel = useCancelSwarmRun();
  if (run.isPending) return <LoadingCard lines={5} />;
  if (run.error) return <ApiErrorNotice error={run.error} />;
  const r = run.data;
  const live = r.status === 'running' || r.status === 'needs_input';
  return (
    <Card>
      <section className={bs.form} aria-label="Swarm run">
        <div className={bs.spread}>
          <span className={bs.row}>
            <SwarmRunChip status={r.status} />
            <span className={bs.muted} title={stamp(r.created_at)}>
              {ago(r.created_at)} · on {place(r.runs_on)} · {r.review === 'auto' ? 'merged as they open' : 'you review each turn'}
            </span>
          </span>
          {live && (
            <Button variant="ghost" size="sm" icon="close" loading={cancel.isPending} onClick={() => cancel.mutate(r.id)}>
              Cancel run
            </Button>
          )}
        </div>
        <div>
          <span className={bs.label}>Task</span>
          <p className={bs.output}>{r.task}</p>
        </div>
        {r.error && <p className={styles.error}>{r.error}</p>}
        <ApiErrorNotice error={cancel.error} />
        {r.turns.length > 0 ? (
          <ol className={styles.timeline} aria-label="Turns">
            {r.turns.map((t) => (
              <Turn key={t.n} turn={t} run={r} />
            ))}
          </ol>
        ) : (
          <p className={bs.muted}>No turn yet.</p>
        )}
      </section>
    </Card>
  );
}

/** Give the crew a task; its runs, newest first (`?run=` opens one); the open run in full. */
function RunsTab({ swarm, place }: { swarm: Swarm; place: (id: string | null) => string }) {
  const runs = useSwarmRuns(swarm.slug);
  const start = useRunSwarm(swarm.slug);
  const [params, setParams] = useSearchParams();
  const [task, setTask] = useState('');
  const open = (id: string) => setParams({ tab: 'runs', run: id }, { replace: true });
  const shown = params.get('run') ?? runs.data?.[0]?.id ?? null;
  const live = runs.data?.some((r) => swarmGoing(r.status) || r.status === 'needs_input') ?? false;
  return (
    <div className={bs.stack}>
      <Card>
        <div className={bs.form}>
          <TextArea label="Task" hint="What the crew is to do in the repo. Each bot does its part in turn." value={task} onChange={(e) => setTask(e.target.value)} />
          <ApiErrorNotice error={start.error} />
          <div className={bs.row}>
            <Button
              variant="primary"
              disabled={task.trim() === '' || live}
              loading={start.isPending}
              onClick={() =>
                start.mutate(task.trim(), {
                  onSuccess: (r) => {
                    setTask('');
                    open(r.id);
                  },
                })
              }
            >
              Start
            </Button>
            {live && <span className={bs.muted}>A run is going: answer its pull request or cancel it first.</span>}
          </div>
        </div>
      </Card>
      <ApiErrorNotice error={runs.error} />
      {runs.data?.length === 0 && (
        <EmptyState icon="logs" title="No runs yet">
          Give the crew a task and start it.
        </EmptyState>
      )}
      {runs.data && runs.data.length > 0 && (
        <ul className={bs.steps} aria-label="Runs">
          {runs.data.map((r) => (
            <li key={r.id}>
              <button type="button" className={bs.runRow} aria-pressed={r.id === shown} onClick={() => open(r.id)}>
                <span className={bs.spread}>
                  <span className={bs.grow}>{r.task}</span>
                  <SwarmRunChip status={r.status} />
                </span>
                <span className={bs.muted} title={stamp(r.created_at)}>
                  {ago(r.created_at)} · {r.turns.length} {r.turns.length === 1 ? 'turn' : 'turns'}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {shown && <RunView key={shown} id={shown} place={place} />}
    </div>
  );
}

function SettingsTab({ swarm }: { swarm: Swarm }) {
  const update = useUpdateSwarm(swarm.slug);
  const remove = useDeleteSwarm();
  const toast = useToast();
  const navigate = useNavigate();
  const [deleting, setDeleting] = useState(false);
  return (
    <div className={bs.stack}>
      <Card>
        <SwarmEditor swarm={swarm} label="Save" saving={update.isPending} error={update.error} onSave={(body) => update.mutate(body, { onSuccess: () => toast.show('Saved.') })} />
      </Card>
      <div className={bs.row}>
        <Button variant="danger" icon="trash" onClick={() => setDeleting(true)}>
          Delete swarm
        </Button>
      </div>
      <ConfirmDialog
        open={deleting}
        title={`Delete ${swarm.name}?`}
        description="Its runs go with it. The branches and pull requests stay on GitHub."
        confirmLabel="Delete"
        pending={remove.isPending}
        error={remove.error}
        onConfirm={() => remove.mutate(swarm.slug, { onSuccess: () => navigate('/swarms') })}
        onClose={() => setDeleting(false)}
      />
    </div>
  );
}

/** One swarm: its repo, crew and rrotor, its runs (each turn's pull request merged or rejected there), its settings. */
export function SwarmPage() {
  const { name: slug = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const swarm = useSwarm(slug);
  const places = useBotPlaces();
  const named = new Map((places.data ?? []).map((p) => [p.id, p.name]));
  const place = (id: string | null) => (id ? (named.get(id) ?? 'your rrotor') : 'a rrotor since deleted');
  const tab: TabId = params.get('tab') === 'settings' ? 'settings' : 'runs';
  const s = swarm.data;
  return (
    <div className={cs.page}>
      <Link to="/swarms" className={cs.back}>
        <Icon name="arrowLeft" size={14} /> Swarms
      </Link>
      <div className={cs.hero}>
        <div className={cs.heroText}>
          <h1 className={cs.title}>{s?.name ?? slug}</h1>
          <p className={cs.muted}>
            {s ? (
              <>
                <a href={s.repo_url} target="_blank" rel="noreferrer">
                  {s.repo_url.replace(/^https:\/\/github\.com\//, '')}
                </a>{' '}
                · {s.base_branch} · {s.members.map((m) => m.name).join(' → ')} · on {place(s.runs_on)}
              </>
            ) : (
              ' '
            )}
          </p>
        </div>
      </div>
      {swarm.isPending && <LoadingCard lines={6} />}
      <ApiErrorNotice error={swarm.error} />
      {s && (
        <>
          <Tabs label="Swarm" tabs={tabs} value={tab} onChange={(id) => setParams({ tab: id }, { replace: true })} />
          <div role="tabpanel" id={panelId(tab)} aria-labelledby={tabId(tab)} className={`${cs.panel} ${bs.tabBody}`}>
            {tab === 'runs' && <RunsTab swarm={s} place={place} />}
            {tab === 'settings' && <SettingsTab key={s.updated_at} swarm={s} />}
          </div>
        </>
      )}
    </div>
  );
}
