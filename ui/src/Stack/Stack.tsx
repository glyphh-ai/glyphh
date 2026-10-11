import type { CSSProperties, ReactNode } from "react";
import { cx } from "../lib/cx";
import { type Space, space } from "../lib/space";
import styles from "./Stack.module.css";

export interface StackProps {
  children: ReactNode;
  gap?: Space;
  align?: "start" | "center" | "end" | "stretch";
  className?: string;
}

/** Children one above the other, a fixed step apart. */
export function Stack({ children, gap = 4, align = "stretch", className }: StackProps) {
  const style = { "--stack-gap": space(gap), "--stack-align": align } as CSSProperties;
  return <div className={cx(styles.stack, className)} style={style}>{children}</div>;
}
