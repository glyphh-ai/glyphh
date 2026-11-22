import { Link, useNavigate } from 'react-router';
import { useBotPlaces } from '@/api/bots';
import { useCreateSwarm, useSwarms, type Swarm } from '@/api/swarms';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { plural } from '@/lib/format';
import { Button, Card, Chip, EmptyState, Icon, Skeleton } from '@/ui';
import { swarmPath } from './parts';
import { SwarmEditor } from './SwarmEditor';
import cs from '../connections/connections.module.css';
import bs from '../bots/bots.module.css';
import styles from './swarms.module.css';

const repoName = (url: string) => url.replace(/^https:\/\/github\.com\//, '');

function SwarmCard({ swarm, place }: { swarm: Swarm; place?: string }) {
  const title = `swarm-${swarm.slug}`;
  return (
    <li>
      <Link to={swarmPath(swarm.slug)} className={bs.card} aria-labelledby={title}>
        <div className={bs.cardBody}>
          <h2 id={title} className={bs.name}>
            {swarm.name}
          </h2>
          <span className={`${bs.muted} ${styles.code}`}>
            <Icon name="github" size={12} /> {repoName(swarm.repo_url)} · {swarm.base_branch}
          </span>
          <p className={bs.summary}>{swarm.members.map((m) => m.name).join(' → ') || 'No bots in the crew'}</p>
          <span className={bs.muted}>
            {plural(swarm.rounds, 'round')} · {swarm.review === 'auto' ? 'merged as they open' : 'you review each turn'}
          </span>
          <span className={bs.place}>
            <Chip tone="violet">On {place ?? 'your rrotor'}</Chip>
          </span>
        </div>
      </Link>
    </li>
  );
}

/** The org's swarms: crews of its bots taking turns on a GitHub repo, each turn a pull request. */
export function SwarmsPage() {
  const swarms = useSwarms();
  const places = useBotPlaces();
  const navigate = useNavigate();
  const named = new Map((places.data ?? []).map((p) => [p.id, p.name]));
  return (
    <div className={cs.page}>
      <PageHeader
        title="Swarms"
        description="A crew of your bots taking turns on one GitHub repo, on one of your rrotors. Each turn is a pull request you merge or reject; a bot says DONE when the task is finished."
        actions={
          <Button variant="primary" icon="plus" onClick={() => navigate('/swarms/new')}>
            New swarm
          </Button>
        }
      />
      <ApiErrorNotice error={swarms.error} />
      {swarms.isPending && <Skeleton height={120} />}
      {swarms.data?.length === 0 && (
        <EmptyState icon="team" title="No swarms yet">
          Put two or more of your bots on a repo and give them a task. <Link to="/swarms/new">New swarm</Link>
        </EmptyState>
      )}
      {swarms.data && swarms.data.length > 0 && (
        <ul className={bs.grid} aria-label="Swarms">
          {swarms.data.map((s) => (
            <SwarmCard key={s.id} swarm={s} place={named.get(s.runs_on)} />
          ))}
        </ul>
      )}
    </div>
  );
}

/** A new swarm, made and then opened. */
export function NewSwarmPage() {
  const create = useCreateSwarm();
  const navigate = useNavigate();
  return (
    <div className={cs.page}>
      <PageHeader title="New swarm" description="Choose the repo, the bots in the order they speak, and the rrotor their turns run on." />
      <Card>
        <SwarmEditor
          label="Make swarm"
          saving={create.isPending}
          error={create.error}
          onSave={(body) => create.mutate(body, { onSuccess: (s) => navigate(swarmPath(s.slug)) })}
        />
      </Card>
    </div>
  );
}
