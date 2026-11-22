import { createContext, useContext, useEffect, type ReactNode } from 'react';
import type { Bot, BotRun, BotSpec, RunStatus } from '@/api/bots';
import { Cat } from '@/bots/cat/Cat';
import type { Look } from '@/bots/cat/look';
import { mascotSrc } from '@/bots/cat/mascots';
import { plural } from '@/lib/format';
import { decisionsOf } from '../ada';

/** What the shell's parts ask of it: say something in a toast, open or close a panel or the editor. */
export type PanelId = 'decisions' | 'gates' | 'tools';
export type ShellApi = {
  toast: (text: string) => void;
  openPanel: (id: PanelId) => void;
  editBot: (slug: string | null, advanced?: boolean) => void;
};
export const ShellContext = createContext<ShellApi>({ toast: () => undefined, openPanel: () => undefined, editBot: () => undefined });
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

/** "Ran 4 steps, asked Ada 3 times": what a run did, in a line (the app's toolSummary, for a bot's loop). */
export function runSummary(run: BotRun, spec: BotSpec): string {
  const decided = decisionsOf(run, spec).reduce((n, d) => n + Math.max(1, d.items.length), 0);
  const parts = [`ran ${plural(run.log.length, 'step')}`];
  if (decided) parts.push(`asked Ada ${plural(decided, 'time')}`);
  const s = parts.join(', ');
  return s[0]!.toUpperCase() + s.slice(1);
}

/** A model's name cut to fit a chip: "Claude Sonnet 5.5 (default)" is "Sonnet 5.5". */
export const shortModel = (label: string): string => label.replace(/\s*\(.*\)\s*$/, '').replace(/^Claude\s+/i, '').trim() || label;

/** The small mono tag beside a bot's name: how many gates it has in Ada. */
export const botTag = (bot: Bot): string => (bot.gate_models.length ? plural(bot.gate_models.length, 'gate') : '');

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
export function Modal({ title, children, wide, small, onClose, front }: { title: string; children: ReactNode; wide?: boolean; small?: boolean; onClose: () => void; front?: boolean }) {
  useEscape(onClose);
  return (
    <div className={front ? 'veil front' : 'veil'} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={wide ? 'modal wide' : small ? 'modal confirm' : 'modal'} role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button type="button" className="icon" aria-label="Close" onClick={onClose}>
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
