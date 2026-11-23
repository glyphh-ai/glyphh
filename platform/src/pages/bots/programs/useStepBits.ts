import type { Bot } from '@/api/bots';
import { useToolSearch, type Step } from '@/api/programs';

/** The bot that does a step: its own, or the program's. */
export const botOf = (step: Step, programBot: string | null, bots: Bot[]): Bot | undefined => bots.find((b) => b.slug === (step.bot || programBot));

/** A tool step's action, as the org's tools name it (its title and app), found by its key for the bot that uses it. */
export function useToolName(step: Step, bot: string | null) {
  const key = step.kind === 'tool' ? (step.tool ?? '') : '';
  const found = useToolSearch(key, bot, key !== '');
  return found.data?.find((t) => t.key === key) ?? null;
}
