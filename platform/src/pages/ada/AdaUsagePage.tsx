import { Link } from 'react-router';
import { useAdaModels, useAdaUsage, type AdaUsage } from '@/api/ada';
import { useMe } from '@/api/queries';
import { List, Row } from '@/components/List';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { date, money, plural } from '@/lib/format';
import { SettingsTitle } from '@/pages/settings/SettingsTitle';
import { Card, EmptyState, Icon, LoadingCard, ProgressBar } from '@/ui';
import usageStyles from '@/pages/settings/UsagePage.module.css';
import { TokensSection } from '@/pages/settings/tokens/TokensSection';
import { ConnectionsMeter } from '@/pages/settings/usage/ConnectionsCard';
import { AdaErrorNotice } from './AdaErrorNotice';
import styles from './ada.module.css';

const n = (value: number) => value.toLocaleString('en-GB');

const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

/** "2026-10" as "October 2026"; anything else as it came. */
export function monthText(month: string): string {
  const [year, mon] = month.split('-').map(Number);
  const name = mon ? monthNames[mon - 1] : undefined;
  return year && name ? `${name} ${year}` : month;
}

/** The precedents the org's models hold, against the plan's cap. */
export function PrecedentsMeter({ usage }: { usage: AdaUsage }) {
  const { used, max } = usage.precedents;
  return (
    <div>
      <div className={styles.value}>
        <span className={usageStyles.used}>{n(used)}</span>
        <span className={styles.of}>{max === null ? 'precedents, no limit' : `of ${n(max)} precedents`}</span>
      </div>
      {max !== null && <ProgressBar value={used} max={max} label="Precedents" />}
    </div>
  );
}

/** The requests this month, against the plan's month (the bar stops full when a metered plan goes past it). */
export function RequestsMeter({ usage }: { usage: AdaUsage }) {
  const { used, max } = usage.requests;
  return (
    <div>
      <div className={styles.value}>
        <span className={usageStyles.used}>{n(used)}</span>
        <span className={styles.of}>{max === null ? 'requests, no limit' : `of ${n(max)} requests`}</span>
      </div>
      {max !== null && <ProgressBar value={Math.min(used, max)} max={max} label="Requests this month" />}
    </div>
  );
}

/**
 * What happens past the month, in a line: on a metered plan (Pro, Team) what is over and its price; on one that is
 * not (Free), when requests start again, and once they are used, the way to a plan with more.
 */
export function RequestsNote({ usage, centsPer10k }: { usage: AdaUsage; centsPer10k: number | null | undefined }) {
  const { used, max, over, overage } = usage.requests;
  const again = date(usage.resets_at);
  const price = centsPer10k ? `${money(centsPer10k)} per 10,000` : null;
  if (max === null) return null;
  if (overage) {
    if (over > 0) return <p className={styles.meta}>{`${n(over)} past the month, billed${price ? ` at ${price}` : ''}. The count starts again on ${again}.`}</p>;
    return <p className={styles.meta}>{`Past ${n(max)}, requests go on${price ? ` at ${price}` : ', billed'}. The count starts again on ${again}.`}</p>;
  }
  if (used >= max) {
    return (
      <p className={styles.meta}>
        {`This month’s requests are used: they start again on ${again}. `}
        <Link to="/settings/plans">Upgrade for more</Link>
      </p>
    );
  }
  return <p className={styles.meta}>{`Past ${n(max)}, requests stop until ${again}.`}</p>;
}

/** Usage, with Ada Cloud on: precedents and requests against the plan's, the month counted, and each model's precedents. */
export function AdaUsagePage() {
  const usage = useAdaUsage();
  const models = useAdaModels();
  const me = useMe();
  const centsPer10k = me.data?.plan.cloud?.overage_cents_per_10k;
  const data = usage.data;

  return (
    <>
      <SettingsTitle title="Usage">What you use, against what your plan allows.</SettingsTitle>

      <SettingsSection
        title="This month"
        description={data ? `On ${data.plan}. ${monthText(data.month)}, counted in UTC: requests start again on ${date(data.resets_at)}.` : undefined}
      >
        {usage.isPending && <LoadingCard lines={3} />}
        <AdaErrorNotice error={usage.error} />
        {data && (
          <div className={usageStyles.meters}>
            <Card>
              <div className={usageStyles.meterHead}>
                <Icon name="model" />
                Precedents
              </div>
              <PrecedentsMeter usage={data} />
              <p className={styles.meta}>{`Across ${plural(data.models, 'model')}.`}</p>
            </Card>
            <Card>
              <div className={usageStyles.meterHead}>
                <Icon name="monitor" />
                Requests this month
              </div>
              <RequestsMeter usage={data} />
              <RequestsNote usage={data} centsPer10k={centsPer10k} />
              {data.requests_per_second !== null && <p className={styles.meta}>{`Up to ${plural(data.requests_per_second, 'call')} a second.`}</p>}
            </Card>
            <ConnectionsMeter />
          </div>
        )}
      </SettingsSection>

      <TokensSection />

      <SettingsSection title="Models" description="The precedents each model holds. Every model counts towards the plan’s precedents.">
        {models.isPending && <LoadingCard />}
        <AdaErrorNotice error={models.error} />
        {models.data?.length === 0 && <EmptyState icon="model" title="No models yet" />}
        {models.data && models.data.length > 0 && (
          <List label="Precedents by model">
            {[...models.data]
              .sort((a, b) => b.precedents - a.precedents)
              .map((model) => (
                <Row
                  key={model.id}
                  title={<Link to={`/models/${encodeURIComponent(model.name)}`}>{model.name}</Link>}
                  meta={`Version ${model.version}`}
                  actions={<span className={usageStyles.calls}>{plural(model.precedents, 'precedent')}</span>}
                />
              ))}
          </List>
        )}
      </SettingsSection>
    </>
  );
}
