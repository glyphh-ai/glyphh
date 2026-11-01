import { useLayoutEffect } from 'react';

/**
 * The form whose submit makes the runtime, as the dialog's footer shows it: its primary button, bottom right, with
 * Cancel to its left. With none (a runtime made, or nothing to make), the footer has Done alone.
 */
export type Primary = { form: string; label: string; ready: boolean; pending: boolean };

export type OnPrimary = (primary: Primary | null) => void;

/**
 * Tells the dialog this form's button while it is on screen, and takes it away when it goes. Layout effects, so the
 * footer changes in the same paint as the form, never a frame behind it.
 */
export function useFooterPrimary(onPrimary: OnPrimary, { form, label, ready, pending }: Primary) {
  useLayoutEffect(() => {
    onPrimary({ form, label, ready, pending });
  }, [onPrimary, form, label, ready, pending]);
  useLayoutEffect(() => () => onPrimary(null), [onPrimary]);
}
