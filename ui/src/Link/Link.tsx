import type { AnchorHTMLAttributes, ReactNode } from "react";
import { cx } from "../lib/cx";
import styles from "./Link.module.css";

export interface LinkProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  href: string;
  children: ReactNode;
  /** Opens in a new tab, without handing the new page a handle on this one. */
  external?: boolean;
}

/** A link. External ones open in a new tab and say so to screen readers. */
export function Link({ href, children, external = false, className, ...rest }: LinkProps) {
  const outside = external ? { target: "_blank", rel: "noopener noreferrer" } : {};
  return (
    <a {...rest} {...outside} href={href} className={cx(styles.link, className)}>
      {children}
      {external && <span className={styles.hidden}> (opens in a new tab)</span>}
    </a>
  );
}
