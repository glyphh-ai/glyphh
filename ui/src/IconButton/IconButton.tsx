import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cx } from "../lib/cx";
import styles from "./IconButton.module.css";

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children" | "aria-label"> {
  /** What the button does, said out loud: an icon alone says nothing to a screen reader. */
  label: string;
  icon: ReactNode;
  variant?: "ghost" | "secondary";
}

/** A button that is only an icon, with its label for screen readers and as its tooltip. */
export function IconButton({ label, icon, variant = "ghost", className, type = "button", ...rest }: IconButtonProps) {
  return (
    <button {...rest} type={type} aria-label={label} title={label} className={cx(styles.icon, className)}
      data-variant={variant}>
      {icon}
    </button>
  );
}
