import type { ReactNode } from "react";
import { cx } from "../lib/cx";
import styles from "./Heading.module.css";

export interface HeadingProps {
  level: 1 | 2 | 3 | 4;
  children: ReactNode;
  className?: string;
}

/** A heading at its level: h1 to h4, each with its own size. */
export function Heading({ level, children, className }: HeadingProps) {
  const Tag = `h${level}` as const;
  return <Tag className={cx(styles.heading, styles[`h${level}`], className)}>{children}</Tag>;
}
