import { useEffect, useRef } from 'react';
import type { ProjectRun } from '@/api/projects';

/**
 * Reads new turns aloud with the browser's own voice, only while `on` (the crew's Narrate when watched) and the
 * crew's chat is open and in front. A run mostly goes unwatched: nothing here speaks unless asked to, and what was
 * already said when the run came into view is never read back.
 */
export function useNarration(on: boolean, run: ProjectRun | undefined) {
  const heard = useRef<{ id: string; turns: Set<number> } | null>(null);
  useEffect(() => {
    if (!run) return;
    const said = run.turns.filter((t) => t.said.trim() !== '');
    if (heard.current?.id !== run.id) {
      heard.current = { id: run.id, turns: new Set(said.map((t) => t.n)) };
      return;
    }
    const fresh = said.filter((t) => !heard.current!.turns.has(t.n));
    for (const t of fresh) heard.current.turns.add(t.n);
    if (!on || fresh.length === 0 || document.hidden) return;
    if (!('speechSynthesis' in window) || typeof SpeechSynthesisUtterance === 'undefined') return;
    for (const t of fresh) window.speechSynthesis.speak(new SpeechSynthesisUtterance(`${t.bot_name}. ${t.said}`));
  }, [on, run]);
  // Turned off, or the chat closed: whatever is being read stops.
  useEffect(() => {
    if (!on) return;
    return () => {
      if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    };
  }, [on]);
}
