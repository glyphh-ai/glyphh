import type { ReactNode } from 'react';
import { Button, Dialog } from '@/ui';
import { ApiErrorNotice } from './ApiErrorNotice';

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  description: ReactNode;
  confirmLabel: string;
  pending: boolean;
  error: unknown;
  onConfirm: () => void;
  onClose: () => void;
};

/** Asks before an action that cannot be taken back, and shows the server's refusal if there is one. */
export function ConfirmDialog({ open, title, description, confirmLabel, pending, error, onConfirm, onClose }: ConfirmDialogProps) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title}
      description={description}
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="danger" loading={pending} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <ApiErrorNotice error={error} />
    </Dialog>
  );
}
