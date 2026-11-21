// The demos on demo.glyphh.ai's front page, one entry each. A new demo adds its entry here; `soon` shows the card
// without a link until the demo is live.
export const DEMOS = [
  {
    href: '/bot/',
    title: 'Teach a bot',
    blurb: 'Make up a rule and keep it to yourself. A bot asks you about 40 expenses, Ada learns your rule from the answers, and the bot starts deciding alone.',
    tags: ['bots', 'learning', 'approvals'],
    model: 'launch-demo-bot-*',
  },
  {
    href: '/expenses/',
    title: 'Expense approvals',
    blurb: 'Ada approves or rejects expense claims from 40 past decisions, says when she isn’t sure, and learns from one correction.',
    tags: ['finance', 'approvals', 'policy'],
    model: 'launch-demo-expenses',
  },
  {
    href: '/voice/',
    title: 'Voice check',
    blurb: 'Ada reads how you sound against how you usually sound. No audio leaves your browser, only the numbers.',
    tags: ['voice', 'game', 'audio'],
    model: 'launch-demo-voice-2',
  },
];
