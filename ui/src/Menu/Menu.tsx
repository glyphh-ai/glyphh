import { type KeyboardEvent, type ReactNode, useEffect, useId, useRef } from "react";
import { useDisclosure } from "../hooks/useDisclosure";
import styles from "./Menu.module.css";

export interface MenuItem {
  key: string;
  label: string;
  onSelect: () => void;
  danger?: boolean;
}

export interface MenuProps {
  /** The button that opens it: its words or an icon with this as its label. */
  label: string;
  trigger: ReactNode;
  items: MenuItem[];
}

/** A short list of actions behind a button. Arrows move, Escape closes and returns focus, a click outside closes. */
export function Menu({ label, trigger, items }: MenuProps) {
  const { open, toggle, hide } = useDisclosure();
  const id = useId();
  const button = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    (list.current?.querySelector("[role=menuitem]") as HTMLElement | null)?.focus();
    const outside = (e: MouseEvent) => { if (!list.current?.contains(e.target as Node) && e.target !== button.current) hide(); };
    document.addEventListener("mousedown", outside);
    return () => document.removeEventListener("mousedown", outside);
  }, [open, hide]);
  const onKeyDown = (e: KeyboardEvent) => {
    const all = Array.from((list.current as HTMLDivElement).querySelectorAll<HTMLElement>("[role=menuitem]"));
    const at = all.indexOf(document.activeElement as HTMLElement);
    if (e.key === "Escape") { hide(); button.current?.focus(); }
    if (e.key === "ArrowDown") all[(at + 1) % all.length]?.focus();
    if (e.key === "ArrowUp") all[(at - 1 + all.length) % all.length]?.focus();
  };
  return (
    <div className={styles.menu}>
      <button ref={button} type="button" className={styles.trigger} aria-label={label} aria-haspopup="menu"
        aria-expanded={open} aria-controls={id} onClick={toggle}>{trigger}</button>
      {open && (
        <div ref={list} id={id} role="menu" aria-label={label} className={styles.list} onKeyDown={onKeyDown}>
          {items.map((item) => (
            <button key={item.key} type="button" role="menuitem" tabIndex={-1} className={styles.item}
              data-danger={item.danger || undefined} onClick={() => { hide(); item.onSelect(); }}>{item.label}</button>
          ))}
        </div>
      )}
    </div>
  );
}
