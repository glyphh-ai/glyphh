/** Line icons, one set: the Glyphh Bot app's (glyphh-bot src/renderer/src/Menu.tsx), with the platform's few added. */
export const ICON = {
  folder: 'M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z',
  refresh: 'M23 4v6h-6M20.49 15a9 9 0 1 1-2.12-9.36L23 10',
  expand: 'M6 9l6 6 6-6',
  collapse: 'M18 15l-6-6-6 6',
  plus: 'M12 5v14M5 12h14',
  chat: 'M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9l-5 4V6a1 1 0 0 1 1-1z',
  settings:
    'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z',
  mic: 'M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM19 11a7 7 0 0 1-14 0M12 18v3',
  more: 'M5 12h.01M12 12h.01M19 12h.01',
  edit: 'M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z',
  recents: 'M12 7v5l3 2M21 12a9 9 0 1 1-3-6.7M21 4v5h-5',
  logOut: 'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9',
  // The platform's own panels: every decision, the gates in Ada, the tools.
  decisions: 'M9 6h11M9 12h11M9 18h11M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2',
  gates: 'M6 3v12M18 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM18 9a9 9 0 0 1-9 9',
  tools: 'M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6',
  menu: 'M3 6h18M3 12h18M3 18h18',
  bots: 'M5 6.5a2 2 0 1 0 4 0 2 2 0 0 0-4 0zM15 6.5a2 2 0 1 0 4 0 2 2 0 0 0-4 0zM10 16.5a2 2 0 1 0 4 0 2 2 0 0 0-4 0zM8.5 8l2.5 6.6M15.5 8 13 14.6M9 6.5h6',
} as const;

export function Icon({ d, size = 16 }: { d: string; size?: number }) {
  return (
    <svg className="ico" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={d} />
    </svg>
  );
}

/** The rings: ticks and arcs turning at their own speeds, white on black (glyphh-bot Hud.tsx). */
export function Reactor({ size, className = '' }: { size: number; className?: string }) {
  return (
    <svg className={`reactor ${className}`} width={size} height={size} viewBox="0 0 200 200" aria-hidden>
      <g className="r1">
        <circle cx="100" cy="100" r="97" strokeDasharray="1 5" />
      </g>
      <g className="r2">
        <circle cx="100" cy="100" r="88" strokeDasharray="92 22 8 22 40 22" strokeWidth="2.2" />
      </g>
      <g className="r3">
        <circle cx="100" cy="100" r="77" strokeDasharray="3 9" strokeWidth="5" />
      </g>
      <g className="r4">
        <circle cx="100" cy="100" r="66" strokeDasharray="130 40 30 40" />
        <path d="M100 30 L104 38 L96 38 Z M100 170 L104 162 L96 162 Z M30 100 L38 96 L38 104 Z M170 100 L162 96 L162 104 Z" />
      </g>
      <g className="r5">
        <circle cx="100" cy="100" r="54" strokeDasharray="2 4" strokeWidth="3" />
      </g>
      <circle className="r0" cx="100" cy="100" r="44" />
    </svg>
  );
}
