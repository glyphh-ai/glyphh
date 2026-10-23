/**
 * Glyphh's staff open the staff view when they sign in (his order, 2026-10-23: "support@glyphh.ai should open to a super
 * admin view of the platform"); they can still use their own org as anyone does. Which one they chose holds for the
 * browser tab (sessionStorage), so signing in again opens the staff view again.
 */
const key = 'glyphh.view';

export function inOrgView(): boolean {
  return sessionStorage.getItem(key) === 'org';
}

export function chooseOrgView(): void {
  sessionStorage.setItem(key, 'org');
}

export function chooseStaffView(): void {
  sessionStorage.removeItem(key);
}
