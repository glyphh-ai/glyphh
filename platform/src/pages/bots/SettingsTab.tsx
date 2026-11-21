import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useDeleteBot, type Bot } from '@/api/bots';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { Button, Card, useToast } from '@/ui';
import styles from './bots.module.css';

/** Deleting the bot. */
export function SettingsTab({ bot }: { bot: Bot }) {
  const navigate = useNavigate();
  const toast = useToast();
  const remove = useDeleteBot();
  const [deleting, setDeleting] = useState(false);

  return (
    <div className={styles.stack}>
      <Card>
        <div className={styles.form}>
          <h2 className={styles.name}>Delete this bot</h2>
          <p className={styles.muted}>Its runs and gates go with it. Your connections stay.</p>
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
        description="Its runs and gates go with it. This cannot be undone."
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
