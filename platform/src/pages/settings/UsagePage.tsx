import { Link } from 'react-router';
import { useMe, usePlans, useRuntimeKeys } from '@/api/queries';
import type { Me } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { List, Row } from '@/components/List';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { ago, money } from '@/lib/format';
import { sizeLabel } from '@/pages/machines/sizes';
import { Card, Chip, EmptyState, Icon, LoadingCard, ProgressBar } from '@/ui';
import { hasHosting, hostingPlansText } from './billing/plans';
import { SettingsTitle } from './SettingsTitle';
import styles from './UsagePage.module.css';

/** What you use this month: precedents against the plan's managed bucket, hosting so far, and each API key's calls. */
export function UsagePage() {
  const me = useMe();
  const keys = useRuntimeKeys();
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
            <Hosting me={me.data} />
          </div>
        )}
      </SettingsSection>

      {me.data && hasHosting(me.data.plan) && (
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

/** Precedents on the org's hosted runtimes against the plan's bucket. Those on your own runtimes never count. */
function Precedents({ me }: { me: Me }) {
  const { used, limit } = me.precedents;
  return (
    <Card>
      <div className={styles.meterHead}>
        <Icon name="model" />
        Precedents
      </div>
      {hasHosting(me.plan) ? (
        <>
          <div className={styles.value}>
            <span className={styles.used}>{used.toLocaleString('en-GB')}</span>
            <span className={styles.of}>{limit === null ? 'on hosted machines, no limit' : `of ${limit.toLocaleString('en-GB')} on hosted machines`}</span>
          </div>
          {limit !== null && <ProgressBar value={used} max={limit} label="Precedents used" />}
        </>
      ) : (
        <span className={styles.of}>No limit on your own runtimes.</span>
      )}
    </Card>
  );
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
