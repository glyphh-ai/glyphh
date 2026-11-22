// The Glyphh Bot app's markdown (glyphh-bot src/renderer/src/md.ts), copied for the platform's bot chat: headings,
// paragraphs, lists (nested, numbered, task lists), tables, quotes, rules, fenced code with Copy, diffs, images and
// links. Pure string work, no DOM. Changed for a web page, where a bot's words are not trusted: a link or an image
// goes only to http(s) (an image also to a data: image), anything else stays as its text; there is no folder on disk
// to open, so no "Open in editor"; mermaid and math stay as their source.

export const esc = (s: string): string =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

export interface MdOptions {
  /** The workspace folder: relative image paths are read from it. */
  base?: string
}

/** A link a bot's words may hold: the web or an email address, nothing that runs. */
export const safeHref = (href: string): boolean => /^(https?:\/\/|mailto:)/i.test(href.trim())

/** Where an image's src points: the web and data: images as they are, anything else nowhere. */
export function imageSrc(src: string, _base = ''): string {
  return /^(https?:\/\/|data:image\/(png|jpe?g|gif|webp);)/i.test(src.trim()) ? src.trim() : ''
}

/** Text inside a block: code spans, math, bold, italic, strike, images, links, bare urls. */
export function inline(s: string, o: MdOptions = {}): string {
  const keep: string[] = []
  const stash = (html: string): string => `\u0000${keep.push(html) - 1}\u0000`
  let t = s
    .replace(/`([^`\n]+)`/g, (_, c: string) => stash(`<code>${esc(c)}</code>`))
    .replace(/\$\$([^$\n]+)\$\$/g, (_, m: string) => stash(`<span class="math" data-tex="${esc(m)}">${esc(m)}</span>`))
    .replace(/(^|[^\\$\w])\$([^\s$](?:[^$\n]*[^\s$])?)\$(?![\w$])/g, (all, pre: string, m: string) =>
      /^\d[\d.,]*$/.test(m) ? all : pre + stash(`<span class="math i" data-tex="${esc(m)}">${esc(m)}</span>`)
    )
    .replace(/!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g, (_, alt: string, src: string) =>
      stash(imageSrc(src, o.base) ? `<img class="mdimg" alt="${esc(alt)}" src="${esc(imageSrc(src, o.base))}" />` : esc(alt))
    )
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, label: string, href: string) =>
      stash(safeHref(href) ? `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${inline(label, o)}</a>` : inline(label, o))
    )
    .replace(/(^|[\s(])(https?:\/\/[^\s<)]+[^\s<).,;:!?'"])/g, (_, pre: string, url: string) =>
      pre + stash(`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(url)}</a>`)
    )
  t = esc(t)
    .replace(/\*\*([^*\n]+)\*\*/g, '<b>$1</b>')
    .replace(/__([^_\n]+)__/g, '<b>$1</b>')
    .replace(/(^|[^*\w])\*([^*\s][^*\n]*?)\*(?!\w)/g, '$1<i>$2</i>')
    .replace(/(^|[^_\w])_([^_\s][^_\n]*?)_(?!\w)/g, '$1<i>$2</i>')
    .replace(/~~([^~\n]+)~~/g, '<s>$1</s>')
  return t.replace(/\u0000(\d+)\u0000/g, (_, i: string) => keep[Number(i)]!)
}

/** One line of a unified diff, classed for colour. */
export function diffLineClass(l: string): string {
  if (l.startsWith('+++') || l.startsWith('---') || l.startsWith('diff ') || l.startsWith('index ')) return 'h'
  if (l.startsWith('@@')) return 'at'
  if (l.startsWith('+')) return 'a'
  if (l.startsWith('-')) return 'd'
  return ''
}

/** Lines added and removed in a diff. */
export function diffStat(text: string): { added: number; removed: number } {
  let added = 0
  let removed = 0
  for (const l of text.split('\n')) {
    if (l.startsWith('+') && !l.startsWith('+++')) added++
    else if (l.startsWith('-') && !l.startsWith('---')) removed++
  }
  return { added, removed }
}

export function diffHtml(text: string): string {
  return text
    .replace(/\n$/, '')
    .split('\n')
    .map((l) => `<div class="${diffLineClass(l)}">${esc(l) || ' '}</div>`)
    .join('')
}

function fence(lang: string, body: string, open: boolean): string {
  const l = lang.toLowerCase()
  if (l === 'diff' || l === 'patch') {
    const st = diffStat(body)
    const files = (body.match(/^\+\+\+ (?:b\/)?(.+)$/gm) ?? []).map((x) => x.replace(/^\+\+\+ (?:b\/)?/, ''))
    const name = files.length === 1 ? files[0]! : files.length ? `${files.length} files` : 'Diff'
    return `<details class="mdiff"${open ? ' open' : ''}><summary><span class="fname">${esc(name)}</span><i class="add">+${st.added}</i><i class="del">−${st.removed}</i></summary><pre class="diff">${diffHtml(body)}</pre></details>`
  }
  return `<div class="code" data-lang="${esc(l)}"><div class="code-head"><span>${esc(l || 'text')}</span><button type="button" data-act="copy">Copy</button></div><pre><code>${esc(body)}</code></pre></div>`
}

const splitRow = (row: string): string[] =>
  row
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split(/(?<!\\)\|/)
    .map((c) => c.trim().replace(/\\\|/g, '|'))

const isSep = (row: string): boolean => row.includes('-') && /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/.test(row)

/** Markdown to html. A fence left open (while a reply streams in) shows as code so far. */
export function renderMarkdown(text: string, o: MdOptions = {}): string {
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const out: string[] = []
  let para: string[] = []
  // Open lists: their kind and the indent they sit at.
  const lists: { kind: 'ul' | 'ol'; indent: number }[] = []
  const endPara = (): void => {
    if (para.length) out.push(`<p>${para.map((p) => inline(p, o)).join('<br/>')}</p>`)
    para = []
  }
  const endLists = (to = 0): void => {
    while (lists.length > to) out.push(`</li></${lists.pop()!.kind}>`)
  }
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!
    const f = line.match(/^\s*(```+|~~~+)\s*([\w+#.-]*)/)
    if (f) {
      endPara()
      endLists()
      const body: string[] = []
      let closed = false
      for (i++; i < lines.length; i++) {
        if (lines[i]!.trim().startsWith(f[1]!)) {
          closed = true
          break
        }
        body.push(lines[i]!)
      }
      out.push(fence(f[2] ?? '', body.join('\n'), !closed || body.length <= 40))
      continue
    }
    if (/^\s*\$\$\s*$/.test(line)) {
      endPara()
      endLists()
      const body: string[] = []
      for (i++; i < lines.length && !/^\s*\$\$\s*$/.test(lines[i]!); i++) body.push(lines[i]!)
      out.push(fence('math', body.join('\n'), true))
      continue
    }
    const h = line.match(/^(#{1,6})\s+(.*?)\s*#*\s*$/)
    if (h) {
      endPara()
      endLists()
      out.push(`<h${h[1]!.length}>${inline(h[2]!, o)}</h${h[1]!.length}>`)
      continue
    }
    if (line.includes('|') && i + 1 < lines.length && isSep(lines[i + 1]!)) {
      endPara()
      endLists()
      const head = splitRow(line)
      const align = splitRow(lines[i + 1]!).map((c) => (c.startsWith(':') && c.endsWith(':') ? 'center' : c.endsWith(':') ? 'right' : ''))
      const td = (c: string, k: number, tag: string): string => `<${tag}${align[k] ? ` style="text-align:${align[k]}"` : ''}>${inline(c, o)}</${tag}>`
      const rows: string[] = []
      for (i += 2; i < lines.length && lines[i]!.includes('|') && lines[i]!.trim(); i++) rows.push(`<tr>${splitRow(lines[i]!).map((c, k) => td(c, k, 'td')).join('')}</tr>`)
      i--
      out.push(`<div class="mdtable"><table><thead><tr>${head.map((c, k) => td(c, k, 'th')).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`)
      continue
    }
    const li = line.match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/)
    if (li) {
      endPara()
      const indent = li[1]!.replace(/\t/g, '  ').length
      const kind = /\d/.test(li[2]!) ? 'ol' : 'ul'
      while (lists.length && indent < lists.at(-1)!.indent) endLists(lists.length - 1)
      const top = lists.at(-1)
      if (!top || indent > top.indent) {
        const start = kind === 'ol' && parseInt(li[2]!, 10) !== 1 ? ` start="${parseInt(li[2]!, 10)}"` : ''
        lists.push({ kind, indent })
        out.push(`<${kind}${start}>`)
      } else if (top.kind !== kind) {
        endLists(lists.length - 1)
        lists.push({ kind, indent })
        out.push(`<${kind}>`)
      } else out.push('</li>')
      const task = li[3]!.match(/^\[([ xX])\]\s+(.*)$/)
      out.push(
        task
          ? `<li class="task"><input type="checkbox" disabled${task[1] !== ' ' ? ' checked' : ''}/> ${inline(task[2]!, o)}`
          : `<li>${inline(li[3]!, o)}`
      )
      continue
    }
    if (lists.length && /^\s{2,}\S/.test(line)) {
      out.push(`<br/>${inline(line.trim(), o)}`)
      continue
    }
    if (/^\s*>/.test(line)) {
      endPara()
      endLists()
      const q: string[] = []
      for (; i < lines.length && /^\s*>/.test(lines[i]!); i++) q.push(lines[i]!.replace(/^\s*>\s?/, ''))
      i--
      out.push(`<blockquote>${renderMarkdown(q.join('\n'), o)}</blockquote>`)
      continue
    }
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) {
      endPara()
      endLists()
      out.push('<hr/>')
      continue
    }
    if (/^\s*DONE\.?\s*$/.test(line)) {
      endPara()
      endLists()
      out.push('<span class="done">DONE</span>')
      continue
    }
    if (!line.trim()) {
      endPara()
      if (lists.length && !/^(\s*)([-*+]|\d+[.)])\s+/.test(lines[i + 1] ?? '')) endLists()
      continue
    }
    endLists()
    para.push(line.trim())
  }
  endPara()
  endLists()
  return out.join('\n')
}

/** The chat's renderer. */
export const md = renderMarkdown

/** A markdown file rendered for reading (the Editor's preview). */
export const mdDoc = (text: string, base?: string): string => renderMarkdown(text, { base })

/** A file extension for a code block's language, for "Open in editor". */
export function extFor(lang: string): string {
  const m: Record<string, string> = {
    typescript: 'ts', ts: 'ts', tsx: 'tsx', javascript: 'js', js: 'js', jsx: 'jsx', python: 'py', py: 'py',
    json: 'json', html: 'html', css: 'css', bash: 'sh', sh: 'sh', shell: 'sh', zsh: 'sh', yaml: 'yml', yml: 'yml',
    markdown: 'md', md: 'md', go: 'go', rust: 'rs', rs: 'rs', ruby: 'rb', java: 'java', c: 'c', cpp: 'cpp', sql: 'sql', swift: 'swift', kotlin: 'kt'
  }
  return m[lang.toLowerCase()] ?? 'txt'
}

/** The Monaco language id for a code block's tag. */
export function monacoLang(lang: string): string {
  const m: Record<string, string> = {
    ts: 'typescript', tsx: 'typescript', js: 'javascript', jsx: 'javascript', py: 'python', sh: 'shell', bash: 'shell', zsh: 'shell', yml: 'yaml', md: 'markdown', rs: 'rust', rb: 'ruby', kt: 'kotlin'
  }
  const l = lang.toLowerCase()
  return m[l] ?? l
}
