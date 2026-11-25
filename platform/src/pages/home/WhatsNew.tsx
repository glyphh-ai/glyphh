import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { useAdaReleases } from '@/api/ada';
import { date } from '@/lib/format';
import { notesPath } from '@/lib/releases';
import { AdaStatusChip } from '@/pages/ada/AdaRelease';
import { Card, Skeleton } from '@/ui';
import styles from './home.module.css';

const SHOWN = 3;

type Item = { key: string; name: ReactNode; to: string; meta?: ReactNode; summary: string };

/** A card of a few new things, each a link with a line about it; a quiet line when there are none. */
function NewsCard({ title, more, items, pending, none }: { title: string; more: { to: string; label: string }; items: Item[] | undefined; pending: boolean; none: string }) {
  return (
    <Card aria-label={title}>
      <div className={styles.news}>
        <div className={styles.wideHead}>
          <h3 className={styles.label}>{title}</h3>
          <Link to={more.to} className={styles.link}>
            {more.label}
          </Link>
        </div>
        {pending && <Skeleton height={48} />}
        {!pending && (items?.length ?? 0) === 0 && <p className={styles.meta}>{none}</p>}
        {items && items.length > 0 && (
          <ul className={styles.items}>
            {items.map((item) => (
              <li key={item.key} className={styles.item}>
                <div className={styles.itemHead}>
                  <Link to={item.to} className={styles.itemName}>
                    {item.name}
                  </Link>
                  {item.meta}
                </div>
                {item.summary && <p className={styles.summary}>{item.summary}</p>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

/** Ada's newest versions, from Settings › Releases. */
function AdaNews() {
  const releases = useAdaReleases();
  const items = releases.data?.versions
    .filter((r) => r.status !== 'retired')
    .sort((a, b) => b.released.localeCompare(a.released))
    .slice(0, SHOWN)
    .map<Item>((r) => ({
      key: r.name,
      name: <span className={styles.mono}>{r.name}</span>,
      to: notesPath(r.name),
      meta: (
        <>
          <AdaStatusChip release={r} />
          <span className={styles.date}>{date(r.released)}</span>
        </>
      ),
      summary: r.summary,
    }));
  return <NewsCard title="New in Ada" more={{ to: '/settings/releases', label: 'All releases' }} items={items} pending={releases.isPending} none="No releases to show." />;
}

/** What is new at Glyphh: Ada's releases. */
export function WhatsNew() {
  return (
    <section aria-labelledby="whats-new">
      <h2 id="whats-new" className={styles.rowTitle}>
        What’s new
      </h2>
      <div className={styles.row}>
        <AdaNews />
      </div>
    </section>
  );
}
