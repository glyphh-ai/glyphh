import { useMe, useRuntimeKeys, useRuntimeNodes } from '@/api/queries';
import type { Me } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { List, Row } from '@/components/List';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { ago } from '@/lib/format';
import { Card, Chip, EmptyState, Icon, LoadingCard, ProgressBar } from '@/ui';
import { NodeCount, NodeList } from './licence/Nodes';
import { SettingsTitle } from './SettingsTitle';
import styles from './UsagePage.module.css';

/** What you use: precedents against the plan's per node, the runtime nodes against the plan's, each API key's calls. */
export function UsagePage() {
  const me = useMe();
  const keys = useRuntimeKeys();
  const nodes = useRuntimeNodes();
  const plan = me.data?.plan;

  return (
    <>
      <SettingsTitle title="Usage">What you use, against what your plan allows.</SettingsTitle>

      <SettingsSection title="This month" description={plan && `On ${plan.name}.`}>
        {me.isPending && <LoadingCard lines={3} />}
        <ApiErrorNotice error={me.error} />
        {me.data && (
          <div className={styles.meters}>
            <Precedents me={me.data} />
            {nodes.data && <NodeCount nodes={nodes.data} />}
          </div>
        )}
      </SettingsSection>

      <SettingsSection
        title="Runtime nodes"
        description="Each node that has linked or sent a heartbeat in the last two days, local or self-hosted, with its precedents against the plan’s per node."
      >
        {nodes.isPending && <LoadingCard />}
        <ApiErrorNotice error={nodes.error} />
        {nodes.data && <NodeList nodes={nodes.data} perNode={me.data?.precedents.limit ?? null} />}
      </SettingsSection>

      <SettingsSection title="API keys" description="Calls each key let into your runtime, as the runtime reports them.">
        {keys.isPending && <LoadingCard />}
        <ApiErrorNotice error={keys.error} />
        {keys.data?.length === 0 && <EmptyState icon="key" title="No API keys yet" />}
        {keys.data && keys.data.length > 0 && (
          <List label="API key calls">
            {[...keys.data]
              .sort((a, b) => b.calls - a.calls)
              .map((key) => (
                <Row
                  key={key.id}
                  title={key.name}
                  badges={key.revoked_at && <Chip>Revoked</Chip>}
                  meta={key.last_used_at ? `Last used ${ago(key.last_used_at)}` : 'Never used'}
                  actions={<span className={styles.calls}>{`${key.calls.toLocaleString()} ${key.calls === 1 ? 'call' : 'calls'}`}</span>}
                />
              ))}
          </List>
        )}
      </SettingsSection>
    </>
  );
}

/**
 * Precedents against the plan's per node: the fullest node's, as the runtimes last said. rrotor holds each node to the
 * cap its licence key carries.
 */
function Precedents({ me }: { me: Me }) {
  const { used, limit } = me.precedents;
  return (
    <Card>
      <div className={styles.meterHead}>
        <Icon name="model" />
        Precedents
      </div>
      <div className={styles.value}>
        <span className={styles.used}>{used.toLocaleString('en-GB')}</span>
        <span className={styles.of}>{limit === null ? 'on the fullest node, no limit' : `of ${limit.toLocaleString('en-GB')} on the fullest node`}</span>
      </div>
      {limit !== null && <ProgressBar value={used} max={limit} label="Precedents on the fullest node" />}
    </Card>
  );
}
