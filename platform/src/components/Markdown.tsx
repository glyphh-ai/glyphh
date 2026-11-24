import { Fragment, type ReactNode } from 'react';
import styles from './Markdown.module.css';

/**
 * Markdown someone else wrote (a plugin's README, a skill's instructions), shown as text a person reads: headings,
 * lists, tables, code, quotes, rules, paragraphs, bold, italics, code spans and links. Built as React elements, never
 * as HTML, so nothing in the text runs: a tag in it shows as the characters it is, and a link goes to http(s) only.
 */

const INLINE = /(`[^`]+`|!?\[[^\]]*\]\([^)\s]+(?:\s+"[^"]*")?\)|\*\*[^*]+\*\*|__[^_]+__|\*[^*\s][^*]*\*|_[^_\s][^_]*_)/g;

/** One line's bold, italics, code spans, links and images (an image is its words; nothing is loaded from elsewhere). */
export function inline(text: string): ReactNode[] {
  return text.split(INLINE).map((part, i) => {
    if (part.startsWith('`') && part.endsWith('`') && part.length > 1) return <code key={i}>{part.slice(1, -1)}</code>;
    if ((part.startsWith('**') || part.startsWith('__')) && part.length > 4) return <strong key={i}>{inline(part.slice(2, -2))}</strong>;
    const link = /^(!?)\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)$/.exec(part);
    if (link) {
      const [, image, label = '', href = ''] = link;
      if (image) return <Fragment key={i}>{label}</Fragment>;
      return /^https?:\/\//i.test(href) ? (
        <a key={i} href={href} target="_blank" rel="noreferrer noopener">
          {inline(label)}
        </a>
      ) : (
        <Fragment key={i}>{inline(label)}</Fragment>
      );
    }
    if (/^(\*[^*\s][^*]*\*|_[^_\s][^_]*_)$/.test(part)) return <em key={i}>{part.slice(1, -1)}</em>;
    return <Fragment key={i}>{part}</Fragment>;
  });
}

type Block = { kind: 'h' | 'p' | 'ul' | 'ol' | 'code' | 'quote' | 'rule' | 'table'; level?: number; lines: string[] };

const cells = (row: string): string[] =>
  row
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split(/(?<!\\)\|/)
    .map((cell) => cell.trim().replace(/\\\|/g, '|'));
const isDivider = (row: string) => row.includes('-') && /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/.test(row);

/** The text cut into blocks: fenced code, a heading, a list, a table, a quote, a rule, else a paragraph. */
export function blocks(text: string): Block[] {
  const out: Block[] = [];
  let open: Block | null = null;
  let fence: string | null = null;
  // Comments are for the file's writer, not its reader.
  const lines = text.replace(/<!--[\s\S]*?-->/g, '').split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!;
    const fenced = /^\s*(```+|~~~+)/.exec(line);
    if (fence !== null) {
      if (fenced && fenced[1]!.startsWith(fence)) fence = open = null;
      else open!.lines.push(line);
      continue;
    }
    if (fenced) {
      fence = fenced[1]!;
      out.push((open = { kind: 'code', lines: [] }));
      continue;
    }
    const heading = /^(#{1,6})\s+(.*?)\s*#*\s*$/.exec(line);
    const bullet = /^\s*[-*+]\s+(.*)$/.exec(line);
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    const quote = /^\s*>\s?(.*)$/.exec(line);
    // The block the line before left open, read through one name so each branch below sees all its kinds.
    const before = open as Block | null;
    if (heading) {
      out.push({ kind: 'h', level: heading[1]!.length, lines: [heading[2] ?? ''] });
      open = null;
    } else if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) {
      out.push({ kind: 'rule', lines: [] });
      open = null;
    } else if (line.includes('|') && isDivider(lines[i + 1] ?? '')) {
      out.push((open = { kind: 'table', lines: [line] }));
      i++;
    } else if (before?.kind === 'table' && line.includes('|') && line.trim() !== '') {
      before.lines.push(line);
    } else if (bullet || numbered || quote) {
      const kind = bullet ? 'ul' : numbered ? 'ol' : 'quote';
      const said = (bullet ?? numbered ?? quote)![1] ?? '';
      if (before?.kind === kind) before.lines.push(said);
      else out.push((open = { kind, lines: [said] }));
    } else if (line.trim() === '') {
      open = null;
    } else if ((before?.kind === 'ul' || before?.kind === 'ol') && /^\s{2,}\S/.test(line)) {
      // A list item's next line.
      before.lines[before.lines.length - 1] += ` ${line.trim()}`;
    } else if (before?.kind === 'p') {
      before.lines.push(line.trim());
    } else {
      out.push((open = { kind: 'p', lines: [line.trim()] }));
    }
  }
  return out;
}

function shown(block: Block, i: number): ReactNode {
  if (block.kind === 'code') return <pre key={i}>{block.lines.join('\n')}</pre>;
  if (block.kind === 'rule') return <hr key={i} />;
  if (block.kind === 'h') {
    // The page has its own h1 and h2: a file's headings sit under them.
    const Tag = (block.level! <= 2 ? 'h3' : 'h4') as 'h3' | 'h4';
    return <Tag key={i}>{inline(block.lines[0] ?? '')}</Tag>;
  }
  if (block.kind === 'ul' || block.kind === 'ol') {
    const List = block.kind;
    return (
      <List key={i}>
        {block.lines.map((line, j) => (
          <li key={j}>{inline(line)}</li>
        ))}
      </List>
    );
  }
  if (block.kind === 'table') {
    const [head = '', ...rows] = block.lines;
    return (
      <div key={i} className={styles.table}>
        <table>
          <thead>
            <tr>
              {cells(head).map((cell, j) => (
                <th key={j}>{inline(cell)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, j) => (
              <tr key={j}>
                {cells(row).map((cell, k) => (
                  <td key={k}>{inline(cell)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  if (block.kind === 'quote') return <blockquote key={i}>{inline(block.lines.join(' '))}</blockquote>;
  return <p key={i}>{inline(block.lines.join(' '))}</p>;
}

export function Markdown({ text, label }: { text: string; label?: string }) {
  return (
    <div className={styles.markdown} aria-label={label}>
      {blocks(text).map(shown)}
    </div>
  );
}
