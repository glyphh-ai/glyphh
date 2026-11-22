import { useSetPermissions, type Connection, type ConnectionTool, type Permission } from '@/api/bots';
import { permissionChanges, useAppTools } from '@/api/connections';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ToolPermissions } from '@/bots/tools/ToolPermissions';
import { EmptyState, Skeleton } from '@/ui';
import styles from './connections.module.css';

/**
 * The app's tools as claude.ai's connector shows its tool permissions, kept on the server for every bot of the org: a
 * tool switched off is one no bot uses (blocked), one on needs approval (the hand, as a tool never set does) or is
 * always allowed.
 */
export function ToolsPanel({ connection }: { connection: Connection }) {
  const tools = useAppTools(connection.id);
  const save = useSetPermissions(connection.id);
  const put = (keys: string[], to: (t: ConnectionTool) => Permission | null) => {
    const changed = permissionChanges(tools.data ?? [], keys, to);
    if (Object.keys(changed).length > 0) save.mutate(changed);
  };

  return (
    <div className={styles.sections}>
      <p className={styles.lede}>
        Choose which of {connection.app_name}’s tools your bots may use. Each is on unless you switch it off; the hand means a bot waits for your
        approval in Approvals first, the tick that it goes ahead.
      </p>
      <ApiErrorNotice error={tools.error ?? save.error} />
      {tools.isPending ? (
        <div aria-busy="true" aria-label="Loading tools" className={styles.sections}>
          {Array.from({ length: 2 }, (_, i) => (
            <Skeleton key={i} height={44} width="100%" />
          ))}
        </div>
      ) : tools.data?.length === 0 ? (
        <EmptyState icon="layers" title="No tools">
          Pipedream has no actions for {connection.app_name} yet.
        </EmptyState>
      ) : (
        <ToolPermissions
          label={`${connection.app_name} tools`}
          tools={tools.data ?? []}
          busy={save.isPending}
          isOn={(t) => t.permission !== 'deny'}
          onSwitch={(keys, on) => put(keys, (t) => (on ? (t.permission === 'deny' ? 'ask' : null) : 'deny'))}
          onApproval={(keys, ask) => put(keys, (t) => (t.permission === 'deny' ? null : ask ? 'ask' : 'allow'))}
        />
      )}
    </div>
  );
}
