import { useMemo, useState, type FormEvent } from 'react';
import { useActivate, useAdaVersions, usePutSpec, type AdaModel, type AdaVersion, type VersionChange } from '@/api/ada';
import { AdaErrorNotice } from '../AdaErrorNotice';
import { date } from '@/lib/format';
import { checkSpec, specText } from '@/lib/spec';
import { Button, Card, Chip, CodeBlock, LoadingCard, TextField } from '@/ui';
import { SpecEditor } from '../SpecEditor';
import { ChangeResult } from './ChangeResult';
import styles from '../ada.module.css';

/** The live spec, a new version from an edited one, and every version with a way back to it. */
export function SpecTab({ model }: { model: AdaModel }) {
  const [editing, setEditing] = useState(false);
  const [change, setChange] = useState<VersionChange | null>(null);

  return (
    <>
      <Card>
        <div className={styles.leverHead}>
          <h2 className={styles.cardTitle}>Version {model.version}’s spec</h2>
          {!editing && (
            <Button size="sm" onClick={() => setEditing(true)}>
              Edit spec
            </Button>
          )}
        </div>
        {editing ? (
          <EditSpec
            model={model}
            onDone={(made) => {
              setEditing(false);
              setChange(made);
            }}
            onCancel={() => setEditing(false)}
          />
        ) : (
          <CodeBlock code={specText(model.spec)} label="spec" />
        )}
        {change && <ChangeResult model={model.name} change={change} />}
      </Card>
      <Versions model={model} />
    </>
  );
}

function EditSpec({ model, onDone, onCancel }: { model: AdaModel; onDone: (change: VersionChange) => void; onCancel: () => void }) {
  const put = usePutSpec(model.name);
  const [text, setText] = useState(specText(model.spec));
  const [note, setNote] = useState('');
  const checked = useMemo(() => checkSpec(text), [text]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (checked.spec) put.mutate({ spec: checked.spec, ...(note.trim() ? { note: note.trim() } : {}) }, { onSuccess: onDone });
  };

  return (
    <form className={styles.form} onSubmit={submit}>
      <SpecEditor value={text} onChange={setText} checked={checked} />
      <TextField label="Why" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} placeholder="Kept with the version" />
      <p className={styles.meta}>
        A change that only reads the cases differently is live at once. Adding or taking away roles, or changing the seed, dimension or lexicon,
        rewrites the cases first while this version serves.
      </p>
      <AdaErrorNotice error={put.error} />
      <div className={styles.actions}>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button variant="primary" type="submit" loading={put.isPending} disabled={!checked.spec}>
          Save as a new version
        </Button>
      </div>
    </form>
  );
}

function status(version: AdaVersion) {
  if (version.active) return <Chip tone="green" dot>Live</Chip>;
  if (version.gone) return <Chip>Dropped</Chip>;
  if (!version.ready) return <Chip tone="amber">Being made</Chip>;
  return null;
}

/** Every version, newest first; any ready one can be made live again (a rollback). */
function Versions({ model }: { model: AdaModel }) {
  const versions = useAdaVersions(model.name);
  const activate = useActivate(model.name);
  const [change, setChange] = useState<VersionChange | null>(null);

  return (
    <Card>
      <h2 className={styles.cardTitle}>Versions</h2>
      {versions.isPending && <LoadingCard lines={3} />}
      <AdaErrorNotice error={versions.error ?? activate.error} />
      {change && <ChangeResult model={model.name} change={change} />}
      {versions.data && (
        <div className={styles.tableBox}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Version</th>
                <th scope="col">Why</th>
                <th scope="col">Made</th>
                <th scope="col">Status</th>
                <th scope="col">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {[...versions.data].reverse().map((version) => (
                <tr key={version.version}>
                  <td className={styles.num}>v{version.version}</td>
                  <td>{version.note || '—'}</td>
                  <td className={styles.num}>{date(version.made_at)}</td>
                  <td>{status(version)}</td>
                  <td>
                    {!version.active && version.ready && !version.gone && (
                      <Button
                        size="sm"
                        loading={activate.isPending && activate.variables === version.version}
                        onClick={() => activate.mutate(version.version, { onSuccess: setChange })}
                      >
                        Make live
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
