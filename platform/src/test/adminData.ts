import type { AuditPage, OpsEventPage, Traffic } from '@/api/admin';
import * as fixtures from './fixtures';

/** What is left of the staff view's answers, in the server's shapes (its /v1/admin). */

export const staffMe = { ...fixtures.me, email: 'support@glyphh.ai', staff: true };

export const audit: AuditPage = {
  entries: [{ id: 'a1', at: '2026-10-23T10:00:00Z', staff_email: 'support@glyphh.ai', action: 'adminTraffic', org_id: null, target: '/v1/admin/traffic', detail: {}, outcome: 'ok' }],
  next_before: '2026-10-23T09:00:00Z',
};

export const events: OpsEventPage = {
  events: [
    {
      id: 'e1',
      first_at: '2026-10-23T09:00:00Z',
      last_at: '2026-10-23T09:05:00Z',
      severity: 'error',
      kind: 'stripe',
      source: 'glyphh.billing',
      message: 'stripe call failed',
      detail: { path: '/subscriptions/sub_x' },
      org_id: 'o-acme',
      trace_id: 'trace-9',
      count: 3,
      acknowledged_at: null,
      acknowledged_by: null,
    },
    {
      id: 'e2',
      first_at: '2026-10-23T08:00:00Z',
      last_at: '2026-10-23T08:00:00Z',
      severity: 'warning',
      kind: 'worker',
      source: 'glyphh.ada',
      message: 'a worker stopped; starting another',
      detail: {},
      org_id: null,
      trace_id: null,
      count: 1,
      acknowledged_at: '2026-10-23T08:10:00Z',
      acknowledged_by: 'support@glyphh.ai',
    },
  ],
  next_before: null,
};

const point = (day: string, uniques: number) => ({ day, requests: uniques * 9, page_views: uniques * 3, uniques, bytes: 1000, threats: 0, cached_share: 0.4 });
const none = { pages: [], referrers: [], rum_pages: [], rum_referrers: [] };

/** glyphh.ai on a Free plan whose adaptive dataset gives hosts, pages and referrers; glyphh.app with Web Analytics only. */
export const traffic: Traffic = {
  connected: true,
  pulled_at: '2026-10-23T11:05:00Z',
  days: 30,
  since: '2026-09-24',
  last_7: { days: 7, visitors: 4_200, page_views: 9_000, previous_visitors: 3_500, previous_page_views: 9_500, visitors_change: 0.2, page_views_change: -0.0526, sign_ups: 42, conversion: 0.01 },
  last_30: { days: 30, visitors: 18_000, page_views: 40_000, previous_visitors: 0, previous_page_views: 0, visitors_change: null, page_views_change: null, sign_ups: 150, conversion: 0.0083 },
  zones: [
    {
      name: 'glyphh.ai',
      plan: 'Free Website',
      pulled_at: '2026-10-23T11:05:00Z',
      available: { daily: { ok: true, days: 60 }, hosts: { ok: true, days: 3 }, pages: { ok: true, days: 3 }, referrers: { ok: true, days: 3 }, rum: { ok: false, note: 'not authorized for that account' } },
      series: [point('2026-10-22', 600), point('2026-10-23', 700)],
      hosts: [
        { host: 'docs.glyphh.ai', series: [{ day: '2026-10-22', requests: 300, visits: 90 }, { day: '2026-10-23', requests: 320, visits: 95 }] },
        { host: 'glyphh.ai', series: [{ day: '2026-10-22', requests: 5_000, visits: 800 }, { day: '2026-10-23', requests: 5_200, visits: 850 }] },
      ],
      countries: [{ host: '', key: 'GB', n: 3_000 }, { host: '', key: 'US', n: 2_000 }],
      ...none,
      pages: [{ host: 'glyphh.ai', key: '/pricing', n: 700 }, { host: 'docs.glyphh.ai', key: '/quickstart', n: 120 }],
      referrers: [{ host: 'glyphh.ai', key: 'www.google.com', n: 400 }, { host: 'docs.glyphh.ai', key: 'github.com', n: 60 }],
    },
    {
      name: 'glyphh.app',
      plan: 'Free Website',
      pulled_at: '2026-10-23T10:05:00Z',
      available: { daily: { ok: true, days: 60 }, hosts: { ok: false, note: 'Not on this zone’s plan' }, pages: { ok: false }, referrers: { ok: false, note: 'unknown field' }, rum: { ok: true, days: 7 } },
      series: [point('2026-10-22', 50), point('2026-10-23', 60)],
      hosts: [],
      countries: [],
      ...none,
      rum_pages: [{ host: 'glyphh.app', key: '/sign-in', n: 30 }],
      rum_referrers: [{ host: 'glyphh.app', key: 'www.google.com', n: 10 }],
    },
  ],
  github: {
    connected: true,
    repos: [
      {
        name: 'glyphh-ai/glyphh',
        pulled_at: '2026-10-23T11:05:00Z',
        last_14: { views: 900, view_uniques: 310, clones: 120, clone_uniques: 45 },
        total: { views: 1_400, view_uniques: 520, clones: 200, clone_uniques: 77 },
        since: '2026-10-09',
        series: [
          { day: '2026-10-22', views: 60, view_uniques: 20, clones: 8, clone_uniques: 3 },
          { day: '2026-10-23', views: 70, view_uniques: 25, clones: 9, clone_uniques: 4 },
        ],
        referrers: [{ key: 'Google', count: 200, uniques: 80 }],
        paths: [{ key: '/glyphh-ai/glyphh', count: 600, uniques: 250 }],
      },
    ],
  },
};

/** Each GET of the staff view and its answer, for the page tests' fake server. */
export const staffAnswers: Record<string, object> = {
  '/admin/traffic': traffic,
  '/admin/audit': audit,
  '/admin/events': events,
};
