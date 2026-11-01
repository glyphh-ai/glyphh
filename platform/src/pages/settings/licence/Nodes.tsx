import { Link } from 'react-router';
import type { RuntimeNode, RuntimeNodes } from '@/api/types';
import { List, Row } from '@/components/List';
import { ago } from '@/lib/format';
import { Card, Chip, EmptyState, Icon, ProgressBar } from '@/ui';
import { machinesText } from '../billing/plans';
import styles from '../UsagePage.module.css';

/** The runtime nodes against the plan's, from `GET /v1/license/nodes`. Over is shown, never stopped. */
export function NodeCount({ nodes }: { nodes: RuntimeNodes }) {
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
  const kind = node.mode === 'local' ? 'Local' : 'Self-hosted';
  const parts = [node.node_id ? (node.runtime ?? 'A runtime') : kind];
  if (node.node_id && node.mode === 'local') parts.push('local');
  if (node.version) parts.push(node.version);
  parts.push(node.seen_at ? `last seen ${ago(node.seen_at)}` : 'not seen yet');
  return parts.join(' · ');
}

function precedentsOf(precedents: number | null, perNode: number | null): string {
  if (precedents === null) return 'No precedents reported';
  const held = precedents.toLocaleString('en-GB');
  return perNode === null ? `${held} precedents` : `${held} of ${perNode.toLocaleString('en-GB')} precedents`;
}

/**
 * Each node, local or self-hosted, with its runtime, role, version, precedents and when it was last seen; a note when
 * over the plan. `perNode` is the plan's precedents per node (null: unlimited).
 */
export function NodeList({ nodes, perNode }: { nodes: RuntimeNodes; perNode: number | null }) {
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
          A rrotor counts once it links to Glyphh. See <Link to="/runtimes">Runtimes</Link> to install one.
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
