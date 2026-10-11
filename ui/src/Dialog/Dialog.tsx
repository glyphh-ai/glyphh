import { type ReactNode, useEffect, useId, useRef } from "react";
import { Heading } from "../Heading/Heading";
import styles from "./Dialog.module.css";

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  children?: ReactNode;
  /** The buttons at the bottom: the main action last. */
  actions?: ReactNode;
}

/** A modal dialog, the browser's own: focus stays inside it, Escape closes it. */
export function Dialog({ open, onClose, title, description, children, actions }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current as HTMLDialogElement;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog ref={ref} className={styles.dialog} aria-labelledby={titleId} onClose={onClose}>
      <div className={styles.inner}>
        <div id={titleId}><Heading level={2}>{title}</Heading></div>
        {description && <p className={styles.description}>{description}</p>}
        {children}
        {actions && <div className={styles.actions}>{actions}</div>}
      </div>
    </dialog>
  );
}
