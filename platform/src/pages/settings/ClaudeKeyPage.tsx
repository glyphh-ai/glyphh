import { useState } from 'react';
import { useBotKey, useBotModels, useRemoveBotKey, useSetBotKey } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { date } from '@/lib/format';
import { Button, Chip, Skeleton, TextField, useToast } from '@/ui';
import { SettingsTitle } from './SettingsTitle';
import styles from '../bots/bots.module.css';

/**
 * The org's own Claude key for its bots, or none (bots then run on Glyphh's). Both are billed: on the org's key it
 * pays Anthropic for the tokens and Glyphh the markup only; on Glyphh's it pays Glyphh the rate and the markup.
 */
export function ClaudeKeyPage() {
  const toast = useToast();
  const key = useBotKey();
  const models = useBotModels();
  const set = useSetBotKey();
  const remove = useRemoveBotKey();
  const [typed, setTyped] = useState('');
  const [removing, setRemoving] = useState(false);
  const markup = models.data?.markup_pct ?? 20;

  const save = () =>
    set.mutate(typed.trim(), {
      onSuccess: () => {
        setTyped('');
        toast.show('Your Claude key is saved. Bots run on it from their next run.');
      },
    });

  return (
    <>
      <SettingsTitle title="Claude key">The Claude key your bots run on: yours, or Glyphh’s.</SettingsTitle>
      <SettingsSection
        title="How it is billed"
        description="Either way you are billed by the tokens your bots use; the key decides what the bill holds."
      >
        <ul className={styles.list}>
          <li className={styles.item}>
            <span className={styles.grow}>
              <span className={styles.toolName}>Your own key</span>
              <span className={`${styles.muted} ${styles.block}`}>Anthropic bills you for the tokens. Glyphh bills the {markup}% markup only.</span>
            </span>
            {key.data?.set && <Chip tone="violet">In use</Chip>}
          </li>
          <li className={styles.item}>
            <span className={styles.grow}>
              <span className={styles.toolName}>Glyphh’s key</span>
              <span className={`${styles.muted} ${styles.block}`}>Glyphh bills the tokens at Anthropic’s rate plus {markup}%. Nothing to set up.</span>
            </span>
            {key.data && !key.data.set && <Chip tone="violet">In use</Chip>}
          </li>
        </ul>
      </SettingsSection>
      <SettingsSection title="Your key" description="Kept encrypted on the server; only its last characters are ever shown again.">
        <ApiErrorNotice error={key.error} />
        {key.isPending ? (
          <Skeleton height={40} width="60%" />
        ) : key.data?.set ? (
          <div className={styles.spread}>
            <span>
              <span className={styles.toolName}>Key ending {key.data.hint.replace(/^…/, '')}</span>
              {key.data.set_at && <span className={`${styles.muted} ${styles.block}`}>Saved {date(key.data.set_at)}</span>}
            </span>
            <Button variant="ghost" icon="trash" onClick={() => setRemoving(true)}>
              Remove
            </Button>
          </div>
        ) : null}
        {key.data && (
          <div className={styles.form}>
            <TextField
              label={key.data.set ? 'Replace it' : 'Claude API key'}
              type="password"
              autoComplete="off"
              mono
              placeholder="sk-ant-…"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              hint="From console.anthropic.com, under API keys."
            />
            <ApiErrorNotice error={set.error} />
            <div className={styles.row}>
              <Button variant="primary" disabled={typed.trim() === ''} loading={set.isPending} onClick={save}>
                Save key
              </Button>
            </div>
          </div>
        )}
      </SettingsSection>
      <ConfirmDialog
        open={removing}
        title="Remove your Claude key?"
        description={`Bots run on Glyphh’s key from their next run, billed at the rate plus ${markup}%.`}
        confirmLabel="Remove"
        pending={remove.isPending}
        error={remove.error}
        onConfirm={() =>
          remove.mutate(undefined, {
            onSuccess: () => {
              setRemoving(false);
              toast.show('Your Claude key is removed.');
            },
          })
        }
        onClose={() => setRemoving(false)}
      />
    </>
  );
}
