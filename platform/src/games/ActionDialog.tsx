import { useState, type FormEvent } from 'react';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Button, Dialog, Select, Switch, TextField, useToast } from '@/ui';
import { useGameAction, type Args } from './api';
import type { Action, Field, Row } from './catalog';
import { Facts } from './DataView';
import styles from './games.module.css';

/** What the fields typed come to: numbers as numbers, ticks as true, blanks left out. */
export function argsFrom(fields: readonly Field[], values: Record<string, string | boolean>): Args {
  const out: Args = {};
  for (const f of fields) {
    const v = values[f.name];
    if (f.kind === 'check') {
      if (v === true) out[f.name] = true;
    } else if (typeof v === 'string' && v.trim() !== '') {
      out[f.name] = f.kind === 'number' ? Number(v) : v.trim();
    }
  }
  return out;
}

/**
 * Runs one action of a game. With nothing to ask and nothing to fear it runs at once; otherwise a dialog asks for
 * what it needs, red when it can't quietly be taken back. Where the game shows what would happen first, that is
 * shown before anything is done.
 */
export function useActionRunner(game: string) {
  const toast = useToast();
  const action = useGameAction(game);
  const [open, setOpen] = useState<{ action: Action; row: Row | null } | null>(null);

  const start = (a: Action, row: Row | null) => {
    if (!a.fields?.length && !a.danger && !a.preview) {
      action.mutate(
        { tool: a.tool, args: a.args ? a.args(row ?? {}) : {} },
        { onSuccess: () => toast.show(`${a.label}: done.`), onError: (e) => toast.show(e.message, 'error') },
      );
      return;
    }
    action.reset();
    setOpen({ action: a, row });
  };

  const dialog = open ? <ActionDialog key={`${open.action.tool}-${open.action.label}`} game={game} action={open.action} row={open.row} onClose={() => setOpen(null)} /> : null;
  return { start, dialog, pending: action.isPending };
}

function ActionDialog({ game, action: a, row, onClose }: { game: string; action: Action; row: Row | null; onClose: () => void }) {
  const toast = useToast();
  const action = useGameAction(game);
  const [values, setValues] = useState<Record<string, string | boolean>>({});
  const [preview, setPreview] = useState<unknown>(undefined);
  const fields = a.fields ?? [];
  const missing = fields.some((f) => f.required && (typeof values[f.name] !== 'string' || !(values[f.name] as string).trim()));
  const reasonShort = fields.some((f) => f.name === 'reason' && typeof values.reason === 'string' && values.reason.trim().length < 3);

  const args = () => ({ ...(a.args ? a.args(row ?? {}) : {}), ...argsFrom(fields, values) });
  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    if (missing || reasonShort) return;
    if (a.preview && preview === undefined) {
      action.mutate({ tool: a.tool, args: args(), preview: true }, { onSuccess: (result) => setPreview(result ?? {}) });
      return;
    }
    action.mutate(
      { tool: a.tool, args: a.preview ? { ...args(), confirm: true } : args() },
      {
        onSuccess: () => {
          toast.show(`${a.label}: done.`);
          onClose();
        },
      },
    );
  };

  const who = row ? String(row.nick ?? row.name?.quoted ?? row.name ?? row.title?.quoted ?? row.card_name ?? row.email ?? row.id ?? '') : '';
  const confirmLabel = a.preview && preview === undefined ? 'Show what happens' : a.label;
  return (
    <Dialog
      open
      size={preview !== undefined ? 'wide' : 'default'}
      onClose={onClose}
      title={who ? `${a.label}: ${who}` : a.label}
      description={a.danger ? 'This can’t quietly be taken back.' : undefined}
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant={a.danger ? 'danger' : 'primary'} loading={action.isPending} disabled={missing || reasonShort} onClick={() => submit()}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <form className={styles.form} onSubmit={submit}>
        {fields.map((f) =>
          f.kind === 'select' ? (
            <Select
              key={f.name}
              label={f.label}
              hint={f.hint}
              options={f.options ?? []}
              value={String(values[f.name] ?? f.options?.[0]?.value ?? '')}
              onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
            />
          ) : f.kind === 'check' ? (
            <div key={f.name} className={styles.check}>
              <Switch checked={values[f.name] === true} onChange={(on: boolean) => setValues((v) => ({ ...v, [f.name]: on }))} label={f.label} />
              <span aria-hidden="true">{f.label}</span>
            </div>
          ) : (
            <TextField
              key={f.name}
              label={f.label}
              hint={f.hint}
              type={f.kind === 'number' ? 'number' : 'text'}
              required={f.required}
              value={String(values[f.name] ?? '')}
              onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
            />
          ),
        )}
        {/* Enter submits, as in any form. */}
        <button type="submit" hidden />
      </form>
      {preview !== undefined && (
        <div className={styles.preview} aria-label="What would happen">
          <h3 className={styles.partTitle}>What would happen</h3>
          <Facts data={preview} depth={1} />
        </div>
      )}
      <ApiErrorNotice error={action.error} />
    </Dialog>
  );
}
