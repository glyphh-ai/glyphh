import { useState, type FormEvent } from 'react';
import { useAdaLevers, usePatchSettings, type AdaModel, type LeverValue, type Levers, type VersionChange } from '@/api/ada';
import { AdaErrorNotice } from '../AdaErrorNotice';
import { effectText, leverFromText, leverProblem, levers as known } from '@/lib/spec';
import { Button, Card, Chip, LoadingCard, TextField } from '@/ui';
import { ChangeResult } from './ChangeResult';
import { draftOf, leverFor, LeverInput, type Draft } from './LeverInput';
import styles from '../ada.module.css';

/** The levers this platform knows first, in its order, then any other the server names. */
function ordered(settings: Levers['settings']): string[] {
  const names = known.map((lever) => lever.name).filter((name) => name in settings);
  return [...names, ...Object.keys(settings).filter((name) => !names.includes(name))];
}

/** The changed levers, as values, and any out of range. */
export function changesOf(current: Levers['settings'], draft: Record<string, Draft>) {
  const changes: Record<string, LeverValue> = {};
  const problems: Record<string, string> = {};
  for (const [name, typed] of Object.entries(draft)) {
    const lever = leverFor(name, current[name] ?? null);
    const value = typeof typed === 'boolean' ? typed : leverFromText(lever, typed);
    if (value === current[name]) continue;
    const problem = typeof value === 'number' && Number.isNaN(value) ? 'A number.' : leverProblem(name, value);
    if (problem) problems[name] = problem;
    else changes[name] = value;
  }
  return { changes, problems };
}

/** Every lever as it stands on the live version; saving the changed ones makes a new version. */
export function SettingsTab({ model }: { model: AdaModel }) {
  const levers = useAdaLevers(model.name);
  // Kept here: the form starts afresh on the new version.
  const [change, setChange] = useState<VersionChange | null>(null);
  if (levers.isPending) return <LoadingCard lines={6} />;
  if (levers.error) return <AdaErrorNotice error={levers.error} />;
  return <SettingsForm key={levers.data.version} model={model} levers={levers.data} change={change} setChange={setChange} />;
}

type FormProps = { model: AdaModel; levers: Levers; change: VersionChange | null; setChange: (change: VersionChange) => void };

function SettingsForm({ model, levers, change, setChange }: FormProps) {
  const patch = usePatchSettings(model.name);
  const [draft, setDraft] = useState<Record<string, Draft>>(() => Object.fromEntries(Object.entries(levers.settings).map(([k, v]) => [k, draftOf(v)])));
  const [note, setNote] = useState('');
  const { changes, problems } = changesOf(levers.settings, draft);
  const changed = Object.keys(changes).length;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    patch.mutate({ changes, ...(note.trim() ? { note: note.trim() } : {}) }, { onSuccess: setChange });
  };

  return (
    <Card>
      <form className={styles.form} onSubmit={submit}>
        <p className={styles.about}>
          Version {levers.version}’s levers. Saving makes a new version; the one before stays, to go back to. Backtest a change first to see what
          it does on your own cases.
        </p>
        <div>
          {ordered(levers.settings).map((name) => {
            const lever = leverFor(name, levers.settings[name] ?? null);
            return (
              <div key={name} className={styles.lever}>
                <div className={styles.leverHead}>
                  <span className={styles.leverName}>
                    <strong>{lever.label}</strong>
                    <code className={styles.mono}>{name}</code>
                  </span>
                  <Chip tone={lever.effect === 'reencode' ? 'amber' : 'neutral'}>{effectText[lever.effect]}</Chip>
                </div>
                {lever.about && <p className={styles.about}>{lever.about}</p>}
                <LeverInput lever={lever} value={draft[name] ?? ''} onChange={(value) => setDraft((d) => ({ ...d, [name]: value }))} error={problems[name]} />
              </div>
            );
          })}
        </div>
        <TextField label="Why" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} placeholder="Kept with the version" />
        <AdaErrorNotice error={patch.error} />
        {change && <ChangeResult model={model.name} change={change} />}
        <div className={styles.actions}>
          <Button variant="primary" type="submit" loading={patch.isPending} disabled={changed === 0 || Object.keys(problems).length > 0}>
            {changed === 0 ? 'Save as a new version' : `Save ${changed === 1 ? '1 change' : `${changed} changes`} as a new version`}
          </Button>
        </div>
      </form>
    </Card>
  );
}
