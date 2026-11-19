import type { Args } from './api';

/**
 * What each game's admin page shows: its tabs, each one admin tool of that game read and shown, with the actions
 * that game's tools offer on each row or on the tab. Only tools the game has (the platform's server allows no
 * other); nothing here is invented for a game that lacks it.
 */

export type Row = Record<string, any>;

export type Field = {
  name: string;
  label: string;
  kind?: 'text' | 'number' | 'select' | 'check';
  options?: ReadonlyArray<{ value: string; label: string }>;
  required?: boolean;
  hint?: string;
};

export type Action = {
  label: string;
  tool: string;
  /** What the row (or nothing, on a tab's own action) fixes. */
  args?: (row: Row) => Args;
  /** What is asked for first, in a dialog. */
  fields?: readonly Field[];
  /** Can't quietly be taken back: asked in a red dialog. */
  danger?: boolean;
  /** The game answers what would happen first, then needs confirm: true. */
  preview?: boolean;
  /** Offered on a row only when this holds. */
  when?: (row: Row) => boolean;
};

export type View = {
  id: string;
  label: string;
  tool: string;
  args?: Args;
  /** The list in the answer to show as the table; without one, the whole answer is shown. */
  list?: string;
  columns?: readonly string[];
  search?: boolean;
  /** A choice of narrowing, each with the arguments it sends; the first is the default. */
  states?: ReadonlyArray<{ value: string; label: string; args?: Args }>;
  /** Extra fields sent with the read, such as which place's times. */
  inputs?: readonly Field[];
  /** The game pages its lists: the first page's number. */
  paging?: 0 | 1;
  /** A row's own page, opened in a dialog. */
  open?: { tool: string; args: (row: Row) => Args };
  rowActions?: readonly Action[];
  /** Actions on the tab itself, asking for what they need. */
  tabActions?: readonly Action[];
};

export type GameCatalog = { id: string; name: string; views: readonly View[] };

const reason: Field = { name: 'reason', label: 'Reason', required: true, hint: 'Kept in the game’s record of actions.' };
const all = { value: '', label: 'All' };
const s = (value: string, label: string, args?: Args) => ({ value, label, args: args ?? { state: value } });

const frank: GameCatalog = {
  id: 'frank',
  name: 'Free Fall Frank',
  views: [
    {
      id: 'review',
      label: 'To review',
      tool: 'admin_queue',
      list: 'levels',
      columns: ['name', 'author', 'maker', 'made', 'world', 'play_url'],
      rowActions: [
        { label: 'Approve', tool: 'admin_review', args: (r) => ({ id: r.id, decision: 'approve' }) },
        {
          label: 'Decline',
          tool: 'admin_review',
          danger: true,
          args: (r) => ({ id: r.id, decision: 'decline' }),
          fields: [{ name: 'note', label: 'Why, for its maker', required: true }],
        },
      ],
    },
    {
      id: 'levels',
      label: 'Levels',
      tool: 'admin_levels',
      list: 'levels',
      columns: ['name', 'author', 'status', 'plays', 'made', 'note', 'play_url'],
      rowActions: [
        { label: 'Approve', tool: 'admin_review', args: (r) => ({ id: r.id, decision: 'approve' }), when: (r) => r.status !== 'public' },
        {
          label: 'Take off',
          tool: 'admin_review',
          danger: true,
          args: (r) => ({ id: r.id, decision: 'decline' }),
          fields: [{ name: 'note', label: 'Why, for its maker', required: true }],
          when: (r) => r.status === 'public',
        },
      ],
    },
    {
      id: 'players',
      label: 'Players',
      tool: 'admin_players',
      args: { limit: 200 },
      list: 'players',
      columns: ['name', 'email', 'src', 'runs', 'best', 'coins', 'paid', 'last'],
      open: { tool: 'admin_player', args: (r) => ({ did: r.did }) },
    },
    { id: 'payments', label: 'Payments', tool: 'admin_payments', list: 'payments' },
    { id: 'stats', label: 'Stats', tool: 'admin_stats' },
    {
      id: 'sponsors',
      label: 'Sponsors',
      tool: 'admin_ads',
      list: 'ads',
      columns: ['id', 'text', 'sub', 'url', 'color', 'live', 'views', 'clicks'],
      rowActions: [
        { label: 'Switch off', tool: 'admin_ad_set', args: (r) => ({ id: r.id, live: false }), when: (r) => r.live === true },
        { label: 'Switch on', tool: 'admin_ad_set', args: (r) => ({ id: r.id, live: true }), when: (r) => r.live !== true },
      ],
      tabActions: [
        {
          label: 'Add or change a sponsor',
          tool: 'admin_ad_set',
          fields: [
            { name: 'id', label: 'Short name', required: true, hint: 'a-z, 0-9, - and _. An existing one is changed.' },
            { name: 'text', label: 'Sign', hint: '2 to 12 characters.' },
            { name: 'sub', label: 'Second line', hint: 'Up to 22 characters.' },
            { name: 'url', label: 'Link', hint: 'https://…' },
            { name: 'color', label: 'Colour', hint: 'Like #ff4fd8.' },
          ],
        },
      ],
    },
    {
      id: 'links',
      label: 'Ad links',
      tool: 'admin_stats',
      list: 'ad_links',
      columns: ['code', 'note', 'players', 'played', 'stayed', 'signed', 'buyers', 'revenue'],
      tabActions: [
        {
          label: 'New ad link',
          tool: 'admin_campaign_set',
          fields: [
            { name: 'code', label: 'Code', required: true, hint: 'The link is freefallfrank.com/?src=<code>.' },
            { name: 'note', label: 'What it is for' },
          ],
        },
      ],
    },
  ],
};

const crabby: GameCatalog = {
  id: 'crabby',
  name: 'Crabby Knife Fight',
  views: [
    { id: 'overview', label: 'Overview', tool: 'admin_overview' },
    {
      id: 'players',
      label: 'Players',
      tool: 'admin_list',
      args: { what: 'players' },
      search: true,
      paging: 0,
      states: [all, s('banned', 'Banned')],
      columns: ['nick', 'name', 'email', 'created', 'banned', 'why', 'clears', 'made', 'reported'],
      rowActions: [
        { label: 'Ban', tool: 'admin_ban', danger: true, args: (r) => ({ uid: r.id }), fields: [{ name: 'why', label: 'Why', required: true }], when: (r) => !r.banned },
        { label: 'Lift ban', tool: 'admin_ban', args: (r) => ({ uid: r.id, lift: true }), when: (r) => Boolean(r.banned) },
      ],
    },
    {
      id: 'places',
      label: 'Made places',
      tool: 'admin_list',
      args: { what: 'places' },
      search: true,
      paging: 0,
      states: [all, s('shown', 'Shown'), s('hidden', 'Hidden')],
      columns: ['name', 'nick', 'email', 'run', 'plays', 'reported', 'hidden', 'why'],
      rowActions: [
        { label: 'Hide', tool: 'admin_hide', danger: true, args: (r) => ({ id: r.id }), fields: [{ name: 'why', label: 'Why', required: true }], when: (r) => !r.hidden },
        { label: 'Show', tool: 'admin_hide', args: (r) => ({ id: r.id, show: true }), when: (r) => Boolean(r.hidden) },
      ],
    },
    {
      id: 'reports',
      label: 'Reports',
      tool: 'admin_list',
      args: { what: 'reports' },
      search: true,
      paging: 0,
      states: [s('open', 'Open'), s('closed', 'Closed'), all],
      rowActions: [
        { label: 'Close', tool: 'admin_report', args: (r) => ({ id: r.id, state: 'closed' }), fields: [{ name: 'note', label: 'Note' }], when: (r) => r.state === 'open' },
        { label: 'Open again', tool: 'admin_report', args: (r) => ({ id: r.id, state: 'open' }), when: (r) => r.state !== 'open' },
      ],
    },
    {
      id: 'times',
      label: 'Fastest times',
      tool: 'admin_list',
      args: { what: 'times' },
      search: true,
      paging: 0,
      inputs: [{ name: 'place', label: 'Place', kind: 'select', options: [1, 2, 3, 4, 5, 6, 7].map((n) => ({ value: String(n), label: `Place ${n}` })) }],
      columns: ['nick', 'name', 'email', 'secs', 'gold', 'at', 'banned'],
      rowActions: [{ label: 'Drop time', tool: 'admin_drop_time', danger: true, args: (r) => ({ place: String(r.place).replace(/^made:/, ''), uid: r.uid }) }],
    },
  ],
};

const queueKinds = ['report', 'made', 'post_waiting', 'transfer', 'dispute', 'payouts', 'claude_hold', 'storage'];

const mahj: GameCatalog = {
  id: 'mahj',
  name: 'Bams & Brags',
  views: [
    {
      id: 'queue',
      label: 'Waiting',
      tool: 'admin_queue',
      search: true,
      paging: 0,
      states: [all, ...queueKinds.map((k) => s(k, k.replace('_', ' '), { kind: k }))],
      columns: ['kind', 'age', 'summary', 'who', 'context', 'resolve_with'],
      rowActions: [
        { label: 'Close report', tool: 'admin_report', args: (r) => ({ id: Number(String(r.id).split(':')[1]), state: 'closed' }), fields: [reason], when: (r) => r.kind === 'report' },
        { label: 'Approve', tool: 'admin_review', args: (r) => ({ id: String(r.id).split(':')[1], approve: true }), fields: [reason], when: (r) => r.kind === 'made' },
        { label: 'Decline', tool: 'admin_review', args: (r) => ({ id: String(r.id).split(':')[1], approve: false }), fields: [reason], when: (r) => r.kind === 'made' },
        { label: 'Send again', tool: 'admin_transfer', args: (r) => ({ reg: String(r.id).split(':')[1] }), fields: [reason], when: (r) => r.kind === 'transfer' },
      ],
    },
    { id: 'overview', label: 'Overview', tool: 'admin_overview' },
    {
      id: 'live',
      label: 'Live',
      tool: 'admin_live',
      list: 'tables',
      columns: ['name', 'place', 'open', 'started', 'hand', 'people'],
      rowActions: [{ label: 'Close table', tool: 'admin_close', danger: true, preview: true, args: (r) => ({ what: 'table', id: r.id }), fields: [reason] }],
      tabActions: [
        {
          label: 'Close a tournament',
          tool: 'admin_close',
          danger: true,
          preview: true,
          args: () => ({ what: 'tournament' }),
          fields: [{ name: 'id', label: 'Tournament id', required: true }, reason],
        },
      ],
    },
    {
      id: 'players',
      label: 'Players',
      tool: 'admin_list',
      args: { what: 'players' },
      search: true,
      paging: 0,
      states: [all, s('accounts', 'Accounts'), s('banned', 'Banned')],
      columns: ['name', 'email', 'country', 'city', 'hands', 'pass', 'reported', 'banned', 'updated'],
      open: { tool: 'admin_player', args: (r) => ({ uid: r.id }) },
      rowActions: [
        { label: 'Ban', tool: 'admin_ban', danger: true, preview: true, args: (r) => ({ uid: r.id }), fields: [reason], when: (r) => !r.banned },
        { label: 'Lift ban', tool: 'admin_ban', args: (r) => ({ uid: r.id, lift: true }), fields: [reason], when: (r) => Boolean(r.banned) },
        { label: 'Give pass', tool: 'admin_pass', args: (r) => ({ uid: r.id }), fields: [reason], when: (r) => !r.pass },
        { label: 'Take pass', tool: 'admin_pass', danger: true, args: (r) => ({ uid: r.id, take: true }), fields: [reason], when: (r) => Boolean(r.pass) },
      ],
    },
    {
      id: 'reports',
      label: 'Reports',
      tool: 'admin_list',
      args: { what: 'reports' },
      search: true,
      paging: 0,
      states: [s('open', 'Open'), s('closed', 'Closed'), all],
      columns: ['id', 'at', 'state', 'of_name', 'by_name', 'why', 'text', 'tbl'],
      rowActions: [
        { label: 'Close', tool: 'admin_report', args: (r) => ({ id: r.id, state: 'closed' }), fields: [reason], when: (r) => r.state === 'open' },
        { label: 'Open again', tool: 'admin_report', args: (r) => ({ id: r.id, state: 'open' }), fields: [reason], when: (r) => r.state !== 'open' },
      ],
    },
    {
      id: 'looks',
      label: 'Looks',
      tool: 'admin_list',
      args: { what: 'made' },
      search: true,
      paging: 0,
      states: [s('pending', 'To review'), s('public', 'Public'), s('declined', 'Declined'), s('hidden', 'Hidden'), all],
      columns: ['kind', 'name', 'by_name', 'status', 'note', 'created'],
      rowActions: [
        { label: 'Approve', tool: 'admin_review', args: (r) => ({ id: r.id, approve: true }), fields: [reason], when: (r) => r.status === 'pending' },
        { label: 'Decline', tool: 'admin_review', args: (r) => ({ id: r.id, approve: false }), fields: [reason], when: (r) => r.status === 'pending' },
        { label: 'Hide', tool: 'admin_hide', danger: true, preview: true, args: (r) => ({ what: 'made', id: r.id }), fields: [reason], when: (r) => r.status !== 'hidden' },
        { label: 'Show', tool: 'admin_hide', args: (r) => ({ what: 'made', id: r.id, show: true }), fields: [reason], when: (r) => r.status === 'hidden' },
      ],
    },
    {
      id: 'leagues',
      label: 'Leagues',
      tool: 'admin_list',
      args: { what: 'leagues' },
      search: true,
      paging: 0,
      states: [all, s('paid', 'Paid'), s('hidden', 'Hidden')],
      open: { tool: 'admin_league', args: (r) => ({ id: r.id ?? r.slug }) },
      rowActions: [
        { label: 'Hide', tool: 'admin_hide', danger: true, preview: true, args: (r) => ({ what: 'league', id: r.id ?? r.slug }), fields: [reason], when: (r) => !r.hidden },
        { label: 'Show', tool: 'admin_hide', args: (r) => ({ what: 'league', id: r.id ?? r.slug, show: true }), fields: [reason], when: (r) => Boolean(r.hidden) },
        { label: 'Pause paid sign-ups', tool: 'admin_registrations', danger: true, args: (r) => ({ league: r.id ?? r.slug, pause: true }), fields: [reason] },
        { label: 'Resume paid sign-ups', tool: 'admin_registrations', args: (r) => ({ league: r.id ?? r.slug, pause: false }), fields: [reason] },
        {
          label: 'Fix Claude balance',
          tool: 'admin_balance',
          args: (r) => ({ id: r.id ?? r.slug }),
          fields: [{ name: 'dollars', label: 'Dollars', kind: 'number', required: true, hint: 'Minus to take off. 500 at most. Moves no money.' }, reason],
        },
      ],
    },
    {
      id: 'events',
      label: 'Events',
      tool: 'admin_list',
      args: { what: 'events' },
      search: true,
      paging: 0,
      states: [all, ...['draft', 'published', 'live', 'finished', 'cancelled', 'hidden'].map((v) => s(v, v[0]!.toUpperCase() + v.slice(1)))],
      open: { tool: 'admin_event', args: (r) => ({ id: r.id }) },
      rowActions: [
        { label: 'Hide', tool: 'admin_hide', danger: true, preview: true, args: (r) => ({ what: 'event', id: r.id }), fields: [reason], when: (r) => !r.hidden },
        { label: 'Show', tool: 'admin_hide', args: (r) => ({ what: 'event', id: r.id, show: true }), fields: [reason], when: (r) => Boolean(r.hidden) },
      ],
      tabActions: [
        {
          label: 'Strike out a hand',
          tool: 'admin_score',
          danger: true,
          fields: [{ name: 'event', label: 'Event id', required: true }, { name: 'hand', label: 'Hand id', required: true, hint: 'From the event’s day.' }, reason],
        },
        {
          label: 'End a board or door',
          tool: 'admin_revoke',
          danger: true,
          fields: [
            { name: 'what', label: 'Which', kind: 'select', required: true, options: [{ value: 'board', label: 'A board’s view code' }, { value: 'door', label: 'A door’s session' }] },
            { name: 'event', label: 'Event id', required: true },
            { name: 'id', label: 'Its id', required: true, hint: 'From the event’s sessions.' },
            reason,
          ],
        },
      ],
    },
    {
      id: 'posts',
      label: 'Posts',
      tool: 'admin_list',
      args: { what: 'posts' },
      search: true,
      paging: 0,
      states: [all, s('shown', 'Shown'), s('waiting', 'Waiting'), s('hidden', 'Hidden'), s('photos', 'Photos')],
      rowActions: [
        { label: 'Hide', tool: 'admin_hide', danger: true, preview: true, args: (r) => ({ what: r.photo ? 'photo' : 'post', id: r.id }), fields: [reason], when: (r) => r.state !== 'hidden' },
        { label: 'Show', tool: 'admin_hide', args: (r) => ({ what: r.photo ? 'photo' : 'post', id: r.id, show: true }), fields: [reason], when: (r) => r.state === 'hidden' },
      ],
    },
    { id: 'money', label: 'Money', tool: 'admin_money', args: { what: 'summary' } },
    {
      id: 'transfers',
      label: 'Transfers',
      tool: 'admin_list',
      args: { what: 'transfers' },
      search: true,
      paging: 0,
      states: [all, s('failed', 'Failed'), s('due', 'Due'), s('paid', 'Paid'), s('disputed', 'Disputed')],
      rowActions: [
        { label: 'Send again', tool: 'admin_transfer', args: (r) => ({ reg: r.id ?? r.reg }), fields: [reason], when: (r) => r.state !== 'paid' && r.xfer !== 'paid' },
        { label: 'Check dispute', tool: 'admin_transfer', args: (r) => ({ reg: r.id ?? r.reg, check_dispute: true }), fields: [reason] },
      ],
    },
    { id: 'claude', label: 'Claude', tool: 'admin_claude', search: true, paging: 0 },
    { id: 'audit', label: 'Record', tool: 'admin_audit', search: true, paging: 0 },
    { id: 'guide', label: 'Guide', tool: 'admin_guide' },
  ],
};

const carol: GameCatalog = {
  id: 'carol',
  name: 'Send a Carol',
  views: [
    { id: 'overview', label: 'Overview', tool: 'admin_overview', args: { days: 30 } },
    {
      id: 'carols',
      label: 'Carols',
      tool: 'admin_cards',
      search: true,
      paging: 1,
      states: [all, s('draft', 'Draft'), s('ready', 'Ready'), s('down', 'Down'), s('deleted', 'Deleted')],
      columns: ['card_name', 'title', 'state', 'occasion', 'paid', 'opens', 'maker', 'updated'],
      open: { tool: 'admin_card', args: (r) => ({ id: r.id }) },
      rowActions: [
        { label: 'Take down', tool: 'admin_take_down', danger: true, args: (r) => ({ id: r.id }), fields: [reason], when: (r) => r.state === 'ready' },
        { label: 'Put back', tool: 'admin_take_down', args: (r) => ({ id: r.id, restore: true }), fields: [reason], when: (r) => r.state === 'down' },
        { label: 'Delete for good', tool: 'admin_delete_media', danger: true, preview: true, args: (r) => ({ id: r.id }), fields: [reason], when: (r) => r.state !== 'deleted' },
      ],
    },
    {
      id: 'accounts',
      label: 'Accounts',
      tool: 'admin_accounts',
      search: true,
      paging: 1,
      states: [all, s('paid', 'Paid', { paid: true }), s('banned', 'Banned', { banned: true })],
      rowActions: [
        {
          label: 'Credits',
          tool: 'admin_grant',
          args: (r) => ({ uid: r.id ?? r.uid }),
          fields: [{ name: 'credits', label: 'Credits', kind: 'number', required: true, hint: '1 to 50, or minus to take unused ones away.' }, reason],
        },
        { label: 'Ban', tool: 'admin_ban', danger: true, args: (r) => ({ uid: r.id ?? r.uid }), fields: [reason], when: (r) => !r.banned },
        { label: 'Lift ban', tool: 'admin_ban', args: (r) => ({ uid: r.id ?? r.uid, lift: true }), fields: [reason], when: (r) => Boolean(r.banned) },
      ],
    },
    {
      id: 'reports',
      label: 'Reports',
      tool: 'admin_reports',
      search: true,
      paging: 1,
      states: [s('open', 'Open'), s('done', 'Done'), s('all', 'All')],
      rowActions: [{ label: 'Close', tool: 'admin_report', args: (r) => ({ id: r.id }), fields: [{ ...reason, label: 'What was done' }], when: (r) => r.state === 'open' }],
    },
    {
      id: 'jobs',
      label: 'Jobs',
      tool: 'admin_jobs',
      search: true,
      paging: 1,
      states: [all, s('failed', 'Failed'), s('stuck', 'Stuck', { stuck: true }), s('queued', 'Queued'), s('running', 'Running'), s('done', 'Done')],
      rowActions: [{ label: 'Retry', tool: 'admin_retry_job', args: (r) => ({ id: r.id }), fields: [reason], when: (r) => r.state !== 'done' }],
    },
    {
      id: 'templates',
      label: 'Templates',
      tool: 'admin_templates',
      search: true,
      paging: 1,
      states: [all, s('on', 'On', { off: false }), s('off', 'Off', { off: true })],
      rowActions: [
        { label: 'Switch off', tool: 'admin_template', args: (r) => ({ id: r.id, off: true }), fields: [reason], when: (r) => !r.off },
        { label: 'Switch on', tool: 'admin_template', args: (r) => ({ id: r.id, off: false }), fields: [reason], when: (r) => Boolean(r.off) },
        { label: 'Order', tool: 'admin_template', args: (r) => ({ id: r.id }), fields: [{ name: 'order', label: 'Place in the order', kind: 'number', required: true, hint: 'Lower comes first.' }, reason] },
      ],
    },
    {
      id: 'occasions',
      label: 'Occasions',
      tool: 'admin_occasions',
      rowActions: [
        {
          label: 'Change',
          tool: 'admin_occasion',
          args: (r) => ({ id: r.id }),
          fields: [
            { name: 'state', label: 'State', kind: 'select', options: [{ value: '', label: 'As it is' }, { value: 'live', label: 'Live' }, { value: 'soon', label: 'Soon' }, { value: 'off', label: 'Off' }] },
            { name: 'from', label: 'Featured from', hint: 'MM-DD' },
            { name: 'to', label: 'Featured to', hint: 'MM-DD' },
            { name: 'clear', label: 'Not featured', kind: 'check' },
            reason,
          ],
        },
      ],
    },
    {
      id: 'limits',
      label: 'Prices and limits',
      tool: 'admin_prices',
      tabActions: [
        {
          label: 'Change a limit',
          tool: 'admin_limit',
          fields: [
            { name: 'name', label: 'Limit', required: true, hint: 'Like takesPerCarol, freeDrafts, emailsPerDay.' },
            { name: 'value', label: 'Value', kind: 'number' },
            { name: 'reset', label: 'Back to the default', kind: 'check' },
            reason,
          ],
        },
      ],
    },
    { id: 'audit', label: 'Record', tool: 'admin_audit', search: true, paging: 1 },
  ],
};

export const catalogs: readonly GameCatalog[] = [frank, crabby, mahj, carol];

export const catalogOf = (id: string | undefined) => catalogs.find((c) => c.id === id);
