import { useState } from 'react';
import { Link } from 'react-router';
import { useLicenceKeys, useMe, useRuntimeNodes } from '@/api/queries';
import type { LicenceKey } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { List, Row } from '@/components/List';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { date } from '@/lib/format';
import { Button, Card, CardEyebrow, Chip, CopyButton, CopyField, LoadingCard } from '@/ui';
import billing from '../billing/billing.module.css';
import settings from '../settings.module.css';
import { SettingsTitle } from '../SettingsTitle';
import { community, graceDays, keyEnv, keyFile, masked, stateChip, termsText, tierName } from './licence';
import { NodeCount, NodeList } from './Nodes';
import styles from './Licence.module.css';

/**
 * The org's licence key: the one its runtimes are sent now (its plan, runtime nodes and expiry), how it reaches them,
 * the nodes it is counted against, and the keys before it. Free has none: rrotor runs as Community.
 */
export function LicencePage() {
  const me = useMe();
  const licence = useLicenceKeys();
  const nodes = useRuntimeNodes();
  const free = me.data?.plan.price_cents === 0;
  const current = licence.data?.keys.find((key) => key.key === licence.data?.license_key) ?? null;
  const older = licence.data?.keys.filter((key) => key !== current) ?? [];

  return (
    <>
      <SettingsTitle title="Licence">The key rrotor runs on. It carries your plan’s limits to every node.</SettingsTitle>

      <SettingsSection title="Licence key" description="One for each paid month. It renews itself at each payment.">
        {(me.isPending || licence.isPending) && <LoadingCard lines={3} />}
        <ApiErrorNotice error={me.error ?? licence.error} />
        {me.data && licence.data && (current ? <CurrentKey licence={current} /> : <Community free={free} />)}
      </SettingsSection>

      {me.data && licence.data && !free && (
        <SettingsSection title="How it reaches rrotor" description="Nothing to do for a node that reaches Glyphh.">
          <div className={styles.how}>
            <div className={styles.way}>
              <h3 className={styles.wayTitle}>Automatic</h3>
              <p className={styles.text}>
                Each node picks up the newest key when it links to Glyphh, and again at its daily heartbeat. When your plan renews, the new key
                follows on its own.
              </p>
            </div>
            <div className={styles.way}>
              <h3 className={styles.wayTitle}>Air-gapped nodes</h3>
              <p className={styles.text}>
                Paste the key as <code className={styles.code}>{keyEnv}</code>, or save it as <code className={styles.code}>{keyFile}</code>. Paste the
                new one each month: rrotor holds a key {graceDays} days past its expiry, then runs as Community.
              </p>
            </div>
          </div>
        </SettingsSection>
      )}

      <SettingsSection
        title="Runtime nodes"
        description="Each rrotor node seen in the last two days, local or self-hosted, counted against your plan. Over the plan is shown, never stopped."
      >
        {nodes.isPending && <LoadingCard />}
        <ApiErrorNotice error={nodes.error} />
        {nodes.data && (
          <div className={styles.nodes}>
            <NodeCount nodes={nodes.data} />
            <NodeList nodes={nodes.data} perNode={me.data?.precedents.limit ?? null} />
          </div>
        )}
      </SettingsSection>

      {older.length > 0 && (
        <SettingsSection title="Older keys" description="Expired keys, and keys whose subscription ended. None is sent to rrotor.">
          <List label="Older licence keys">
            {older.map((key) => (
              <Row
                key={key.license_id}
                title={`${tierName(key.tier)} key`}
                badges={<Chip tone={stateChip[key.state].tone}>{stateChip[key.state].label}</Chip>}
                meta={olderMeta(key)}
                actions={
                  <>
                    <span className={styles.masked}>{masked(key.key)}</span>
                    <CopyButton value={key.key} label={`${tierName(key.tier)} key issued ${date(key.issued_at)}`} />
                  </>
                }
              />
            ))}
          </List>
        </SettingsSection>
      )}
    </>
  );
}

function olderMeta(key: LicenceKey): string {
  const parts = [`Issued ${date(key.issued_at)}`];
  if (key.revoked_at) parts.push(`revoked ${date(key.revoked_at)}`);
  parts.push(`${key.state === 'live' ? 'expires' : 'expired'} ${date(key.expires_at)}`);
  return parts.join(' · ');
}

/** The key the org's runtimes are sent now: masked until revealed, its terms and expiry. */
function CurrentKey({ licence }: { licence: LicenceKey }) {
  const [revealed, setRevealed] = useState(false);
  return (
    <Card aria-label="Current licence key">
      <CardEyebrow>{tierName(licence.tier)}</CardEyebrow>
      <div className={billing.titleLine}>
        <h3 className={billing.planName}>Licence key</h3>
        <Chip tone={stateChip[licence.state].tone} dot>
          {stateChip[licence.state].label}
        </Chip>
        <Chip>Expires {date(licence.expires_at)}</Chip>
      </div>
      <CopyField value={licence.key} label="licence key" shown={revealed ? undefined : masked(licence.key)}>
        <Button size="sm" variant="ghost" onClick={() => setRevealed((shown) => !shown)} aria-pressed={revealed}>
          {revealed ? 'Hide' : 'Reveal'}
        </Button>
      </CopyField>
      <div className={billing.chips}>
        {termsText(licence).map((text) => (
          <Chip key={text}>{text}</Chip>
        ))}
      </div>
      <p className={settings.note}>Issued {date(licence.issued_at)}. Keep it out of version control.</p>
    </Card>
  );
}

/** No key: on Free rrotor runs as Community; on a paid plan, until the first payment goes through. */
function Community({ free }: { free: boolean }) {
  return (
    <Card aria-label="Community">
      <CardEyebrow>{free ? 'Free' : 'No key yet'}</CardEyebrow>
      <h3 className={billing.planName}>{free ? 'Community: no key needed' : 'Running as Community'}</h3>
      <div className={billing.chips}>
        {termsText(community).map((text) => (
          <Chip key={text}>{text}</Chip>
        ))}
      </div>
      <p className={billing.description}>
        {free ? (
          <>
            rrotor with no key runs as Community, with these limits. A paid plan brings a key, sent to your nodes on its own. See{' '}
            <Link to="/settings/billing">Billing</Link>.
          </>
        ) : (
          'A key is issued once your plan’s payment goes through, and sent to your nodes on its own. Until then they run as Community.'
        )}
      </p>
    </Card>
  );
}
