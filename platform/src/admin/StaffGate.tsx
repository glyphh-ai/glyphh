import type { ReactNode } from 'react';
import { Navigate } from 'react-router';
import { useMe } from '@/api/queries';
import { NavGroup, NavItem } from '@/layout/Sidebar/Sidebar';
import { LoadingCard } from '@/ui';
import { inOrgView } from './staffView';

/** The staff view's pages: staff only (the server refuses anyone else too); anyone else goes home. */
export function RequireStaff({ children }: { children: ReactNode }) {
  const { data: me, isPending } = useMe();
  if (isPending) return <LoadingCard />;
  if (!me?.staff) return <Navigate to="/" replace />;
  return <>{children}</>;
}

/** In their own org's view, staff keep a way back to the staff view, at the foot of the sidebar's pages. */
export function StaffNav() {
  const { data: me } = useMe();
  if (!me?.staff) return null;
  return (
    <NavGroup label="Glyphh">
      <NavItem to="/admin" icon="flag">
        Staff view
      </NavItem>
    </NavGroup>
  );
}

/** Home: for staff, the staff view first, unless they chose their own org in this tab. */
export function StaffHome({ children }: { children: ReactNode }) {
  const { data: me } = useMe();
  if (me?.staff && !inOrgView()) return <Navigate to="/admin" replace />;
  return <>{children}</>;
}
