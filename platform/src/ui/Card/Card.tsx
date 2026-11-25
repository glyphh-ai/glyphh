import type { HTMLAttributes, ReactNode } from 'react';
import { cx } from '@/lib/cx';
import styles from './Card.module.css';

type CardProps = HTMLAttributes<HTMLElement> & {
  as?: 'section' | 'div' | 'li' | 'article';
  padding?: 'md' | 'lg';
  children: ReactNode;
};

export function Card({ as: Tag = 'section', padding = 'md', className, children, ...rest }: CardProps) {
  return (
    <Tag className={cx(styles.card, styles[padding], className)} {...rest}>
      {children}
    </Tag>
  );
}

/** The small grey line above a card's title, such as a price. */
export function CardEyebrow({ children }: { children: ReactNode }) {
  return <span className={styles.eyebrow}>{children}</span>;
}
