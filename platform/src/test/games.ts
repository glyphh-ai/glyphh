import type { Overview } from '@/games/api';
import { http, HttpResponse } from './server';

/** The games' admin as the platform's route handlers answer it (/api/games), with the games faked. */

export const overview: Overview = {
  at: 1_763_500_000_000,
  games: [
    {
      id: 'frank',
      name: 'Free Fall Frank',
      site: 'https://freefallfrank.com',
      icon: 'https://freefallfrank.com/icon-192.png',
      connected: true,
      health: { ok: true, build: '29d40a007e', ms: 80 },
      error: null,
      summary: {
        players: 12_480,
        playersAre: 'devices',
        new24: 214,
        active24: 1_032,
        revenue: { today: 297, d7: 2_574, d30: null, all: 48_312 },
        pending: [{ label: 'Levels to review', count: 3, tab: 'review' }],
      },
    },
    {
      id: 'crabby',
      name: 'Crabby Knife Fight',
      site: 'https://crabbyknifefight.com',
      icon: 'https://crabbyknifefight.com/icon-192.png',
      connected: true,
      health: { ok: true, build: 'af3a39fca3', ms: 90 },
      error: null,
      summary: { players: 2_311, playersAre: 'devices', new24: 41, active24: 187, revenue: null, pending: [{ label: 'Open reports', count: 0, tab: 'reports' }] },
    },
    {
      id: 'mahj',
      name: 'Bams & Brags',
      site: 'https://bamsandbrags.com',
      icon: 'https://bamsandbrags.com/icon-192.png',
      connected: true,
      health: { ok: false, build: null, ms: 8000 },
      error: 'Bams & Brags did not answer.',
      summary: null,
    },
    {
      id: 'carol',
      name: 'Send a Carol',
      site: 'https://sendacarol.com',
      icon: 'https://sendacarol.com/favicon.ico',
      connected: false,
      health: { ok: true, build: 'c505da9f01', ms: 70 },
      error: 'GAME_ADMIN_KEY_CAROL is not set on the platform.',
      summary: null,
    },
  ],
};

/** Each game's tools as a game answers them, by "<game>/<tool>". */
export const toolAnswers: Record<string, unknown> = {
  'frank/admin_queue': {
    waiting: 2,
    levels: [
      { id: 'lv1', name: 'Rooftops', author: 'Sam', maker: 'google:1', made: '2026-11-18', world: 'city', play_url: 'https://freefallfrank.com/?level=lv1', status: 'pending' },
      { id: 'lv2', name: 'Sewer run', author: 'Jo', maker: 'google:2', made: '2026-11-19', world: 'sewer', play_url: 'https://freefallfrank.com/?level=lv2', status: 'pending' },
    ],
  },
  'frank/admin_stats': {
    site: 'https://freefallfrank.com',
    overview: { players: 12_480, players24: 214, accounts: 902, revenue: 48_312 },
    days: [{ d: '2026-11-19', players: 214, runs: 5_120, revenue: 297 }],
    ad_links: [{ code: 'reddit-claude', note: 'Reddit, the Claude post', players: 410, played: 380, stayed: 120, signed: 30, buyers: 4, revenue: 396 }],
    note: 'Times are seconds, money is cents.',
  },
  'frank/admin_players': { total: 1, players: [{ did: 'd1', name: 'Sam', email: 'sam@example.com', src: 'reddit-claude', runs: 40, best: 88, coins: 120, paid: 99, last: 1_763_500_000_000 }] },
  'frank/admin_player': { did: 'd1', account: { name: 'Sam', email: 'sam@example.com' }, purchases: [{ kind: 'pack:1', amount: 99 }] },
  'crabby/admin_list': {
    total: 2,
    pages: 2,
    page: 0,
    items: [
      { id: 'google:7', nick: 'Pinchy', name: 'Pat', email: 'pat@example.com', created: 1_763_400_000_000, banned: 0, why: null, clears: 3, made: 1, reported: 2 },
      { id: 'google:8', nick: 'Clawd', name: 'Lee', email: 'lee@example.com', created: 1_763_300_000_000, banned: 1, why: 'cheating', clears: 0, made: 0, reported: 5 },
    ],
  },
  'mahj/admin_list': {
    total: 1,
    pages: 1,
    page: 0,
    items: [{ id: 'email:ann@example.com', name: 'Ann', email: 'ann@example.com', country: 'US', city: 'Austin', hands: 120, pass: 1, reported: 0, banned: 0, updated: 1_763_500_000_000 }],
  },
  'carol/admin_cards': {
    total: 1,
    pages: 1,
    page: 1,
    items: [{ id: 'c1', card_name: 'mum-xmas', title: { quoted: 'For Mum' }, state: 'ready', occasion: 'christmas', paid: true, opens: 4, maker: 'kid@example.com', updated: 1_763_500_000_000 }],
  },
};

export const gamesHandlers = () => [
  http.get('*/api/games/overview', () => HttpResponse.json(overview)),
  http.post('*/api/games/:game/tools/:tool', ({ params }) => {
    const answer = toolAnswers[`${params.game as string}/${params.tool as string}`];
    return HttpResponse.json({ result: answer ?? { ok: true } });
  }),
];
