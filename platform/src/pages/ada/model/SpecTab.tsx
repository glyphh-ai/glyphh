import { useMemo, useState, type FormEvent } from 'react';
import { usePutSpec, type AdaModel, type VersionChange } from '@/api/ada';
import { AdaErrorNotice } from '../AdaErrorNotice';
import { checkSpec, specText } from '@/lib/spec';
import { Button, Card, CodeBlock, TextField } from '@/ui';
import { SpecEditor } from '../SpecEditor';
import { ChangeResult } from './ChangeResult';
import styles from '../ada.module.css';

/** The live spec, and a new version from an edited one (every version, and the way back to one, is the Versions tab). */
export function SpecTab({ model }: { model: AdaModel }) {
  const [editing, setEditing] = useState(false);
  const [change, setChange] = useState<VersionChange | null>(null);

  return (
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
      <TextField
        label="Release notes"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        maxLength={500}
        placeholder="What this version is for (left empty, the Versions tab shows what changed)"
      />
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

