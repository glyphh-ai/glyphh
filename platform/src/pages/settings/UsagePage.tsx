import { useMe, useModels, useRuntime, useRuntimeKeys } from '@/api/queries';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { List, Row } from '@/components/List';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { ago, hours } from '@/lib/format';
import { Card, Chip, EmptyState, Icon, LoadingCard, ProgressBar, type IconName } from '@/ui';
import { SettingsTitle } from './SettingsTitle';
import styles from './UsagePage.module.css';

/** What you use against what your plan allows: this month's runtime hours, installs, models, and each API key's calls. */
export function UsagePage() {
  const me = useMe();
  const runtime = useRuntime();
  const models = useModels();
  const keys = useRuntimeKeys();
  const plan = me.data?.plan;
  const modelLimit = plan?.mods.ada?.limits.models;

  return (
    <>
      <SettingsTitle title="Usage">What you use, against what your plan allows.</SettingsTitle>

      <SettingsSection title="This month" description={plan && `On ${plan.name}.`}>
        <ApiErrorNotice error={me.error ?? runtime.error ?? models.error} />
        <div className={styles.meters}>
          <Meter
            icon="monitor"
            label="Runtime hours"
            used={runtime.data && hours(runtime.data.seconds_used)}
            limit={runtime.data?.hours_allowed}
            unit="hours"
            failed={runtime.isError || me.isError}
          />
          <Meter icon="laptop" label="Installs" used={me.data?.used.installs} limit={plan?.limits.installs} unit="installs" failed={me.isError} />
          <Meter icon="model" label="Models" used={models.data?.length} limit={plan && (modelLimit === undefined ? null : modelLimit)} unit="models" failed={models.isError || me.isError} />
        </div>
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

type MeterProps = { icon: IconName; label: string; used: number | undefined; limit: number | null | undefined; unit: string; failed: boolean };

/** One count against its limit; no bar when the plan sets none. Loading until both are known, unless a read failed. */
function Meter({ icon, label, used, limit, unit, failed }: MeterProps) {
  const known = used !== undefined && limit !== undefined;
  return (
    <Card>
      <div className={styles.meterHead}>
        <Icon name={icon} />
        {label}
      </div>
      {known ? (
        <>
          <div className={styles.value}>
            <span className={styles.used}>{used.toLocaleString()}</span>
            <span className={styles.of}>{limit === null ? `${unit}, no limit` : `of ${limit.toLocaleString()} ${unit}`}</span>
          </div>
          {limit !== null && <ProgressBar value={used} max={limit} label={`${label} used`} />}
        </>
      ) : failed ? (
        <span className={styles.of}>Unavailable</span>
      ) : (
        <span className={styles.of} aria-busy="true">
          Loading
        </span>
      )}
    </Card>
  );
}
