import { Fragment } from 'react';
import { Link } from 'react-router';
import { Icon } from '@/ui';
import styles from './TopBar.module.css';

export type Crumb = { label: string; to?: string };

export function TopBar({ crumbs, onToggleSidebar }: { crumbs: Crumb[]; onToggleSidebar: () => void }) {
  return (
    <header className={styles.bar}>
      <button type="button" className={styles.toggle} onClick={onToggleSidebar} aria-label="Menu">
        <Icon name="sidebar" size={18} />
      </button>
      <nav aria-label="Breadcrumb">
        <ol className={styles.crumbs}>
          {crumbs.map((crumb, index) => {
            const last = index === crumbs.length - 1;
            return (
              <Fragment key={crumb.label}>
                {index > 0 && (
                  <li aria-hidden="true" className={styles.separator}>
                    <Icon name="chevronRight" size={14} />
                  </li>
                )}
                <li className={last ? styles.current : undefined} aria-current={last ? 'page' : undefined}>
                  {crumb.to && !last ? <Link to={crumb.to}>{crumb.label}</Link> : crumb.label}
                </li>
              </Fragment>
            );
          })}
        </ol>
      </nav>
    </header>
  );
}
