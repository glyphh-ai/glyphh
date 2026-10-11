import type { ReactNode } from "react";
import { Button, type ButtonVariant } from "../Button/Button";
import { useFormStatus } from "../Form/status";

export interface SubmitButtonProps {
  children: ReactNode;
  variant?: ButtonVariant;
  block?: boolean;
}

/** The form's own submit: busy and unclickable while the form is sending. */
export function SubmitButton({ children, variant = "primary", block }: SubmitButtonProps) {
  const { submitting } = useFormStatus();
  return <Button type="submit" variant={variant} block={block} busy={submitting}>{children}</Button>;
}
