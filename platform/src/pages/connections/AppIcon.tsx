import { cx } from '@/lib/cx';
import styles from './connections.module.css';

/** An app's icon on a tile; without one, its first letter. */
export function AppIcon({ icon, name, large = false }: { icon: string | null; name: string; large?: boolean }) {
  return (
    <span className={cx(styles.appIcon, large && styles.appIconLarge)} aria-hidden="true">
      {icon ? <img src={icon} alt="" /> : name.slice(0, 1).toUpperCase()}
    </span>
  );
}
