import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { useConnections, useLinkConnection, useSyncConnections, type ConnectorApp } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Button, Dialog, useToast } from '@/ui';
import styles from './connections.module.css';

const EVERY_MS = 2000;

type Waiting = { app: ConnectorApp; url: string; blocked: boolean; before: number; gaveUp: boolean };

/**
 * Connecting an app: its own sign-in (Pipedream's) opens in a popup, and while the person signs in the server is
 * asked every two seconds, on the popup closing and on coming back to this window, what is connected. When a new
 * account of the app shows, the dialog closes and the app's page opens on its tools.
 */
export function useConnect({ onConnected }: { onConnected?: (app: ConnectorApp) => void } = {}) {
  const navigate = useNavigate();
  const toast = useToast();
  const connections = useConnections();
  const link = useLinkConnection();
  const sync = useSyncConnections();
  const [waiting, setWaiting] = useState<Waiting | null>(null);
  const popup = useRef<Window | null>(null);
  const closedAt = useRef(0);

  const count = (app: string, list = connections.data) => (list ?? []).filter((c) => c.app === app).length;

  useEffect(() => {
    if (!waiting || waiting.gaveUp) return;
    const check = () => {
      if (sync.isPending) return;
      sync.mutate(undefined, {
        onSuccess: ({ connections: now }) => {
          if (count(waiting.app.slug, now) > waiting.before) {
            setWaiting(null);
            toast.show(`${waiting.app.name} is connected.`);
            if (onConnected) onConnected(waiting.app);
            else navigate(`/connections/${encodeURIComponent(waiting.app.slug)}?tab=tools`);
          } else if (closedAt.current && Date.now() - closedAt.current >= EVERY_MS) {
            setWaiting((w) => w && { ...w, gaveUp: true });
          }
        },
      });
    };
    const watch = setInterval(() => {
      if (popup.current?.closed && !closedAt.current) closedAt.current = Date.now();
      check();
    }, EVERY_MS);
    window.addEventListener('focus', check);
    return () => {
      clearInterval(watch);
      window.removeEventListener('focus', check);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [waiting, sync.isPending]);

  const connect = (app: ConnectorApp) =>
    link.mutate(app.slug, {
      onSuccess: ({ url }) => {
        closedAt.current = 0;
        popup.current = window.open(url, 'glyphh-connect', 'popup,width=560,height=720');
        setWaiting({ app, url, blocked: !popup.current, before: count(app.slug), gaveUp: false });
      },
    });

  const cancel = () => {
    popup.current?.close();
    popup.current = null;
    setWaiting(null);
    sync.reset();
  };

  const dialog = (
    <Dialog
      open={waiting !== null}
      onClose={cancel}
      title={waiting ? `Connect ${waiting.app.name}` : 'Connect'}
      actions={
        waiting?.gaveUp ? (
          <>
            <Button variant="ghost" onClick={cancel}>
              Cancel
            </Button>
            <Button variant="primary" onClick={() => waiting && connect(waiting.app)} loading={link.isPending}>
              Try again
            </Button>
          </>
        ) : (
          <Button variant="ghost" onClick={cancel}>
            Cancel
          </Button>
        )
      }
    >
      <div className={styles.connecting} role="status" aria-live="polite">
        {waiting?.gaveUp ? (
          <p>{waiting.app.name} was not connected. The sign-in window closed before it finished.</p>
        ) : (
          <>
            <span className={styles.spinner} aria-hidden="true" />
            <p className={styles.connectingTitle}>Connecting {waiting?.app.name}…</p>
            {waiting?.blocked ? (
              <p className={styles.muted}>
                Your browser stopped the sign-in window.{' '}
                <a href={waiting.url} target="_blank" rel="noreferrer">
                  Open {waiting.app.name}’s sign-in
                </a>
                , then come back here.
              </p>
            ) : (
              <p className={styles.muted}>Finish signing in to {waiting?.app.name} in the window that opened. This closes by itself once it is connected.</p>
            )}
          </>
        )}
        <ApiErrorNotice error={sync.error} />
      </div>
    </Dialog>
  );

  return { connect, connecting: link.isPending ? link.variables : waiting?.app.slug, error: link.error, dialog };
}
