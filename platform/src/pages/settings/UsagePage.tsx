import { Link } from 'react-router';
import { useHosting, useMe, usePlans, useRuntimeKeys, useRuntimeNodes } from '@/api/queries';
import type { Me, RuntimeNode, RuntimeNodes } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { List, Row } from '@/components/List';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { ago, money } from '@/lib/format';
import { sizeLabel } from '@/pages/machines/sizes';
import { Card, Chip, EmptyState, Icon, LoadingCard, ProgressBar } from '@/ui';
import { hasHosting, hostingPlansText, machinesText } from './billing/plans';
import { SettingsTitle } from './SettingsTitle';
import styles from './UsagePage.module.css';

/**
 * What you use this month: precedents against the plan's per node, the runtime nodes against the plan's, hosting so
 * far, and each API key's calls. While Glyphh hosts nothing, no hosting.
 */
export function UsagePage() {
  const me = useMe();
  const hosting = useHosting();
  const keys = useRuntimeKeys();
  const nodes = useRuntimeNodes();
  const plan = me.data?.plan;

  return (
    <>
      <SettingsTitle title="Usage">What you use, against what your plan allows.</SettingsTitle>

      <SettingsSection title="This month" description={plan && `On ${plan.name}.`}>
        {(me.isPending || (me.data && hosting === undefined)) && <LoadingCard lines={3} />}
        <ApiErrorNotice error={me.error} />
        {me.data && hosting !== undefined && (
          <div className={styles.meters}>
            <Precedents me={me.data} />
            {nodes.data && <NodeCount nodes={nodes.data} />}
            {hosting && <Hosting me={me.data} />}
          </div>
        )}
      </SettingsSection>

      <SettingsSection
        title="Runtime nodes"
        description="Each node that has linked or sent a heartbeat in the last two days, hosted or self-hosted, with its precedents against the plan’s per node."
      >
        {nodes.isPending && <LoadingCard />}
        <ApiErrorNotice error={nodes.error} />
        {nodes.data && <NodeList nodes={nodes.data} perNode={me.data?.precedents.limit ?? null} />}
      </SettingsSection>

      {hosting && me.data && hasHosting(me.data.plan) && (
        <SettingsSection title="Hosted machines" description="What each machine has cost so far this month, as billed.">
          {me.data.hosting.machines.length === 0 ? (
            <EmptyState icon="chip" title="No hosted machines this month" />
          ) : (
            <List label="Hosting by machine">
              {[...me.data.hosting.machines]
                .sort((a, b) => b.cents - a.cents)
                .map((machine) => (
                  <Row
                    key={machine.id}
                    title={machine.name}
                    badges={<Chip>{sizeLabel(machine.size)}</Chip>}
                    actions={<span className={styles.calls}>{money(machine.cents)}</span>}
                  />
                ))}
            </List>
          )}
        </SettingsSection>
      )}

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
 * Precedents against the plan's per node: the fullest node's, hosted or self-hosted, as the runtimes last said. rrotor
 * holds each node to the cap its licence key carries.
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

/** The runtime nodes against the plan's. Over is shown, never stopped. */
function NodeCount({ nodes }: { nodes: RuntimeNodes }) {
  return (
    <Card>
      <div className={styles.meterHead}>
        <Icon name="chip" />
        Runtime nodes
      </div>
      <div className={styles.value}>
        <span className={styles.used}>{nodes.count.toLocaleString('en-GB')}</span>
        <span className={styles.of}>{nodes.max_nodes === null ? 'no limit' : `of ${nodes.max_nodes.toLocaleString('en-GB')}`}</span>
        {nodes.over && <Chip tone="amber">Over the plan</Chip>}
      </div>
      {nodes.max_nodes !== null && <ProgressBar value={Math.min(nodes.count, nodes.max_nodes)} max={nodes.max_nodes} label="Runtime nodes" />}
    </Card>
  );
}

const roleText: Record<NonNullable<RuntimeNode['role']>, string> = { standalone: 'Standalone', head: 'Head', follower: 'Follower' };

function nodeMeta(node: RuntimeNode): string {
  const parts = [node.node_id ? (node.runtime ?? 'A runtime') : node.mode === 'hosted' ? 'Hosted' : 'Self-hosted'];
  if (node.node_id && node.mode === 'hosted') parts.push('hosted');
  if (node.version) parts.push(node.version);
  parts.push(node.seen_at ? `last seen ${ago(node.seen_at)}` : 'not seen yet');
  return parts.join(' · ');
}

/** Each node with its runtime, role, version, precedents and when it was last seen; a note when over the plan. */
function NodeList({ nodes, perNode }: { nodes: RuntimeNodes; perNode: number | null }) {
  return (
    <>
      {nodes.over && nodes.max_nodes !== null && (
        <p className={styles.over} role="note">
          {nodes.count.toLocaleString('en-GB')} nodes on a plan with {machinesText(nodes.max_nodes).toLowerCase()}: over the plan. Nothing is stopped;
          remove a node or <Link to="/settings/plans">change plan</Link>.
        </p>
      )}
      {nodes.nodes.length === 0 ? (
        <EmptyState icon="chip" title="No runtime nodes yet">
          A runtime counts once it links to Glyphh. See <Link to="/?add=1">Add a runtime</Link>.
        </EmptyState>
      ) : (
        <List label="Runtime nodes">
          {nodes.nodes.map((node) => {
            const full = perNode !== null && node.precedents !== null && node.precedents >= perNode;
            return (
              <Row
                key={`${node.runtime_id}/${node.node_id ?? ''}`}
                title={node.node_id ?? node.runtime ?? 'Runtime'}
                badges={
                  <>
                    {node.role && <Chip>{roleText[node.role]}</Chip>}
                    {full && <Chip tone="amber">Full</Chip>}
                  </>
                }
                meta={nodeMeta(node)}
                actions={<span className={styles.calls}>{precedentsOf(node.precedents, perNode)}</span>}
              />
            );
          })}
        </List>
      )}
    </>
  );
}

function precedentsOf(precedents: number | null, perNode: number | null): string {
  if (precedents === null) return 'No precedents reported';
  const held = precedents.toLocaleString('en-GB');
  return perNode === null ? `${held} precedents` : `${held} of ${perNode.toLocaleString('en-GB')} precedents`;
}

/** Hosting this month so far: the total billed, marked up as the plan's rates are. */
function Hosting({ me }: { me: Me }) {
  const plans = usePlans();
  return (
    <Card>
      <div className={styles.meterHead}>
        <Icon name="chip" />
        Hosting
      </div>
      {hasHosting(me.plan) ? (
        <div className={styles.value}>
          <span className={styles.used}>{money(me.hosting.month_to_date_cents)}</span>
          <span className={styles.of}>this month so far</span>
        </div>
      ) : (
        <span className={styles.of}>
          Hosting is on {hostingPlansText(plans.data)}. See <Link to="/settings/billing">Billing</Link>.
        </span>
      )}
    </Card>
  );
}
