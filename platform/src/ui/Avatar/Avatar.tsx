import styles from './Avatar.module.css';

/** A round initial for a person, from their name or email. */
export function Avatar({ name }: { name: string }) {
  const initial = name.trim().charAt(0).toUpperCase() || '?';
  return (
    <span className={styles.avatar} aria-hidden="true">
      {initial}
    </span>
  );
}
