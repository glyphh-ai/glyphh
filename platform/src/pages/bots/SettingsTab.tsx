import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useDeleteBot, useUpdateBot, type Bot } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { Button, Card, TextField, useToast } from '@/ui';
import styles from './bots.module.css';

/** How far one run may go (turns, dollars), and deleting the bot. */
export function SettingsTab({ bot }: { bot: Bot }) {
  const navigate = useNavigate();
  const toast = useToast();
  const update = useUpdateBot(bot.slug);
  const remove = useDeleteBot();
  const [turns, setTurns] = useState(String(bot.limits.max_turns));
  const [usd, setUsd] = useState(String(bot.limits.usd_per_run));
  const [deleting, setDeleting] = useState(false);
  const maxTurns = Number(turns);
  const usdPerRun = Number(usd);
  const ready = Number.isInteger(maxTurns) && maxTurns > 0 && Number.isFinite(usdPerRun) && usdPerRun > 0;

  const save = () =>
    update.mutate({ limits: { max_turns: maxTurns, usd_per_run: usdPerRun } }, { onSuccess: () => toast.show(`${bot.name}’s limits are saved.`) });

  return (
    <div className={styles.stack}>
      <Card>
        <div className={styles.form}>
          <h2 className={styles.name}>Limits</h2>
          <TextField
            label="Most turns a run may take"
            inputMode="numeric"
            value={turns}
            onChange={(e) => setTurns(e.target.value)}
            error={ready || Number.isInteger(maxTurns) ? undefined : 'A whole number.'}
          />
          <TextField label="Most a run may cost, in dollars" inputMode="decimal" value={usd} onChange={(e) => setUsd(e.target.value)} />
          <ApiErrorNotice error={update.error} />
          <div className={styles.row}>
            <Button variant="primary" disabled={!ready} loading={update.isPending} onClick={save}>
              Save limits
            </Button>
          </div>
        </div>
      </Card>
      <Card>
        <div className={styles.form}>
          <h2 className={styles.name}>Delete this bot</h2>
          <p className={styles.muted}>Its runs go with it. Your connections and Ada models stay.</p>
          <div className={styles.row}>
            <Button variant="danger" icon="trash" onClick={() => setDeleting(true)}>
              Delete bot
            </Button>
          </div>
        </div>
      </Card>
      <ConfirmDialog
        open={deleting}
        title={`Delete ${bot.name}?`}
        description="Its runs go with it. This cannot be undone."
        confirmLabel="Delete"
        pending={remove.isPending}
        error={remove.error}
        onConfirm={() =>
          remove.mutate(bot.slug, {
            onSuccess: () => {
              toast.show(`${bot.name} is deleted.`);
              navigate('/bots', { replace: true });
            },
          })
        }
        onClose={() => setDeleting(false)}
      />
    </div>
  );
}
