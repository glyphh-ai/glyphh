import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useId, useState, type ChangeEvent, type FormEvent } from 'react';
import { modelReads, uploadFile, useStartImport, type AdaModel, type ImportFormat, type Imported } from '@/api/ada';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { csvHeader, guessMapping, type Target } from '@/lib/csv';
import { plural } from '@/lib/format';
import { outputsOf, rolesOf } from '@/lib/spec';
import { Button, Card, Select } from '@/ui';
import { JobProgress } from '../JobProgress';
import styles from '../ada.module.css';

const formats = [
  { value: 'csv', label: 'CSV, a column per role' },
  { value: 'jsonl', label: 'JSON Lines, a case per line' },
];
const skip = '';
const contentType: Record<ImportFormat, string> = { csv: 'text/csv', jsonl: 'application/x-ndjson' };

const formatOf = (file: File): ImportFormat => (/\.(jsonl|ndjson|json)$/i.test(file.name) ? 'jsonl' : 'csv');

/** A CSV or JSON Lines file of cases into the model, as a job: a CSV's columns mapped to the spec first, then its progress. */
export function ImportTab({ model }: { model: AdaModel }) {
  const client = useQueryClient();
  const fileId = useId();
  const start = useStartImport(model.name);
  const [file, setFile] = useState<File | null>(null);
  const [format, setFormat] = useState<ImportFormat>('csv');
  const [headers, setHeaders] = useState<string[]>([]);
  const [mapping, setMapping] = useState<Record<string, Target>>({});
  const [job, setJob] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<unknown>(null);

  const roles = rolesOf(model.spec);
  const outputs = outputsOf(model.spec);
  const targets = [
    { value: skip, label: 'Skip this column' },
    ...roles.map((r) => ({ value: r.path, label: r.path })),
    ...outputs.map((o) => (o === 'default' ? { value: 'outcome', label: 'The outcome' } : { value: `outcome.${o}`, label: `The ${o} outcome` })),
    { value: 'ts', label: 'When it happened (ts)' },
    { value: 'id', label: 'Its id' },
  ];

  const choose = async (event: ChangeEvent<HTMLInputElement>) => {
    const picked = event.target.files?.[0] ?? null;
    setFile(picked);
    setJob(null);
    if (!picked) return;
    const kind = formatOf(picked);
    setFormat(kind);
    const found = csvHeader(await picked.slice(0, 64 * 1024).text());
    setHeaders(found);
    setMapping(guessMapping(found, roles, outputs));
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) return;
    setUploadError(null);
    const body = format === 'csv' ? { format, mapping } : { format };
    start.mutate(body, {
      onSuccess: async (started) => {
        setUploading(true);
        try {
          await uploadFile(started.upload.url, file, contentType[format]);
          setJob(started.id);
        } catch (error) {
          setUploadError(error);
        } finally {
          setUploading(false);
        }
      },
    });
  };

  const refresh = useCallback(() => {
    for (const queryKey of modelReads(model.name)) void client.invalidateQueries({ queryKey });
  }, [client, model.name]);

  const mapped = Object.values(mapping).some((target) => target !== null);

  return (
    <Card>
      <form className={styles.form} onSubmit={(e) => void submit(e)}>
        <p className={styles.about}>
          Load your history: each case with its outcome. Cases with an id the model holds replace it. The model learns once at the end.
        </p>
        <div className={styles.row}>
          <div className={styles.field}>
            <label htmlFor={fileId} className={styles.label}>
              File
            </label>
            <input id={fileId} type="file" accept=".csv,.jsonl,.ndjson,.json,text/csv" onChange={(e) => void choose(e)} />
          </div>
          <Select label="Format" value={format} onChange={(e) => setFormat(e.target.value as ImportFormat)} options={formats} />
        </div>

        {file && format === 'csv' && headers.length > 0 && (
          <div className={styles.tableBox}>
            <table className={styles.table} aria-label="Columns">
              <thead>
                <tr>
                  <th scope="col">Column</th>
                  <th scope="col">Goes to</th>
                </tr>
              </thead>
              <tbody>
                {headers.map((header) => (
                  <tr key={header}>
                    <td className={styles.mono}>{header}</td>
                    <td>
                      <Select
                        label={`Where ${header} goes`}
                        value={mapping[header] ?? skip}
                        onChange={(e) => setMapping((m) => ({ ...m, [header]: e.target.value === skip ? null : e.target.value }))}
                        options={targets}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {file && format === 'jsonl' && (
          <p className={styles.meta}>
            Each line: <code className={styles.mono}>{'{"data": {…}, "outcome": "…"}'}</code>, the data in the spec’s shape, layer by segment by role.
          </p>
        )}

        <ApiErrorNotice error={start.error ?? uploadError} />
        {uploading && (
          <p className={styles.meta} role="status">
            Sending {file?.name}…
          </p>
        )}
        {job && (
          <JobProgress id={job} label={`Importing ${file?.name ?? 'the file'}`} onDone={refresh}>
            {(done) => <ImportResult result={done.result as Imported} />}
          </JobProgress>
        )}
        <div className={styles.actions}>
          <Button variant="primary" type="submit" loading={start.isPending || uploading} disabled={!file || (format === 'csv' && !mapped)}>
            Import
          </Button>
        </div>
      </form>
    </Card>
  );
}

/** What an import did: its rows, what went in, and the first refused rows by number. */
function ImportResult({ result }: { result: Imported }) {
  return (
    <div className={styles.form} role="status">
      <p className={styles.good}>
        {plural(result.rows, 'row')}: {result.recorded.toLocaleString('en-GB')} recorded ({result.added.toLocaleString('en-GB')} new,{' '}
        {result.replaced.toLocaleString('en-GB')} replaced), {result.refused.toLocaleString('en-GB')} refused.
      </p>
      {result.refusals.length > 0 && (
        <div className={styles.tableBox}>
          <table className={styles.table} aria-label="Refused rows">
            <thead>
              <tr>
                <th scope="col">Row</th>
                <th scope="col">Where</th>
                <th scope="col">Why</th>
              </tr>
            </thead>
            <tbody>
              {result.refusals.map((refusal) => (
                <tr key={`${refusal.row}-${refusal.path}`}>
                  <td className={styles.num}>{refusal.row}</td>
                  <td className={styles.mono}>{refusal.path || '—'}</td>
                  <td>{refusal.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
