import { useId, useState, type FormEvent } from 'react';
import { useDecide, type AdaModel, type Decision } from '@/api/ada';
import { AdaErrorNotice } from '../AdaErrorNotice';
import { caseFrom, outputOf, outputsOf, rolesOf, type RolePath } from '@/lib/spec';
import { Button, Card, Chip, ProgressBar, Select, TextField } from '@/ui';
import styles from '../ada.module.css';

const percent = (p: number) => `${Math.round(p * 100)}%`;

/** One role's field, by how the spec reads it: a number in its range, words, or a value. */
function RoleField({ role, value, onChange }: { role: RolePath; value: string; onChange: (value: string) => void }) {
  const id = useId();
  const numeric = role.role.numeric_config;
  if (role.role.text_encoding) {
    return (
      <div className={styles.field}>
        <label htmlFor={id} className={styles.label}>
          {role.role.name}
        </label>
        <textarea id={id} className={styles.textarea} value={value} onChange={(e) => onChange(e.target.value)} />
      </div>
    );
  }
  return (
    <TextField
      label={role.role.name}
      type={numeric ? 'number' : 'text'}
      step={numeric ? 'any' : undefined}
      hint={numeric ? `${numeric.min_value} to ${numeric.max_value}` : undefined}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

/** Try it: a case typed into a form built from the spec, decided as `POST /v1/decide` decides it. */
export function TryTab({ model }: { model: AdaModel }) {
  const decide = useDecide();
  // Key parts name a case; they say nothing of it, so they are not asked for.
  const roles = rolesOf(model.spec).filter((r) => !r.role.key_part);
  const outputs = outputsOf(model.spec);
  const [values, setValues] = useState<Record<string, string>>({});
  const [output, setOutput] = useState('default');
  const groups = [...new Set(roles.map((r) => `${r.layer}.${r.segment}`))];

  const submit = (event: FormEvent) => {
    event.preventDefault();
    decide.mutate({ model: model.name, data: caseFrom(model.spec, values), ...(output === 'default' ? {} : { output }) });
  };

  return (
    <>
      <Card>
        <form className={styles.form} onSubmit={submit}>
          <p className={styles.about}>Fill in what you know of a case. What you leave out weighs nothing.</p>
          {groups.map((group) => (
            <div key={group} className={styles.group}>
              {groups.length > 1 && <span className={styles.groupTitle}>{group}</span>}
              {roles
                .filter((r) => `${r.layer}.${r.segment}` === group)
                .map((role) => (
                  <RoleField key={role.path} role={role} value={values[role.path] ?? ''} onChange={(v) => setValues((all) => ({ ...all, [role.path]: v }))} />
                ))}
            </div>
          ))}
          {outputs.length > 1 && (
            <Select label="Decide" value={output} onChange={(e) => setOutput(e.target.value)} options={outputs.map((o) => ({ value: o, label: o === 'default' ? 'The outcome' : o }))} />
          )}
          <AdaErrorNotice error={decide.error} />
          <div className={styles.actions}>
            <Button variant="primary" type="submit" loading={decide.isPending}>
              Decide
            </Button>
          </div>
        </form>
      </Card>
      {decide.data && <Answer decision={decide.data} priced={Boolean(outputOf(model.spec, output)?.costs)} />}
    </>
  );
}

/** The answer, how sure it is, whether a person should decide, each outcome's probability, and the precedents it stands on. */
function Answer({ decision, priced }: { decision: Decision; priced: boolean }) {
  const probabilities = Object.entries(decision.probabilities).sort((a, b) => b[1] - a[1]);
  const confidence = probabilities[0]?.[1] ?? 0;
  return (
    <Card aria-label="Answer">
      <span className={styles.meta}>Answer · version {decision.version}</span>
      {decision.outcome === null ? (
        <p className={styles.about}>Nothing is known yet: no precedent is near enough. A person should decide, and the case be recorded.</p>
      ) : (
        <>
          <span className={styles.big}>{decision.outcome}</span>
          <div className={styles.chips}>
            <Chip tone="blue">Confidence {percent(confidence)}</Chip>
            {decision.ask && <Chip tone="amber">A person should decide</Chip>}
            {priced && decision.expected_cost !== null && <Chip>Expected cost {decision.expected_cost}</Chip>}
          </div>
          <div className={styles.bars} aria-label="Probabilities">
            {probabilities.map(([outcome, p]) => (
              <div key={outcome} className={styles.bar}>
                <span className={styles.mono}>{outcome}</span>
                <ProgressBar value={p} max={1} label={`Probability of ${outcome}`} />
                <span className={styles.num}>{percent(p)}</span>
              </div>
            ))}
          </div>
        </>
      )}
      {decision.receipts.length > 0 && (
        <>
          <h3 className={styles.cardTitle}>Precedents</h3>
          <div className={styles.tableBox}>
            <table className={styles.table} aria-label="Precedents">
              <thead>
                <tr>
                  <th scope="col">Case</th>
                  <th scope="col">Outcome</th>
                  <th scope="col">Similarity</th>
                </tr>
              </thead>
              <tbody>
                {decision.receipts.map((receipt) => (
                  <tr key={receipt.id}>
                    <td className={styles.mono}>{receipt.id}</td>
                    <td>{receipt.outcome ?? '—'}</td>
                    <td className={styles.num}>{percent(receipt.sim)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  );
}
