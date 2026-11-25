import { useMemo, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router';
import { adaFix, useAdaReleases, useCreateAdaModel } from '@/api/ada';
import { AdaErrorNotice } from './AdaErrorNotice';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { choosable, optionText } from '@/lib/releases';
import { checkSpec, examples, modelNamePattern, specText } from '@/lib/spec';
import { Button, Card, Select, TextField } from '@/ui';
import { SpecEditor } from './SpecEditor';
import styles from './ada.module.css';

const blank = { name: 'cases', layers: [{ name: 'case', segments: [{ name: 'about', roles: [{ name: 'kind' }] }] }] };
const starts = [{ value: 'blank', label: 'A blank spec' }, ...examples.map((example) => ({ value: example.id, label: example.label }))];

/** A new model: its name, its spec, checked as it is typed, from an example or blank, and its Ada (the latest stable first). */
export function NewModelPage() {
  const navigate = useNavigate();
  const create = useCreateAdaModel();
  const releases = useAdaReleases();
  const [name, setName] = useState('');
  const [picked, setPicked] = useState<string | null>(null);
  // Until the versions are read, or if they can't be, none is sent: the server makes it on the latest stable.
  const ada = picked ?? releases.data?.latest_stable;
  const fix = adaFix(create.error);
  const [start, setStart] = useState('blank');
  const [text, setText] = useState(specText(blank));
  const checked = useMemo(() => checkSpec(text), [text]);
  const nameProblem = name && !modelNamePattern.test(name) ? 'Lower case letters, digits, _ . and -, up to 63, starting with a letter or digit.' : undefined;

  const pick = (id: string) => {
    setStart(id);
    const example = examples.find((e) => e.id === id);
    setText(specText(example?.spec ?? blank));
    if (example && !name) setName(example.spec.name);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!checked.spec) return;
    create.mutate({ name, spec: checked.spec, ...(ada ? { ada } : {}) }, { onSuccess: (made) => navigate(`/models/${encodeURIComponent(made.name)}`) });
  };

  return (
    <>
      <PageHeader title="New model" description="Describe your cases once: the roles each case has, and the outcomes to decide." />
      <Card>
        <form className={styles.form} onSubmit={submit}>
          <div className={styles.row}>
            <TextField label="Name" mono value={name} onChange={(e) => setName(e.target.value.trim())} maxLength={63} placeholder="tickets" error={nameProblem} autoFocus />
            <Select label="Start from" value={start} onChange={(e) => pick(e.target.value)} options={starts} />
            {releases.data && ada && (
              <Select
                label="Ada"
                value={ada}
                onChange={(e) => setPicked(e.target.value)}
                options={choosable(releases.data).map((r) => ({ value: r.name, label: optionText(r, releases.data) }))}
                hint="It answers with this version until you upgrade it."
              />
            )}
          </div>
          <SpecEditor value={text} onChange={setText} checked={checked} />
          <AdaErrorNotice
            error={create.error}
            action={
              fix &&
              fix !== ada && (
                <Button
                  size="sm"
                  onClick={() => {
                    setPicked(fix);
                    create.reset();
                  }}
                >
                  Choose {fix}
                </Button>
              )
            }
          />
          <div className={styles.actions}>
            <Button variant="ghost" onClick={() => navigate('/models')}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" loading={create.isPending} disabled={!checked.spec || !name || Boolean(nameProblem)}>
              Make model
            </Button>
          </div>
        </form>
      </Card>
    </>
  );
}
