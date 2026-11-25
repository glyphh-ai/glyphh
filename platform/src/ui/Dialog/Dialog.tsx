import { useEffect, useId, useRef, type ReactNode } from 'react';
import { cx } from '@/lib/cx';
import styles from './Dialog.module.css';

type DialogProps = {
  open: boolean;
  /** `wide` fits code blocks and a form beside each other; the default suits a question or a short form. */
  size?: 'default' | 'wide';
  onClose: () => void;
  title: string;
  description?: ReactNode;
  children?: ReactNode;
  /** The buttons along the bottom; the main action goes last. */
  actions: ReactNode;
};

/** A modal on the native <dialog>, so focus, Escape and the backdrop behave as the browser does. */
export function Dialog({ open, size = 'default', onClose, title, description, children, actions }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    // The <dialog> itself always renders; only its body comes and goes.
    const dialog = ref.current!;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className={cx(styles.dialog, size === 'wide' && styles.wide)}
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      onClose={onClose}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
    >
      {open && (
        <div className={styles.body}>
          <h2 id={titleId} className={styles.title}>
            {title}
          </h2>
          {description && (
            <div id={descriptionId} className={styles.description}>
              {description}
            </div>
          )}
          {children}
          <div className={styles.actions}>{actions}</div>
        </div>
      )}
    </dialog>
  );
}
