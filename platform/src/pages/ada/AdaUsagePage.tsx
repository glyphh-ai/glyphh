import { Link } from 'react-router';
import { useAdaModels, useAdaUsage, type AdaUsage } from '@/api/ada';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { List, Row } from '@/components/List';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { plural } from '@/lib/format';
import { SettingsTitle } from '@/pages/settings/SettingsTitle';
import { Card, EmptyState, Icon, LoadingCard, ProgressBar } from '@/ui';
import usageStyles from '@/pages/settings/UsagePage.module.css';
import styles from './ada.module.css';

const n = (value: number) => value.toLocaleString('en-GB');

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

/** Requests this month against the plan's; not counted until the server counts them. */
function Requests({ usage }: { usage: AdaUsage }) {
  const requests = usage.requests;
  return (
    <Card>
      <div className={usageStyles.meterHead}>
        <Icon name="monitor" />
        Requests this month
      </div>
      {requests === null ? (
        <p className={styles.meta}>Not counted yet.</p>
      ) : (
        <>
          <div className={usageStyles.value}>
            <span className={usageStyles.used}>{n(requests.used)}</span>
            <span className={usageStyles.of}>{requests.max === null ? 'no limit' : `of ${n(requests.max)}`}</span>
          </div>
          {requests.max !== null && <ProgressBar value={requests.used} max={requests.max} label="Requests this month" />}
        </>
      )}
    </Card>
  );
}

/** Usage, with Ada Cloud on: precedents and requests against the plan's caps, and each model's precedents. */
export function AdaUsagePage() {
  const usage = useAdaUsage();
  const models = useAdaModels();

  return (
    <>
      <SettingsTitle title="Usage">What you use, against what your plan allows.</SettingsTitle>

      <SettingsSection title="This month" description={usage.data?.plan ? `On ${usage.data.plan}.` : undefined}>
        {usage.isPending && <LoadingCard lines={3} />}
        <ApiErrorNotice error={usage.error} />
        {usage.data && (
          <div className={usageStyles.meters}>
            <Card>
              <div className={usageStyles.meterHead}>
                <Icon name="model" />
                Precedents
              </div>
              <PrecedentsMeter usage={usage.data} />
            </Card>
            <Requests usage={usage.data} />
          </div>
        )}
      </SettingsSection>

      <SettingsSection title="Models" description="The precedents each model holds. Every model counts towards the plan’s precedents.">
        {models.isPending && <LoadingCard />}
        <ApiErrorNotice error={models.error} />
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
