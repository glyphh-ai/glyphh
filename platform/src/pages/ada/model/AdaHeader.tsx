import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { useAdaReleases, type AdaModel, type AdaNotice } from '@/api/ada';
import { cx } from '@/lib/cx';
import { date } from '@/lib/format';
import { isBeta, notesPath, upgradePath } from '@/lib/releases';
import { AdaName } from '../AdaRelease';
import styles from '../ada.module.css';

const looks: Record<AdaNotice['kind'], string | undefined> = {
  upgrade: styles.noticeUpgrade,
  beta: styles.noticeQuiet,
  deprecated: styles.noticeWarn,
  retired: styles.noticeWarn,
  moved: styles.noticeInfo,
};

/** The ways on from a notice: the new version's notes, and the model's upgrade flow to it. */
function ways(model: string, notice: AdaNotice): ReactNode {
  const notes = notice.to && (
    <Link key="notes" to={notesPath(notice.to)}>
      See what changes
    </Link>
  );
  const upgrade = (label: string) => (
    <Link key="upgrade" to={upgradePath(model, notice.to)}>
      {label}
    </Link>
  );
  if (notice.kind === 'upgrade') return [notes, upgrade('Backtest and upgrade')];
  if (notice.kind === 'beta') return [upgrade('Try it in a backtest')];
  if (notice.kind === 'moved') return [notes];
  return [upgrade('Choose a version to move to')];
}

/**
 * Under a model's name: the Ada it runs (Beta beside a beta), and what the server says of it (`ada_notice`): a newer
 * stable to move to, a quieter word of a beta, a warning while its version is deprecated (with its end) or retired,
 * and word that Glyphh moved it off a retired one.
 */
export function AdaHeader({ model }: { model: AdaModel }) {
  const releases = useAdaReleases();
  const notice = model.ada_notice;
  const beta = model.ada_status === 'beta' || isBeta(releases.data, model.ada);
  return (
    <>
      <p className={styles.adaLine}>
        <span>Runs on</span> <AdaName name={model.ada} beta={beta} />{' '}
        <Link to={notesPath(model.ada)} className={styles.meta}>
          About this version
        </Link>
      </p>
      {notice && (
        <div className={cx(styles.notice, looks[notice.kind])} role={notice.kind === 'deprecated' || notice.kind === 'retired' ? 'alert' : 'status'} aria-label="Ada version">
          <span>
            {notice.message}
            {notice.ends && notice.kind === 'deprecated' && ` It ends on ${date(notice.ends)}.`}
          </span>
          <span className={styles.noticeLinks}>{ways(model.name, notice)}</span>
        </div>
      )}
    </>
  );
}
