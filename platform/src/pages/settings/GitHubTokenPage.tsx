import { useState } from 'react';
import { useGitHubKey, useRemoveGitHubKey, useSetGitHubKey } from '@/api/swarms';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { date } from '@/lib/format';
import { Button, Skeleton, TextField, useToast } from '@/ui';
import { SettingsTitle } from './SettingsTitle';
import styles from '../bots/bots.module.css';

const NEW_TOKEN = 'https://github.com/settings/personal-access-tokens/new';

/**
 * The org's GitHub token for its swarms: their turns clone the repo, push each turn's branch and open, merge or close
 * its pull request with it, on the org's rrotor. Tried with GitHub before it is kept, kept encrypted, shown by its
 * last characters and the account it is.
 */
export function GitHubTokenPage() {
  const toast = useToast();
  const key = useGitHubKey();
  const set = useSetGitHubKey();
  const remove = useRemoveGitHubKey();
  const [typed, setTyped] = useState('');
  const [removing, setRemoving] = useState(false);
  const save = () =>
    set.mutate(typed.trim(), {
      onSuccess: (k) => {
        setTyped('');
        toast.show(`Saved: your swarms work on GitHub as ${k.login}.`);
      },
    });

  return (
    <>
      <SettingsTitle title="GitHub token">The token your swarms push branches and open pull requests with.</SettingsTitle>
      <SettingsSection
        title="Your token"
        description="Kept encrypted on the server and sent to your rrotor only for a swarm's turn; only its last characters are ever shown again."
      >
        <ApiErrorNotice error={key.error} />
        {key.isPending ? (
          <Skeleton height={40} width="60%" />
        ) : key.data?.set ? (
          <div className={styles.spread}>
            <span>
              <span className={styles.toolName}>
                Token ending {key.data.hint} · {key.data.login}
              </span>
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
              label={key.data.set ? 'Replace it' : 'GitHub token'}
              type="password"
              autoComplete="off"
              mono
              placeholder="github_pat_…"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              hint="A fine-grained token for the swarms' repos: Contents and Pull requests, read and write."
            />
            <span className={styles.muted}>
              <a href={NEW_TOKEN} target="_blank" rel="noreferrer">
                Make one on GitHub
              </a>
            </span>
            <ApiErrorNotice error={set.error} />
            <div className={styles.row}>
              <Button variant="primary" disabled={typed.trim() === ''} loading={set.isPending} onClick={save}>
                Save token
              </Button>
            </div>
          </div>
        )}
      </SettingsSection>
      <ConfirmDialog
        open={removing}
        title="Remove your GitHub token?"
        description="Your swarms cannot run until you set one again."
        confirmLabel="Remove"
        pending={remove.isPending}
        error={remove.error}
        onConfirm={() =>
          remove.mutate(undefined, {
            onSuccess: () => {
              setRemoving(false);
              toast.show('Your GitHub token is removed.');
            },
          })
        }
        onClose={() => setRemoving(false)}
      />
    </>
  );
}
