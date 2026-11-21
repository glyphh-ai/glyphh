import { Link } from 'react-router';
import type { Billing, Plan } from '@/api/types';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { money } from '@/lib/format';
import { Card, Icon, type IconName } from '@/ui';
import tokens from '../tokens/tokens.module.css';
import styles from './billing.module.css';

const n = (value: number) => value.toLocaleString('en-GB');

type Line = { icon: IconName; name: string; text: string };

/** What happens past each of the plan's limits, as the plan and the server's billing say; nothing made up. */
export function overageLines(plan: Plan, billing: Billing, ada: boolean): Line[] {
  const lines: Line[] = [];
  if (billing.tokens) {
    const max = billing.tokens.max;
    lines.push({
      icon: 'layers',
      name: 'Tokens',
      text:
        max === null
          ? 'By contract.'
          : `Your plan has ${n(max)} tokens a month for bots and hosted models. Past them, each request is charged to your balance at the model’s rates; with the balance empty, they stop until you add funds.`,
    });
  }
  const cloud = plan.cloud;
  if (ada && cloud && cloud.requests_per_month !== null) {
    const price = cloud.overage_cents_per_10k ? `${money(cloud.overage_cents_per_10k)} per 10,000` : 'metered';
    lines.push({
      icon: 'monitor',
      name: 'Ada requests',
      text: cloud.overage
        ? `Past ${n(cloud.requests_per_month)} a month, requests go on at ${price}, on your next invoice.`
        : `Past ${n(cloud.requests_per_month)} a month, requests stop until the month turns.`,
    });
  }
  const connections = billing.connections;
  if (connections && connections.included !== null) {
    lines.push({
      icon: 'external',
      name: 'Connections',
      text:
        connections.cents_a_month === null
          ? `${n(connections.included)} included. Past them, connections are not charged yet.`
          : `${n(connections.included)} included, then ${money(connections.cents_a_month)} a connection a month.`,
    });
  }
  return lines;
}

/** Billing's overages: what each limit of the plan does past it, and the way to a plan with more. */
export function OveragesSection({ plan, billing, ada }: { plan: Plan; billing: Billing; ada: boolean }) {
  const lines = overageLines(plan, billing, ada);
  if (lines.length === 0) return null;
  return (
    <SettingsSection title="Overages" description="What happens past your plan’s limits.">
      <Card aria-label="Overages">
        <ul className={styles.overages}>
          {lines.map((line) => (
            <li key={line.name} className={styles.overage}>
              <span className={styles.overageIcon}>
                <Icon name={line.icon} size={16} />
              </span>
              <div>
                <span className={styles.overageName}>{line.name}</span>
                <p className={tokens.meta}>{line.text}</p>
              </div>
            </li>
          ))}
        </ul>
        <p className={tokens.meta}>
          Need more each month? <Link to="/settings/plans">Change plan</Link>
        </p>
      </Card>
    </SettingsSection>
  );
}
