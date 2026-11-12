// Teach a bot: the visitor answers by a rule of their own, the bot asks less as Ada learns it. The take lives on the
// server (/api/bot, the platform's server/bot.ts); the page sends an outcome and draws what comes back.

const $ = (id) => document.getElementById(id);
const pct = (p) => `${Math.round(p * 100)}%`;
const money = (n) => `$${Number(n).toLocaleString('en-US')}`;
const cap = (s) => s.replace(/^\w/, (c) => c.toUpperCase());
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const done = (o) => (o === 'approve' ? 'Approved' : 'Rejected');

// The roles Ada weighs, as the page names them.
const ROLES = { department: 'Department', category: 'Category', amount: 'Amount', receipt: 'Receipt', policy: 'Policy check' };

let take = null;
let busy = false;

async function api(path, body) {
  const res = await fetch(`/api/bot/${path}`, body === undefined ? {} : { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.error || `The demo server answered ${res.status}.`);
  return json.take;
}

function showError(message) {
  $('error').hidden = !message;
  $('error').textContent = message || '';
}

const policyLabel = (item) =>
  item.policy === 'within limit'
    ? `Within the ${money(item.limit)} limit`
    : item.policy === 'over limit, pre-approved'
      ? `Over the ${money(item.limit)} limit, pre-approved`
      : `<span class="flag">Over the ${money(item.limit)} limit, not pre-approved</span>`;

function renderItem() {
  const { item, n, total, bot } = take;
  $('count').textContent = `Expense ${n + 1} of ${total}`;
  $('ms').textContent = bot?.ms ? `${bot.ms} ms · Ada Cloud` : '';
  $('what').textContent = item.description;
  $('facts').innerHTML = `
    <dt>Filed by</dt><dd>${esc(item.employee)}</dd>
    <dt>Department</dt><dd class="seen">${esc(cap(item.department))}</dd>
    <dt>Category</dt><dd class="seen">${esc(cap(item.category))}</dd>
    <dt>Amount</dt><dd class="seen">${money(item.amount)}</dd>
    <dt>Receipt</dt><dd class="seen">${item.receipt ? 'Attached' : '<span class="flag">Missing</span>'}</dd>
    <dt>Policy check</dt><dd class="seen">${policyLabel(item)}</dd>`;
}

const basisRows = (basis) =>
  basis.length
    ? `<div class="basis"><span class="kicker dim">Closest of your answers</span>${basis
        .map((b) => `<div class="basis-row"><span>${esc(b.item.description)} · ${money(b.item.amount)} <i>expense ${b.n + 1}</i></span><span class="pill ${b.outcome}">${done(b.outcome)}</span><i>${pct(b.sim)} alike</i></div>`)
        .join('')}</div>`
    : '';

function renderBot() {
  const { bot, counts, askFirst, bar, alike } = take;
  const answered = counts.asked + counts.alone;
  if (bot.ask) {
    $('bot-title').textContent = 'The bot asks you';
    $('bot-title').className = 'kicker ask';
    const why =
      bot.why === 'new'
        ? `It has ${answered === 0 ? 'no answers' : answered === 1 ? 'one answer' : `${answered} answers`} from you. It asks about the first ${askFirst}, whatever Ada thinks.`
        : bot.why === 'thin'
          ? `Ada says ${bot.lean} at ${pct(bot.sure)}, but she has little to stand on: the bot decides alone only when your two closest answers are each ${pct(alike)} alike or more and both agree with her.`
          : bot.lean
            ? `Ada leans ${bot.lean} at ${pct(bot.sure)}, under the ${pct(bar)} she needs before the bot decides alone.`
            : 'Ada has nothing close enough to go on.';
    $('bot').innerHTML = `
      <p class="verdict ask rise">Approve or reject?</p>
      <p class="why">${why}</p>
      ${basisRows(bot.basis)}
      <div class="row">
        <button type="button" class="primary" data-outcome="approve">Approve</button>
        <button type="button" class="outline" data-outcome="reject">Reject</button>
      </div>
      <p class="keys"><kbd>A</kbd> approve · <kbd>R</kbd> reject</p>`;
  } else {
    const other = bot.outcome === 'approve' ? 'reject' : 'approve';
    $('bot-title').textContent = 'The bot decided alone';
    $('bot-title').className = `kicker ${bot.outcome}`;
    $('bot').innerHTML = `
      <p class="verdict ${bot.outcome} rise">${done(bot.outcome)}</p>
      <p class="why">Ada is ${pct(bot.sure)} sure, from your ${answered} answers. Is that what your rule says?</p>
      ${basisRows(bot.basis)}
      <div class="row">
        <button type="button" class="primary" data-outcome="${bot.outcome}">Right</button>
        <button type="button" class="outline" data-outcome="${other}">Wrong</button>
      </div>
      <p class="keys"><kbd>Enter</kbd> right · <kbd>W</kbd> wrong</p>`;
  }
}

function renderProgress() {
  const { log, total, n, counts, weights, done: over } = take;
  const cells = Array.from({ length: total }, (_, i) => {
    const e = log[i];
    if (!e) return `<i class="cell ${i === n && !over ? 'now' : ''}"></i>`;
    return e.asked ? '<i class="cell asked">?</i>' : e.wrong ? '<i class="cell wrong">✕</i>' : '<i class="cell right">✓</i>';
  });
  $('strip').innerHTML = cells.join('');
  $('strip').setAttribute('aria-label', `Of ${log.length} expenses so far, the bot asked about ${counts.asked} and decided ${counts.alone} alone, ${counts.wrong} of them wrong.`);
  $('tally').textContent = `Asked you ${counts.asked} · decided alone ${counts.alone} · wrong ${counts.wrong}`;
  $('weights').hidden = !weights;
  if (weights) {
    $('bars').innerHTML = Object.entries(weights)
      .filter(([role]) => ROLES[role])
      .sort((a, b) => b[1] - a[1])
      .map(([role, w]) => `<div class="bar"><span>${ROLES[role]}</span><div><i style="width:${Math.round(Math.min(1, Math.max(0, w)) * 100)}%"></i></div><b>${w.toFixed(2)}</b></div>`)
      .join('');
  }
}

function renderSummary() {
  const { log, total, counts } = take;
  const half = log.slice(Math.floor(total / 2));
  const lateAsked = half.filter((e) => e.asked).length;
  const lateWrong = half.filter((e) => e.wrong).length;
  const right = counts.alone - counts.wrong;
  $('summary').innerHTML = `
    <div class="stats">
      <div class="stat"><b>${counts.asked} of ${total}</b><span>expenses the bot asked you about. A bot that does not learn asks about all ${total}.</span></div>
      <div class="stat"><b>${right} of ${counts.alone}</b><span>decisions it made alone that you called right.</span></div>
      <div class="stat"><b>${lateAsked} asked · ${lateWrong} wrong</b><span>in the last ${half.length} expenses, once it had your first ${total - half.length} answers.</span></div>
    </div>
    <p class="lede">It never saw your rule. Every decision came from your own answers, and each one named the answers it stood on.</p>`;
}

function render() {
  showError('');
  $('start').hidden = Boolean(take);
  $('game').hidden = !take || take.done;
  $('done').hidden = !take?.done;
  $('progress').hidden = !take;
  $('again').hidden = !take || take.done;
  if (!take) return;
  renderProgress();
  if (take.done) return renderSummary();
  renderItem();
  renderBot();
}

async function run(work) {
  if (busy) return;
  busy = true;
  for (const b of document.querySelectorAll('#bot button, #go, #another, #again')) b.disabled = true;
  try {
    take = await work();
    render();
  } catch (e) {
    if (!take) $('start').hidden = false;
    showError(e.message);
  } finally {
    busy = false;
    for (const b of document.querySelectorAll('#bot button, #go, #another, #again')) b.disabled = false;
  }
}

const start = () => run(() => api('start', {}));
const answer = (outcome) => run(() => api('answer', { n: take.n, outcome }));

$('go').addEventListener('click', start);
$('another').addEventListener('click', start);
$('again').addEventListener('click', () => {
  if (confirm('Start again? This bot and what it has learned are deleted.')) start();
});
$('bot').addEventListener('click', (e) => {
  const b = e.target.closest('button[data-outcome]');
  if (b) answer(b.dataset.outcome);
});
document.addEventListener('keydown', (e) => {
  if (!take || take.done || !take.bot || e.metaKey || e.ctrlKey || e.altKey || e.repeat) return;
  const key = e.key.toLowerCase();
  const { bot } = take;
  if (bot.ask && key === 'a') answer('approve');
  else if (bot.ask && key === 'r') answer('reject');
  else if (!bot.ask && key === 'enter' && !e.target.closest('button, a')) answer(bot.outcome);
  else if (!bot.ask && key === 'w') answer(bot.outcome === 'approve' ? 'reject' : 'approve');
});

run(() => api('state'));
