import { useMemo, type MouseEvent } from 'react';
import { md } from './md';

/** A bubble's markdown, as the Glyphh Bot app renders it: tables, checklists, code blocks with Copy. */
export function Markdown({ text }: { text: string }) {
  const html = useMemo(() => md(text), [text]);
  const onClick = (e: MouseEvent) => {
    const btn = (e.target as HTMLElement).closest<HTMLElement>('[data-act="copy"]');
    if (!btn) return;
    const code = btn.closest('.code')?.querySelector('code')?.textContent ?? '';
    void navigator.clipboard?.writeText(code).then(() => {
      btn.textContent = 'Copied';
      setTimeout(() => (btn.textContent = 'Copy'), 1200);
    });
  };
  // The html is md()'s own: every word of the bot's is escaped, links and images go to the web only.
  return <div className="bubble md" onClick={onClick} dangerouslySetInnerHTML={{ __html: html }} />;
}
