import { useEffect, type ReactNode } from 'react';
import { useLocation } from 'react-router';
import { useSession } from '@/api/session';

/** Signed-in pages only: anyone else goes to log in, and comes back here afterwards. */
export function RequireSession({ children }: { children: ReactNode }) {
  const { data: session, isPending } = useSession();
  const location = useLocation();
  const signedOut = session && !session.signedIn;

  useEffect(() => {
    if (signedOut) window.location.assign(`/login?returnTo=${encodeURIComponent(location.pathname + location.search)}`);
  }, [signedOut, location.pathname, location.search]);

  if (isPending || signedOut) return null;
  return <>{children}</>;
}
