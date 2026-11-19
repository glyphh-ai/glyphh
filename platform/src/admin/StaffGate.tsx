import type { ReactNode } from 'react';
import { useMe } from '@/api/queries';
import { AuthLayout } from '@/layout/AuthLayout/AuthLayout';
import { Button, LoadingCard } from '@/ui';

/** The whole console is staff only (the server refuses anyone else too); anyone else sees one line and Sign out. */
export function RequireStaff({ children }: { children: ReactNode }) {
  const { data: me, isPending } = useMe();
  if (isPending) return <LoadingCard />;
  if (!me?.staff) return <StaffOnlyPage />;
  return <>{children}</>;
}

/** Game players never come here (their accounts live on each game's site); a signed-in non-staff person sees this. */
export function StaffOnlyPage() {
  return (
    <AuthLayout title="This is Glyphh’s staff console.">
      <form method="post" action="/auth/logout">
        <Button type="submit" variant="secondary" style={{ width: '100%' }}>
          Sign out
        </Button>
      </form>
    </AuthLayout>
  );
}
