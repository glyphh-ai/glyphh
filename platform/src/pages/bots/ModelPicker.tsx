import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import { useBotKey, useBotModels, type BotModel } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { rate } from '@/lib/format';
import { Button, Chip, Skeleton, TextField } from '@/ui';
import styles from './bots.module.css';

const PER_PAGE = 6;

const per = (input: number, output: number) => `${rate(input)} in · ${rate(output)} out`;

function Row({ model, checked, name, ownKey, onPick }: { model: BotModel; checked: boolean; name: string; ownKey: boolean; onPick: () => void }) {
  return (
    <li>
      <label className={styles.model}>
        <input type="radio" name={name} checked={checked} onChange={onPick} aria-label={model.name} />
        <span className={styles.row}>
          <span className={styles.toolName}>{model.name}</span>
          {model.default && <Chip tone="violet">Default</Chip>}
        </span>
        <span className={styles.prices}>
          <span className={ownKey ? undefined : styles.pays}>Glyphh’s key: {per(model.input_cents_per_mtok, model.output_cents_per_mtok)}</span>
          <span className={ownKey ? styles.pays : undefined}>Your key: {per(model.own_key_input_cents_per_mtok, model.own_key_output_cents_per_mtok)}</span>
        </span>
      </label>
    </li>
  );
}

/**
 * The Claude model a bot runs on, out of every one the server offers: searched by name, a page of six at a time, each
 * with both its prices per million tokens (on Glyphh's key: the rate and the markup; on the org's own key: the markup
 * only). The price the org pays now is the brighter one.
 */
export function ModelPicker({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const models = useBotModels();
  const key = useBotKey();
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const ownKey = key.data?.set ?? false;
  const found = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (models.data?.models ?? []).filter((m) => !needle || `${m.name} ${m.id}`.toLowerCase().includes(needle));
  }, [models.data, q]);
  const last = Math.max(1, Math.ceil(found.length / PER_PAGE));
  const at = Math.min(page, last);
  const shown = found.slice((at - 1) * PER_PAGE, at * PER_PAGE);
  const chosen = models.data?.models.find((m) => m.id === value);

  return (
    <div className={styles.field} role="group" aria-label="Model">
      <span className={styles.label}>Model</span>
      <span className={styles.muted}>
        {chosen ? `${chosen.name} · ` : value ? `${value} · ` : ''}
        {ownKey ? 'Runs on your Claude key: you pay Glyphh the markup only.' : 'Runs on Glyphh’s Claude key: you pay the rate and the markup.'}{' '}
        <Link to="/settings/claude-key">Claude key</Link>
      </span>
      <TextField
        label="Search models"
        type="search"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setPage(1);
        }}
        placeholder="Search by name"
      />
      <ApiErrorNotice error={models.error} />
      <ul className={styles.models} aria-label="Models" aria-busy={models.isPending || undefined}>
        {models.isPending
          ? Array.from({ length: PER_PAGE }, (_, i) => (
              <li key={i} className={styles.model} aria-hidden="true">
                <Skeleton height={14} width={14} />
                <Skeleton height={14} width="50%" />
                <Skeleton height={12} width={180} />
              </li>
            ))
          : shown.map((m) => <Row key={m.id} model={m} name="bot-model" checked={m.id === value} ownKey={ownKey} onPick={() => onChange(m.id)} />)}
        {models.data && shown.length === 0 && (
          <li className={styles.model}>
            <span />
            <span className={styles.muted}>No model matches “{q.trim()}”.</span>
          </li>
        )}
      </ul>
      <div className={styles.pager}>
        <span>
          {found.length === 0 ? 'None' : `${(at - 1) * PER_PAGE + 1}–${Math.min(at * PER_PAGE, found.length)} of ${found.length}`}
          {models.data ? ` · prices per million tokens, ${models.data.markup_pct}% markup` : ''}
        </span>
        <span className={styles.row}>
          <Button size="sm" disabled={at <= 1} onClick={() => setPage(at - 1)}>
            Previous
          </Button>
          <Button size="sm" disabled={at >= last} onClick={() => setPage(at + 1)}>
            Next
          </Button>
        </span>
      </div>
    </div>
  );
}
