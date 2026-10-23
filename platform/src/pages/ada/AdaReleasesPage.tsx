import { useEffect } from 'react';
import { Link, useLocation } from 'react-router';
import { useAdaModels, useAdaReleases, type AdaModelRow, type AdaRelease, type AdaReleases } from '@/api/ada';
import { List, Row } from '@/components/List';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { date, plural } from '@/lib/format';
import { releaseOf, upgradePath } from '@/lib/releases';
import { Card, Chip, LoadingCard } from '@/ui';
import { AdaErrorNotice } from './AdaErrorNotice';
import { AdaStatusChip, ReleaseNotes } from './AdaRelease';
import styles from './ada.module.css';

/** Whether it answers as the version before it, in words. */
function changesText(release: AdaRelease, before: AdaRelease | undefined): string {
  if (!before) return 'The first version';
  return release.changes_answers ? `Changes answers from ${before.name}` : `Answers as ${before.name} does`;
}

/** What its status means for the models on it. */
function statusNote(release: AdaRelease): string | null {
  if (release.status === 'beta') return 'A beta is never the default: choose it by name for a new model, a backtest or an upgrade.';
  if (release.status === 'deprecated') {
    const when = release.ends ? `on ${date(release.ends)}` : 'when it ends';
    return `Its models still answer, but it can’t be chosen for a new model or an upgrade. ${when[0]!.toUpperCase()}${when.slice(1)}, Glyphh moves any model still on it to the latest stable.`;
  }
  if (release.status === 'retired') return 'Retired: Glyphh moved the models on it to the latest stable.';
  return null;
}

function ReleaseCard({ release, before, releases, models }: { release: AdaRelease; before?: AdaRelease; releases: AdaReleases; models: AdaModelRow[] | undefined }) {
  const on = models?.filter((m) => releaseOf(releases, m.ada)?.name === release.name) ?? [];
  const note = statusNote(release);
  return (
    <Card id={release.name} aria-labelledby={`${release.name}-title`} className={styles.release}>
      <div className={styles.leverHead}>
        <div className={styles.chips}>
          <h2 id={`${release.name}-title`} className={`${styles.cardTitle} ${styles.mono}`}>
            {release.name}
          </h2>
          <AdaStatusChip release={release} />
          {release.name === releases.latest_stable && <Chip tone="blue">Default for new models</Chip>}
        </div>
        <span className={styles.meta}>Released {date(release.released)}</span>
      </div>
      <p className={styles.summary}>{release.summary}</p>
      <p className={styles.meta}>
        {changesText(release, before)}
        {release.changes_answers && before ? ': backtest a model before you move it.' : '.'}
      </p>
      {note && <p className={styles.about}>{note}</p>}
      <ReleaseNotes notes={release.notes} />
      <h3 className={styles.label}>{release.models === 0 ? 'None of your models run it' : `${release.models.toLocaleString('en-GB')} of your models ${release.models === 1 ? 'runs' : 'run'} it`}</h3>
      {on.length > 0 && (
        <List label={`Models on ${release.name}`}>
          {on.map((model) => (
            <Row
              key={model.id}
              title={
                <Link to={`/models/${encodeURIComponent(model.name)}`} className={styles.link}>
                  {model.name}
                </Link>
              }
              meta={`Version ${model.version} · ${plural(model.precedents, 'precedent')}`}
              actions={
                release.status !== 'retired' && (
                  <Link to={upgradePath(model.name)} className={styles.link}>
                    Backtest and upgrade
                  </Link>
                )
              }
            />
          ))}
        </List>
      )}
      <p className={styles.details}>
        Kernel {release.kernel}
        {release.aliases.length > 0 && ` · also named ${release.aliases.join(', ')}`}
        {release.deprecated && ` · deprecated ${date(release.deprecated)}`}
        {release.ends && ` · ends ${date(release.ends)}`}
      </p>
    </Card>
  );
}

/**
 * Ada, the versions of it: each one's status, when it was released, whether it changes answers from the one before,
 * its release notes, and the org's models on it with the way to backtest and upgrade each.
 */
export function AdaReleasesPage() {
  const releases = useAdaReleases();
  const models = useAdaModels();
  const { hash } = useLocation();

  // A link to one version's notes (`/ada#ada-1-1`) lands on it once the list is read.
  useEffect(() => {
    if (releases.data && hash) document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView?.({ block: 'start' });
  }, [releases.data, hash]);

  return (
    <>
      <PageHeader
        title="Ada"
        description="The versions of Ada your models answer with. A model keeps the version it was made with until you upgrade it, with a backtest first."
      />
      {releases.isPending && <LoadingCard />}
      <AdaErrorNotice error={releases.error ?? models.error} />
      {releases.data && (
        <div className={styles.stack}>
          {releases.data.versions.map((release, i) => (
            <ReleaseCard key={release.name} release={release} before={releases.data.versions[i + 1]} releases={releases.data} models={models.data} />
          ))}
        </div>
      )}
    </>
  );
}
