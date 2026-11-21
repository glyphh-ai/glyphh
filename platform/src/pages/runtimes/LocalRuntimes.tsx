import { useRuntimeNodes } from '@/api/queries';
import type { RuntimeNode } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { List, Row } from '@/components/List';
import { ago } from '@/lib/format';
import { Card, Chip, LoadingCard } from '@/ui';
import styles from './RuntimesPage.module.css';

const ONLINE_WINDOW_MS = 5 * 60 * 1000;

function meta(node: RuntimeNode): string {
  const parts = [node.version ? `rrotor ${node.version}` : 'rrotor'];
  parts.push(node.seen_at ? `last seen ${ago(node.seen_at)}` : 'not seen yet');
  if (node.precedents !== null) parts.push(`${node.precedents.toLocaleString('en-GB')} precedents`);
  return parts.join(' · ');
}

/**
 * The rrotors linked from the org's own machines (local mode: one per install, from `GET /v1/license/nodes`), named
 * after the machine they were started from. One links from Claude Code with `/glyphh link`.
 */
export function LocalRuntimes({ now = () => Date.now() }: { now?: () => number }) {
  const nodes = useRuntimeNodes();
  const local = nodes.data?.nodes.filter((node) => node.mode === 'local') ?? [];
  return (
    <Card>
      <h2 className={styles.cardTitle}>On your machines</h2>
      <p className={styles.meta}>The rrotors linked from Claude Code on your organisation’s computers, each named after its machine.</p>
      {nodes.isPending && <LoadingCard />}
      <ApiErrorNotice error={nodes.error} />
      {nodes.data && local.length === 0 && (
        <p className={styles.text}>
          None linked yet. In Claude Code, with the glyphh plugin signed in, run <code>/glyphh link</code> and this machine’s rrotor shows here.
        </p>
      )}
      {local.length > 0 && (
        <List label="Local runtimes">
          {local.map((node) => {
            const online = node.seen_at !== null && now() - new Date(node.seen_at).getTime() < ONLINE_WINDOW_MS;
            return (
              <Row
                key={node.runtime_id}
                title={node.runtime ?? 'A local rrotor'}
                badges={<Chip tone={online ? 'green' : 'neutral'}>{online ? 'Online' : 'Away'}</Chip>}
                meta={meta(node)}
              />
            );
          })}
        </List>
      )}
    </Card>
  );
}
