import type { ButtonHTMLAttributes, ReactNode, Ref } from "react";
import { cx } from "../lib/cx";
import { Spinner } from "../Spinner/Spinner";
import styles from "./Button.module.css";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  children: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Working on it: shows a spinner and takes no more clicks, so nothing is sent twice. */
  busy?: boolean;
  icon?: ReactNode;
  block?: boolean;
  ref?: Ref<HTMLButtonElement>;
}

/** The one button. A plain `button` unless told otherwise, so it never submits a form by accident. */
export function Button(props: ButtonProps) {
  const { children, variant = "secondary", size = "md", busy = false, icon, block = false, className, disabled,
    type = "button", ...rest } = props;
  return (
    <button {...rest} type={type} className={cx(styles.button, block && styles.block, className)}
      data-variant={variant} data-size={size} disabled={disabled || busy} aria-busy={busy || undefined}>
      {busy ? <Spinner size="sm" label="Working" /> : icon}
      <span>{children}</span>
    </button>
  );
}
