import { forwardRef, type AnchorHTMLAttributes, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { cx } from '@/lib/cx';
import { Icon, type IconName } from '../Icon/Icon';
import styles from './Button.module.css';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: 'sm' | 'md';
  icon?: IconName;
  iconEnd?: IconName;
  loading?: boolean;
  children?: ReactNode;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'secondary', size = 'md', icon, iconEnd, loading = false, disabled, className, children, type = 'button', ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cx(styles.button, styles[variant], styles[size], className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {icon && <Icon name={icon} size={size === 'sm' ? 14 : 16} />}
      {children}
      {iconEnd && <Icon name={iconEnd} size={14} />}
    </button>
  );
});

type ButtonLinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & {
  variant?: ButtonVariant;
  size?: 'sm' | 'md';
  children?: ReactNode;
};

/** A link that looks like a button, for steps that must be a full page load (a sign-in answer, Stripe). */
export function ButtonLink({ variant = 'secondary', size = 'md', className, children, ...rest }: ButtonLinkProps) {
  return (
    <a className={cx(styles.button, styles[variant], styles[size], className)} {...rest}>
      {children}
    </a>
  );
}
