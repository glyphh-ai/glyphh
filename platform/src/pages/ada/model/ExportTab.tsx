import { useState, type FormEvent } from 'react';
import { useStartExport, type AdaModel } from '@/api/ada';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ButtonLink, Card, Select, Button } from '@/ui';
import { JobProgress } from '../JobProgress';
import styles from '../ada.module.css';

const formats = [
  { value: 'jsonl', label: 'JSON Lines: the precedents, every spec version and what was learned, zipped' },
  { value: 'ada_sqlite', label: 'SQLite: a kernel store of the precedents' },
];

/** Everything of the model back out, as a job whose file downloads by a one-hour link. */
export function ExportTab({ model }: { model: AdaModel }) {
  const start = useStartExport(model.name);
  const [format, setFormat] = useState<'jsonl' | 'ada_sqlite'>('jsonl');
  const [job, setJob] = useState<string | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    start.mutate(format, { onSuccess: (made) => setJob(made.id) });
  };

  return (
    <Card>
      <form className={styles.form} onSubmit={submit}>
        <p className={styles.about}>Your model is yours: export it whenever you like. A JSON Lines export imports into a model of the same spec and answers the same.</p>
        <Select label="Format" value={format} onChange={(e) => setFormat(e.target.value as 'jsonl' | 'ada_sqlite')} options={formats} />
        <ApiErrorNotice error={start.error} />
        {job && (
          <JobProgress key={job} id={job} label="Exporting">
            {(done) =>
              done.download && (
                <div className={styles.chips} role="status">
                  <ButtonLink variant="primary" href={done.download.url} download>
                    Download
                  </ButtonLink>
                  <span className={styles.meta}>The link works for an hour.</span>
                </div>
              )
            }
          </JobProgress>
        )}
        <div className={styles.actions}>
          <Button variant={job ? 'secondary' : 'primary'} type="submit" loading={start.isPending}>
            Export
          </Button>
        </div>
      </form>
    </Card>
  );
}
