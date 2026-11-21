import { useEffect, useRef, useState } from 'react';
import { useConnectorApps, useLinkConnection, useSyncConnections, type ConnectorApp } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Button, Dialog, LoadingCard, TextField } from '@/ui';
import styles from '../bots/bots.module.css';

/** Waits a moment after the last key before asking the server, so each search is one request. */
function useSettled(value: string, ms = 250) {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
}

/**
 * Find an app and connect it: Connect opens the app's own sign-in (Pipedream's) in a popup; when the popup closes, or
 * this window has the focus again, the server is asked what is connected now.
 */
export function AddConnectionDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [q, setQ] = useState('');
  const settled = useSettled(q.trim());
  const apps = useConnectorApps(settled, open);
  const link = useLinkConnection();
  const sync = useSyncConnections();
  const [waiting, setWaiting] = useState<{ app: ConnectorApp; url: string; blocked: boolean } | null>(null);
  const popup = useRef<Window | null>(null);

  // While the person signs in to the app: on the popup closing, or on coming back to this window, see what is connected.
  useEffect(() => {
    if (!waiting) return;
    const check = () => sync.mutate();
    const watch = setInterval(() => {
      if (popup.current?.closed) {
        popup.current = null;
        clearInterval(watch);
        check();
      }
    }, 500);
    window.addEventListener('focus', check);
    return () => {
      clearInterval(watch);
      window.removeEventListener('focus', check);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [waiting]);

  const connect = (app: ConnectorApp) =>
    link.mutate(app.slug, {
      onSuccess: ({ url }) => {
        popup.current = window.open(url, 'glyphh-connect', 'popup,width=560,height=720');
        setWaiting({ app, url, blocked: !popup.current });
      },
    });

  const close = () => {
    setWaiting(null);
    setQ('');
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={close}
      size="wide"
      title="Add a connection"
      description="Connect an app your bots may use. You sign in to the app itself; Glyphh never sees your password."
      actions={
        <Button variant={waiting ? 'primary' : 'ghost'} onClick={close}>
          {waiting ? 'Done' : 'Cancel'}
        </Button>
      }
    >
      <div className={styles.form}>
        {waiting && (
          <p className={styles.muted} role="status">
            {waiting.blocked ? (
              <>
                Your browser stopped the popup.{' '}
                <a href={waiting.url} target="_blank" rel="noreferrer">
                  Open {waiting.app.name}’s sign-in
                </a>
                , then come back here.
              </>
            ) : (
              `Sign in to ${waiting.app.name} in the window that opened, then come back here.`
            )}
            {sync.isSuccess && ' Your connections are up to date.'}
          </p>
        )}
        <TextField label="Search apps" value={q} onChange={(e) => setQ(e.target.value)} />
        {apps.isPending && <LoadingCard />}
        <ApiErrorNotice error={apps.error ?? link.error ?? sync.error} />
        {apps.data?.apps.length === 0 && <p className={styles.muted}>No app matches “{settled}”.</p>}
        {apps.data && apps.data.apps.length > 0 && (
          <ul className={styles.list} aria-label="Apps">
            {apps.data.apps.map((app) => (
              <li key={app.slug} className={styles.item}>
                {app.icon ? <img src={app.icon} alt="" className={styles.icon} /> : <span className={styles.icon} />}
                <div className={styles.grow}>
                  <div className={styles.toolName}>{app.name}</div>
                  {app.description && <div className={styles.muted}>{app.description}</div>}
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  loading={link.isPending && link.variables === app.slug}
                  onClick={() => connect(app)}
                  aria-label={`Connect ${app.name}`}
                >
                  Connect
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Dialog>
  );
}
