import { useRef, type KeyboardEvent } from 'react';
import { cx } from '@/lib/cx';
import styles from './Tabs.module.css';

export type Tab<T extends string> = { id: T; label: string };

/** The ids that tie a tab to its panel: the panel takes `panelId(id)` and is labelled by `tabId(id)`. */
export const tabId = (id: string) => `tab-${id}`;
export const panelId = (id: string) => `panel-${id}`;

type TabsProps<T extends string> = {
  /** What the tabs choose between, for a screen reader. */
  label: string;
  tabs: ReadonlyArray<Tab<T>>;
  value: T;
  onChange: (id: T) => void;
};

/** A row of tabs over one panel. The arrow keys, Home and End move between them, as a tab list's do. */
export function Tabs<T extends string>({ label, tabs, value, onChange }: TabsProps<T>) {
  const list = useRef<HTMLDivElement>(null);

  function onKeyDown(event: KeyboardEvent) {
    const at = tabs.findIndex((tab) => tab.id === value);
    const to = { ArrowRight: at + 1, ArrowLeft: at - 1, Home: 0, End: tabs.length - 1 }[event.key];
    if (to === undefined) return;
    event.preventDefault();
    const next = tabs[(to + tabs.length) % tabs.length]!;
    onChange(next.id);
    list.current?.querySelector<HTMLElement>(`#${tabId(next.id)}`)?.focus();
  }

  return (
    <div ref={list} role="tablist" aria-label={label} className={styles.tabs} onKeyDown={onKeyDown}>
      {tabs.map((tab) => {
        const selected = tab.id === value;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={tabId(tab.id)}
            aria-selected={selected}
            aria-controls={panelId(tab.id)}
            tabIndex={selected ? 0 : -1}
            className={cx(styles.tab, selected && styles.selected)}
            onClick={() => onChange(tab.id)}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
