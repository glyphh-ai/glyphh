import type { ReactNode } from 'react';
import { Navigate } from 'react-router';
import { useAdaCloud } from '@/api/ada';
import { LoadingCard } from '@/ui';

/**
 * Ada Cloud on or off, as the server says (`ada_cloud` on /v1/me). On, Home, Models, API Keys and Usage are Ada's, with
 * Runtimes & licences beside them. Off, the runtimes' own pages.
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
