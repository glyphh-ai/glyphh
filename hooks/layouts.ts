// The built-in layouts: the first run writes them to ~/.glyphh/workspaces.
import type { Layout } from '../types'

export const DEFAULTS: Layout[] = [
  {
    name: 'Comms',
    cols: 2,
    rows: 2,
    colWidths: [0.55, 0.45],
    rowHeights: [0.5, 0.5],
    cells: [
      { panel: 'browser', col: 0, row: 0, rowSpan: 2, url: 'https://mail.google.com' },
      { panel: 'browser', col: 1, row: 0, url: 'https://app.slack.com' },
      { panel: 'browser', col: 1, row: 1, url: 'https://calendar.google.com' },
    ],
    desktop: { panes: ['browser'], collapseSidebar: false, folder: '/Users/timmetim/development/yo' },
  },
  {
    name: 'Browse + file',
    cols: 2,
    rows: 1,
    colWidths: [0.6, 0.4],
    rowHeights: [1],
    cells: [
      { panel: 'browser', col: 0, row: 0, url: 'https://news.ycombinator.com' },
      { panel: 'file', col: 1, row: 0, path: 'README.md' },
    ],
  },
  {
    name: 'Two browsers',
    cols: 2,
    rows: 2,
    colWidths: [0.5, 0.5],
    rowHeights: [0.65, 0.35],
    cells: [
      { panel: 'browser', col: 0, row: 0, url: 'https://example.com' },
      { panel: 'browser', col: 1, row: 0, url: 'https://en.wikipedia.org/wiki/Special:Random' },
      { panel: 'file', col: 0, row: 1, path: 'README.md' },
      { panel: 'file', col: 1, row: 1, path: 'package.json' },
    ],
  },
  {
    name: 'IDE',
    cols: 3,
    rows: 2,
    colWidths: [0.2, 0.5, 0.3],
    rowHeights: [0.6, 0.4],
    cells: [
      { panel: 'tree', col: 0, row: 0 },
      { panel: 'diff', col: 0, row: 1 },
      { panel: 'editor', col: 1, row: 0 },
      { panel: 'terminal', col: 1, row: 1 },
      { panel: 'claude', col: 2, row: 0, rowSpan: 2 },
    ],
    // Open order is the experiment: does the app place panes by it?
    desktop: { panes: ['terminal', 'changes', 'files'], collapseSidebar: true, folder: '/Users/timmetim/development/yo/app' },
  },
  {
    name: 'Files',
    cols: 2,
    rows: 1,
    colWidths: [0.3, 0.7],
    rowHeights: [1],
    cells: [
      { panel: 'tree', col: 0, row: 0 },
      { panel: 'editor', col: 1, row: 0 },
    ],
    desktop: { panes: ['files'], collapseSidebar: false, folder: '/Users/timmetim/development/yo/app' },
  },
]
