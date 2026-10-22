import type { ReactNode } from 'react';
import { Navigate } from 'react-router';
import { useAdaCloud } from '@/api/ada';
import { LoadingCard } from '@/ui';

/**
 * Ada Cloud on or off, as the server says (`ada_cloud` on /v1/me). On, the platform is Ada's: no runtimes, machines,
 * licence or logs. Off, today's pages as they are.
 */
export function AdaOr({ ada, off }: { ada: ReactNode; off: ReactNode }) {
  const on = useAdaCloud();
  if (on === undefined) return <LoadingCard />;
  return <>{on ? ada : off}</>;
}

/** A page of Ada Cloud's only; with it off, `otherwise`. */
export function AdaOnly({ children, otherwise }: { children: ReactNode; otherwise: string }) {
  return <AdaOr ada={children} off={<Navigate to={otherwise} replace />} />;
}

/** A page about runtimes or self-hosting: with Ada Cloud on, Home in its place. */
export function OffOnly({ children }: { children: ReactNode }) {
  return <AdaOr ada={<Navigate to="/" replace />} off={children} />;
}
