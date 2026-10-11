import type { CSSProperties, ReactNode } from "react";
import { cx } from "../lib/cx";
import { type Space, space } from "../lib/space";
import styles from "./Row.module.css";

export interface RowProps {
  children: ReactNode;
  gap?: Space;
  align?: "start" | "center" | "end" | "baseline" | "stretch";
  justify?: "start" | "center" | "end" | "between";
  wrap?: boolean;
  className?: string;
}

const JUSTIFY = { start: "flex-start", center: "center", end: "flex-end", between: "space-between" } as const;

/** Children side by side, a fixed step apart. */
export function Row({ children, gap = 3, align = "center", justify = "start", wrap = false, className }: RowProps) {
  const style = { "--row-gap": space(gap), "--row-align": align, "--row-justify": JUSTIFY[justify] } as CSSProperties;
  return <div className={cx(styles.row, wrap && styles.wrap, className)} style={style}>{children}</div>;
}
