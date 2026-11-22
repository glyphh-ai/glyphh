import { Fragment, type ReactNode } from 'react';
import styles from './decisions.module.css';

/**
 * Markdown a bot's steps answer with (an agent's digest, a tool's text), shown as text a person reads: headings, lists,
 * code, quotes, paragraphs, bold, italics, code spans and https links. Built as React elements, never as HTML, so
 * nothing in the text runs. Text that came through JSON with its line breaks written out (`\n`) has them back.
 */

/** Line breaks written out as `\n` (text escaped twice on its way), back as breaks; text with real ones is left. */
export function unescaped(text: string): string {
  return text.includes('\n') || !text.includes('\\n') ? text : text.replace(/(?:\\r)?\\n/g, '\n').replace(/\\t/g, '  ');
}

const INLINE = /(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__|\*[^*\s][^*]*\*|_[^_\s][^_]*_|\[[^\]]+\]\([^)\s]+\))/g;

/** One line's bold, italics, code spans and links. */
export function inline(text: string): ReactNode[] {
  return text.split(INLINE).map((part, i) => {
    if (part.startsWith('`') && part.endsWith('`') && part.length > 1) return <code key={i}>{part.slice(1, -1)}</code>;
    if ((part.startsWith('**') || part.startsWith('__')) && part.length > 4) return <strong key={i}>{part.slice(2, -2)}</strong>;
    const link = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(part);
    if (link) {
      const href = link[2] ?? '';
      return /^https?:\/\//.test(href) ? (
        <a key={i} href={href} target="_blank" rel="noreferrer noopener">
          {link[1]}
        </a>
      ) : (
        <Fragment key={i}>{link[1]}</Fragment>
      );
    }
    if (/^(\*[^*\s][^*]*\*|_[^_\s][^_]*_)$/.test(part)) return <em key={i}>{part.slice(1, -1)}</em>;
    return <Fragment key={i}>{part}</Fragment>;
  });
}

type Block = { kind: 'h' | 'p' | 'ul' | 'ol' | 'code' | 'quote'; level?: number; lines: string[] };

/** The text cut into blocks: a fenced code block, a heading, a list, a quote, else a paragraph (blank lines end it). */
export function blocks(text: string): Block[] {
  const out: Block[] = [];
  let open: Block | null = null;
  let fenced = false;
  for (const line of unescaped(text).split(/\r?\n/)) {
    if (/^\s*```/.test(line)) {
      if (fenced) open = null;
      else out.push((open = { kind: 'code', lines: [] }));
      fenced = !fenced;
      continue;
    }
    if (fenced) {
      open!.lines.push(line);
      continue;
    }
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    const bullet = /^\s*[-*+]\s+(.*)$/.exec(line);
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    const quote = /^\s*>\s?(.*)$/.exec(line);
    if (heading) {
      out.push({ kind: 'h', level: heading[1]!.length, lines: [heading[2] ?? ''] });
      open = null;
    } else if (bullet || numbered || quote) {
      const kind = bullet ? 'ul' : numbered ? 'ol' : 'quote';
      const said = (bullet ?? numbered ?? quote)![1] ?? '';
      if (open?.kind === kind) open.lines.push(said);
      else out.push((open = { kind, lines: [said] }));
    } else if (line.trim() === '') {
      open = null;
    } else if (open?.kind === 'p') {
      open.lines.push(line.trim());
    } else {
      out.push((open = { kind: 'p', lines: [line.trim()] }));
    }
  }
  return out;
}

function shown(b: Block, i: number): ReactNode {
  if (b.kind === 'code') return <pre key={i}>{b.lines.join('\n')}</pre>;
  if (b.kind === 'h') {
    const Tag = (b.level! <= 2 ? 'h3' : 'h4') as 'h3' | 'h4';
    return <Tag key={i}>{inline(b.lines[0] ?? '')}</Tag>;
  }
  if (b.kind === 'ul' || b.kind === 'ol') {
    const List = b.kind;
    return (
      <List key={i}>
        {b.lines.map((l, j) => (
          <li key={j}>{inline(l)}</li>
        ))}
      </List>
    );
  }
  if (b.kind === 'quote') return <blockquote key={i}>{inline(b.lines.join(' '))}</blockquote>;
  return <p key={i}>{inline(b.lines.join(' '))}</p>;
}

export function Markdown({ text, label }: { text: string; label?: string }) {
  return (
    <div className={styles.markdown} aria-label={label}>
      {blocks(text).map(shown)}
    </div>
  );
}
