import { createContext, useContext, useEffect, type ReactNode } from 'react';
import type { RunStatus } from '@/api/bots';
import { Cat } from '@/bots/cat/Cat';
import type { Look } from '@/bots/cat/look';
import { mascotSrc } from '@/bots/cat/mascots';

export const botPath = (slug: string) => `/bots/${encodeURIComponent(slug)}`;
/**
 * The crew's room. `/bots` with nothing chosen opens the orchestrator's chat, so the crew says it is the crew
 * (`room=crew`); the word is the address's only, the crew is still state and not a page.
 */
export const CREW_ROOM = 'crew';
export const CREW_PATH = `/bots?room=${CREW_ROOM}`;

/** What the shell's parts ask of it: say something in a toast, open Decisions, the editor or the connections. */
export type ShellApi = {
  toast: (text: string) => void;
  openDecisions: () => void;
  /** A bot's settings; none makes a new bot. */
  editBot: (slug: string | null) => void;
  /** The rail's CONNECTIONS, the one place they are; `catalog` opens the apps there are to add. */
  openConnections: (catalog?: boolean) => void;
};
export const ShellContext = createContext<ShellApi>({ toast: () => undefined, openDecisions: () => undefined, editBot: () => undefined, openConnections: () => undefined });
export const useShell = () => useContext(ShellContext);

type FaceProps = { look: Partial<Look> | null | undefined; mascot?: string | null; size: number; mode?: 'head' | 'full'; busy?: boolean; label?: string };

/** A bot's cat, or its own drawn mascot (as an image, so nothing in it runs) in the cat's place. */
export function BotCat({ look, mascot, size, mode = 'head', busy, label }: FaceProps) {
  if (mascot) return <img className="cat-svg mascot" src={mascotSrc(mascot)} width={size} height={mode === 'full' ? size * 1.21 : size} alt={label ?? ''} />;
  return <Cat look={look} size={size} mode={mode} busy={busy} label={label} />;
}

/** A run's state as the rail and a turn's tag say it. */
export const RUN_WORDS: Record<RunStatus, string> = {
  queued: 'queued',
  running: 'working',
  dispatched: 'working there',
  needs_input: 'Needs you',
  done: 'done',
  failed: 'failed',
  skipped: 'cancelled',
};

/** A model's name cut to fit a chip: "Claude Sonnet 5.5 (default)" is "Sonnet 5.5". */
export const shortModel = (label: string): string => label.replace(/\s*\(.*\)\s*$/, '').replace(/^Claude\s+/i, '').trim() || label;

/** How hard a bot thinks, as the pills and the editor say it. */
export const EFFORTS: ReadonlyArray<{ value: string; label: string }> = [
  { value: 'low', label: 'Low effort' },
  { value: 'medium', label: 'Medium effort' },
  { value: 'high', label: 'High effort' },
];
/** The three the screen offers, and the bot's own when it is another the server takes. */
export const effortOptions = (current: string | undefined) =>
  current && !EFFORTS.some((e) => e.value === current) ? [...EFFORTS, { value: current, label: `${current[0]!.toUpperCase()}${current.slice(1)} effort` }] : EFFORTS;

/** What Glyphh cloud cannot do, said wherever it is chosen. */
export const CLOUD_NOTE =
  "Glyphh cloud has fewer tools than a rrotor: bots can read and change files and open pull requests, but can't run commands, tests or a browser. Choose a rrotor for those.";

/** Escape closes what is open (a modal, a menu). */
export function useEscape(onClose: () => void, on = true) {
  useEffect(() => {
    if (!on) return;
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, [onClose, on]);
}

/** A modal as the Glyphh Bot app draws one: the veil, the card, its title and a close. */
export function Modal({ title, children, wide, small, onClose, front, icon }: { title: string; children: ReactNode; wide?: boolean; small?: boolean; onClose: () => void; front?: boolean; icon?: ReactNode }) {
  useEscape(onClose);
  return (
    <div className={front ? 'veil front' : 'veil'} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={wide ? 'modal wide' : small ? 'modal confirm' : 'modal'} role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <h2>
            {icon}
            {title}
          </h2>
          <button type="button" className="icon" aria-label="Close" onClick={onClose}>
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
