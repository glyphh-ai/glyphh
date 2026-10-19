import type { ReactNode } from 'react';
import { Navigate } from 'react-router';
import { useHosting } from '@/api/queries';
import { LoadingCard } from '@/ui';

/** A page about hosted machines: while Glyphh hosts nothing, Getting started (running rrotor yourself) in its place. */
export function HostedOnly({ children }: { children: ReactNode }) {
  const hosting = useHosting();
  if (hosting === undefined) return <LoadingCard />;
  if (!hosting) return <Navigate to="/getting-started" replace />;
  return children;
}
