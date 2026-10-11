import type { ReactNode } from "react";
import { cx } from "../lib/cx";
import styles from "./Text.module.css";

export interface TextProps {
  children: ReactNode;
  as?: "p" | "span" | "div";
  size?: "xs" | "sm" | "md" | "lg";
  tone?: "default" | "muted" | "danger" | "ok";
  weight?: "regular" | "medium" | "bold";
  className?: string;
}

/** Body text, in one of the scale's sizes and tones. */
export function Text({ children, as: Tag = "p", size = "md", tone = "default", weight = "regular", className }: TextProps) {
  return (
    <Tag className={cx(styles.text, className)} data-size={size} data-tone={tone} data-weight={weight}>
      {children}
    </Tag>
  );
}
