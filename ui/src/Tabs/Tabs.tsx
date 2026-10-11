import { type KeyboardEvent, type ReactNode, useId, useRef } from "react";
import styles from "./Tabs.module.css";

export interface Tab {
  key: string;
  label: string;
  content: ReactNode;
}

export interface TabsProps {
  label: string;
  tabs: Tab[];
  value: string;
  onChange: (key: string) => void;
}

const MOVES: Record<string, (i: number, n: number) => number> = {
  ArrowRight: (i, n) => (i + 1) % n, ArrowLeft: (i, n) => (i - 1 + n) % n, Home: () => 0, End: (_, n) => n - 1,
};

/** Tabs: only the chosen one's content shows. Arrow keys, Home and End move between them. */
export function Tabs({ label, tabs, value, onChange }: TabsProps) {
  const prefix = useId();
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const current = Math.max(0, tabs.findIndex((t) => t.key === value));
  const onKeyDown = (e: KeyboardEvent) => {
    const move = MOVES[e.key];
    if (!move) return;
    e.preventDefault();
    const next = move(current, tabs.length);
    onChange((tabs[next] as Tab).key);
    refs.current[next]?.focus();
  };
  const chosen = tabs[current];
  return (
    <div className={styles.tabs}>
      <div role="tablist" aria-label={label} className={styles.list} onKeyDown={onKeyDown}>
        {tabs.map((t, i) => (
          <button key={t.key} ref={(el) => { refs.current[i] = el; }} type="button" role="tab" id={`${prefix}-${t.key}`}
            aria-selected={i === current} aria-controls={`${prefix}-panel`} tabIndex={i === current ? 0 : -1}
            className={styles.tab} onClick={() => onChange(t.key)}>{t.label}</button>
        ))}
      </div>
      <div role="tabpanel" id={`${prefix}-panel`} aria-labelledby={chosen && `${prefix}-${chosen.key}`} className={styles.panel}>
        {chosen?.content}
      </div>
    </div>
  );
}
