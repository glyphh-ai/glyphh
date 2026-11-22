import { useState } from 'react';
import { Link } from 'react-router';
import { useBotPlaces, useBots } from '@/api/bots';
import { useGitHubKey, type NewSwarm, type Review, type Swarm } from '@/api/swarms';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Button, Select, TextField } from '@/ui';
import bs from '../bots/bots.module.css';
import styles from './swarms.module.css';

const REVIEWS: ReadonlyArray<{ value: Review; label: string; hint: string }> = [
  { value: 'each_turn', label: 'Each turn', hint: 'Each pull request waits in Approvals for your merge or reject before the next bot goes.' },
  { value: 'auto', label: 'Merge as they open', hint: 'Each pull request is merged as it opens; the next bot goes at once.' },
];
const ROUNDS = Array.from({ length: 10 }, (_, i) => ({ value: String(i + 1), label: i === 0 ? '1 round' : `${i + 1} rounds` }));

/** The crew in speaking order: each bot moved up or down, or taken out; another of the org's bots added at the end. */
function Crew({ ids, onChange }: { ids: string[]; onChange: (ids: string[]) => void }) {
  const bots = useBots();
  const byId = new Map((bots.data ?? []).map((b) => [b.id, b]));
  const left = (bots.data ?? []).filter((b) => !ids.includes(b.id));
  const move = (i: number, by: number) => {
    const next = [...ids];
    [next[i], next[i + by]] = [next[i + by]!, next[i]!];
    onChange(next);
  };
  return (
    <div className={bs.field}>
      <span className={bs.label}>Crew, in speaking order</span>
      {ids.length > 0 && (
        <ol className={styles.crew} aria-label="Crew">
          {ids.map((id, i) => (
            <li key={id} className={styles.member}>
              <span className={styles.order}>{i + 1}</span>
              <span className={bs.grow}>{byId.get(id)?.name ?? 'A bot deleted since'}</span>
              <Button size="sm" variant="ghost" disabled={i === 0} onClick={() => move(i, -1)} aria-label={`Move ${byId.get(id)?.name ?? 'it'} up`}>
                Up
              </Button>
              <Button size="sm" variant="ghost" disabled={i === ids.length - 1} onClick={() => move(i, 1)} aria-label={`Move ${byId.get(id)?.name ?? 'it'} down`}>
                Down
              </Button>
              <Button size="sm" variant="ghost" icon="close" onClick={() => onChange(ids.filter((x) => x !== id))} aria-label={`Take ${byId.get(id)?.name ?? 'it'} out`} />
            </li>
          ))}
        </ol>
      )}
      {ids.length < 8 && (
        <Select
          label="Add a bot"
          value=""
          onChange={(e) => e.target.value && onChange([...ids, e.target.value])}
          options={[{ value: '', label: left.length ? 'Choose a bot…' : 'Every bot is in the crew' }, ...left.map((b) => ({ value: b.id, label: b.name }))]}
          disabled={left.length === 0}
        />
      )}
      <ApiErrorNotice error={bots.error} />
    </div>
  );
}

/** Which of the org's rrotors the turns run on: a swarm never runs on Glyphh cloud. One offline is greyed. */
function RunsOn({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const places = useBotPlaces();
  const rrotors = (places.data ?? []).filter((p) => p.id !== null);
  if (places.data && rrotors.length === 0)
    return <p className={bs.muted}>Swarms run on one of your rrotors, and none is linked to Glyphh yet. Start one, then come back.</p>;
  const options = [
    { value: '', label: 'Choose a rrotor…' },
    ...rrotors.map((p) => ({ value: p.id!, label: p.linked ? p.name : `${p.name} (offline)`, disabled: !p.linked && p.id !== value })),
  ];
  return (
    <Select
      label="Runs on"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      options={options}
      hint="Its turns run there with Claude Code, on the Claude key set there (ANTHROPIC_API_KEY)."
    />
  );
}

type Props = { swarm?: Swarm; saving: boolean; error: unknown; label: string; onSave: (body: NewSwarm) => void };

/** A swarm's name, repo and base branch, its crew in order, the rrotor it runs on, how many rounds and how it is reviewed. */
export function SwarmEditor({ swarm, saving, error, label, onSave }: Props) {
  const github = useGitHubKey();
  const [name, setName] = useState(swarm?.name ?? '');
  const [repo, setRepo] = useState(swarm?.repo_url ?? '');
  const [base, setBase] = useState(swarm?.base_branch ?? 'main');
  const [members, setMembers] = useState<string[]>(swarm?.members.map((m) => m.id) ?? []);
  const [runsOn, setRunsOn] = useState(swarm?.runs_on ?? '');
  const [rounds, setRounds] = useState(swarm?.rounds ?? 1);
  const [review, setReview] = useState<Review>(swarm?.review ?? 'each_turn');
  const ready = name.trim() !== '' && repo.trim() !== '' && base.trim() !== '' && members.length > 0 && runsOn !== '';
  const save = () => onSave({ name: name.trim(), repo_url: repo.trim(), base_branch: base.trim(), members, runs_on: runsOn, rounds, review });

  return (
    <div className={bs.form}>
      <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Site crew" />
      <div className={bs.pair}>
        <TextField label="GitHub repo" mono value={repo} onChange={(e) => setRepo(e.target.value)} placeholder="https://github.com/acme/site" />
        <TextField label="Base branch" mono value={base} onChange={(e) => setBase(e.target.value)} hint="Each turn starts from it and merges into it." />
      </div>
      <Crew ids={members} onChange={setMembers} />
      <div className={`${bs.pair} ${bs.triple}`}>
        <RunsOn value={runsOn} onChange={setRunsOn} />
        <Select label="Rounds" value={String(rounds)} onChange={(e) => setRounds(Number(e.target.value))} options={ROUNDS} hint="Each round, every bot takes a turn." />
        <Select
          label="Review"
          value={review}
          onChange={(e) => setReview(e.target.value as Review)}
          options={REVIEWS.map(({ value, label: l }) => ({ value, label: l }))}
          hint={REVIEWS.find((r) => r.value === review)?.hint}
        />
      </div>
      {github.data && !github.data.set && (
        <p className={bs.muted}>
          The turns push and open pull requests with your org’s GitHub token: <Link to="/settings/github-token">set it</Link> before the first run.
        </p>
      )}
      <ApiErrorNotice error={error} />
      <div className={bs.row}>
        <Button variant="primary" disabled={!ready} loading={saving} onClick={save}>
          {label}
        </Button>
      </div>
    </div>
  );
}
