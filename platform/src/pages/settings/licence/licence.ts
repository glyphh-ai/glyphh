import type { LicenceKey, LicenceKeyState } from '@/api/types';
import type { ChipTone } from '@/ui';
import { machinesText, precedentsText } from '../billing/plans';

/** Where a node without network access reads its key. */
export const keyEnv = 'GLYPHH_LICENSE_KEY';
export const keyFile = '/etc/rrotor/license.key';

/** What rrotor runs as with no key: Free's limits. */
export const community = { max_nodes: 1, max_precedents: 5_000, cluster_sync_enabled: false } as const;

/** rrotor holds a key this long past its expiry, then runs as Community. */
export const graceDays = 14;

/** Enough of a key to tell it apart, never enough to use: its first 8 and last 6 characters, as the server masks it. */
export function masked(key: string): string {
  return key.length <= 14 ? '•'.repeat(key.length) : `${key.slice(0, 8)}…${key.slice(-6)}`;
}

/** `pro` as the plan's name: Pro. */
export const tierName = (tier: string) => tier.charAt(0).toUpperCase() + tier.slice(1);

/** A key's terms, as chips: its runtime nodes, precedents per node and sync. */
export function termsText(terms: Pick<LicenceKey, 'max_nodes' | 'max_precedents' | 'cluster_sync_enabled'>): string[] {
  return [
    machinesText(terms.max_nodes),
    precedentsText(terms.max_precedents) ?? 'No precedents',
    terms.cluster_sync_enabled ? 'Sync across runtimes' : 'No sync',
  ];
}

export const stateChip: Record<LicenceKeyState, { label: string; tone: ChipTone }> = {
  live: { label: 'Live', tone: 'green' },
  expired: { label: 'Expired', tone: 'neutral' },
  revoked: { label: 'Revoked', tone: 'red' },
};
