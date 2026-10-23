// The page: past decisions, the expense being asked about, and Ada's decision with the precedents it stands on.
// Every answer comes from /api (server.mjs), which asks Ada Cloud through the SDK.

const BAR = 0.75; // the spec's ask_below, in server.mjs

// The company's limits, per expense, as an expense tool applies them before anyone decides. Over the limit needs
// pre-approval; conferences always do.
const LIMITS = {
  'ground transport': 350,
  airfare: 800,
  hotel: 300,
  meals: 300,
  'office supplies': 250,
  software: 200,
  equipment: 500,
  'client gifts': 100,
  conference: 0,
};

const PRESETS = [
  {
    label: 'Uber to JFK · $62',
    claim: { employee: 'Ethan Clarke', department: 'sales', category: 'ground transport', amount: 62, receipt: true, preapproved: false, description: 'Uber to JFK from the Manhattan office' },
  },
  {
    label: 'Coffee, receipt lost · $30',
    claim: { employee: 'Grace Kim', department: 'customer success', category: 'meals', amount: 30, receipt: false, preapproved: false, description: 'Coffee and pastries for customer meeting receipt lost' },
  },
  {
    label: 'Business class to London · $2,400',
    claim: { employee: 'Sofia Alvarez', department: 'marketing', category: 'airfare', amount: 2400, receipt: true, preapproved: false, description: 'Business class to London for a conference' },
  },
];

const $ = (id) => document.getElementById(id);
const money = (n) => `$${Number(n).toLocaleString('en-US')}`;
const pct = (p) => `${Math.round(p * 100)}%`;
const cap = (s) => s.replace(/\b\w/g, (c) => c.toUpperCase());
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const policyOf = (c) => (Number(c.amount) <= LIMITS[c.category] ? 'within limit' : c.preapproved ? 'over limit, pre-approved' : 'over limit, not pre-approved');
const keyOf = (c) => [c.department, c.category, Number(c.amount), c.receipt, policyOf(c), c.description.trim().toLowerCase()].join('|');

let ledger = [];
let claim = { ...PRESETS[0].claim };
let answer = null;
let asked = {}; // claim key → Ada's answers since the last decision recorded for it
let busy = false;

async function api(path, body) {
  const res = await fetch(`/api/${path}`, body === undefined ? {} : { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.error || `The demo server answered ${res.status}.`);
  return json;
}

function showError(message) {
  $('error').hidden = !message;
  $('error').textContent = message || '';
}

function setStatus(text, busyNow = false) {
  $('status').textContent = text;
  $('dot').classList.toggle('busy', busyNow);
}

/* Past decisions */

function renderLedger(lit = new Set()) {
  $('ledger-count').textContent = `${ledger.length} on record`;
  $('ledger').innerHTML = ledger
    .slice()
    .reverse()
    .map((r) => `
      <tr class="${lit.has(r.id) ? 'lit' : ''} ${r.added ? 'added' : ''}" data-id="${r.id}">
        <td class="ref">${r.ref}<i>${r.date}</i></td>
        <td class="what"><b>${esc(r.description)}</b><i>${esc(r.employee)} · ${cap(r.department)} · ${cap(r.category)}</i></td>
        <td class="n">${money(r.amount)}</td>
        <td>${r.receipt ? 'Yes' : '<span class="flag">Missing</span>'}</td>
        <td class="pol">${policyLabel(r.policy)}</td>
        <td><span class="pill ${r.outcome}">${r.outcome === 'approve' ? 'Approved' : 'Rejected'}</span></td>
      </tr>`)
    .join('');
  const first = [...lit][0];
  if (first) document.querySelector(`tr[data-id="${first}"]`)?.scrollIntoView({ block: 'center', behavior: 'smooth' });
}

const policyLabel = (p) =>
  p === 'within limit' ? '<span class="ok">Within limit</span>' : p === 'over limit, pre-approved' ? '<span class="ok">Over · pre-approved</span>' : '<span class="flag">Over · not pre-approved</span>';

/* The expense being asked about */

function renderPresets() {
  $('presets').innerHTML = PRESETS.map((p, i) => `<button type="button" class="chip ${keyOf(p.claim) === keyOf(claim) ? 'on' : ''}" data-i="${i}">${p.label}</button>`).join('');
}

function renderForm() {
  $('category').innerHTML = Object.keys(LIMITS).map((c) => `<option value="${c}">${cap(c)}</option>`).join('');
  fill();
}

function fill() {
  $('employee').value = claim.employee;
  $('department').value = claim.department;
  $('category').value = claim.category;
  $('description').value = claim.description;
  $('amount').value = claim.amount;
  for (const seg of document.querySelectorAll('.seg')) {
    const on = claim[seg.dataset.for] ? 'yes' : 'no';
    for (const b of seg.children) b.classList.toggle('on', b.dataset.v === on);
  }
  renderPolicy();
  renderPresets();
}

function renderPolicy() {
  const limit = LIMITS[claim.category];
  const p = policyOf(claim);
  const rule = limit === 0 ? `${cap(claim.category)} always needs pre-approval` : `${cap(claim.category)} up to ${money(limit)}`;
  $('policy').innerHTML = `<span class="kicker dim">Policy check</span><span class="${p === 'over limit, not pre-approved' ? 'flag' : 'ok'}">${cap(p)}</span><i>${rule}${claim.receipt ? '' : ' · no receipt attached'}</i>`;
}

function read() {
  claim = {
    ...claim,
    employee: $('employee').value.trim(),
    department: $('department').value,
    category: $('category').value,
    description: $('description').value.trim(),
    amount: Number($('amount').value),
  };
}

/* Ada's decision */

function renderAnswer() {
  if (!answer) return;
  const sure = Math.max(...Object.values(answer.probabilities));
  const verdict = answer.ask ? 'ask' : answer.outcome;
  const byId = Object.fromEntries(ledger.map((r) => [r.id, r]));
  const basis = answer.receipts.filter((r) => byId[r.id]).slice(0, 3);
  const history = asked[answer.key] || [];
  const steady = history.length > 1 && history.every((v) => v === history[0]);
  $('ms').innerHTML = `${answer.ms} ms <i>Ada Cloud, round trip</i>`;

  $('answer').innerHTML = `
    <div class="verdict-wrap">
      <p class="verdict ${verdict}">${verdict === 'ask' ? 'Not sure.' : verdict === 'approve' ? 'Approve.' : 'Reject.'}</p>
      <p class="why">${
        verdict === 'ask'
          ? `Leaning ${answer.outcome}, ${pct(sure)} sure. That’s under her ${pct(BAR)} bar, so a person decides.`
          : `${pct(sure)} sure, from ${ledger.length} decisions on record.`
      }</p>
      <div class="meter"><span class="fill ${verdict}" style="width:${Math.round(sure * 100)}%"></span><span class="tick" style="left:${BAR * 100}%"></span></div>
      ${steady ? `<p class="steady">Asked ${history.length}× · the same answer every time</p>` : ''}
      ${basis.length ? `
        <div class="basis">
          <span class="kicker dim">Based on</span>
          ${basis.map((r) => {
            const row = byId[r.id];
            return `<div class="basis-row">
              <span class="ref">${row.ref}</span>
              <span class="what"><b>${esc(row.description)}</b><i>${money(row.amount)} · ${row.receipt ? 'receipt' : 'no receipt'} · ${policyLabel(row.policy)}</i></span>
              <span class="pill ${row.outcome}">${row.outcome === 'approve' ? 'Approved' : 'Rejected'}</span>
              <span class="sim">${pct(r.sim)} alike</span>
            </div>`;
          }).join('')}
        </div>` : ''}
      ${verdict === 'ask' && !answer.recorded ? `
        <div class="decide">
          <span class="kicker pink">You decide</span>
          <div class="decide-row">
            <button type="button" class="outline" data-decide="approve">Approve it</button>
            <button type="button" class="outline" data-decide="reject">Reject it</button>
          </div>
        </div>` : ''}
      ${answer.recorded ? `<p class="recorded">Recorded as ${answer.recorded.ref}, ${answer.recorded.outcome === 'approve' ? 'approved' : 'rejected'}. Ada uses it from the next question. <button type="button" class="link" data-again>Ask again</button></p>` : ''}
    </div>`;
  renderLedger(new Set(basis.map((r) => r.id)));
}

async function ask() {
  if (busy) return;
  read();
  showError('');
  busy = true;
  $('ask').disabled = true;
  $('ask').textContent = 'Asking Ada…';
  try {
    const d = await api('decide', { claim: { ...claim, policy: policyOf(claim) } });
    const key = keyOf(claim);
    asked[key] = [...(asked[key] || []), d.ask ? 'ask' : d.outcome];
    answer = { ...d, key, claim: { ...claim } };
    renderAnswer();
  } catch (e) {
    showError(e.message);
  } finally {
    busy = false;
    $('ask').disabled = false;
    $('ask').textContent = 'Ask Ada';
  }
}

async function decide(outcome) {
  showError('');
  try {
    const row = await api('record', { claim: { ...answer.claim, policy: policyOf(answer.claim) }, outcome });
    ledger.push(row);
    asked[answer.key] = []; // a new precedent: earlier answers about this expense don't count toward "the same every time"
    answer = { ...answer, recorded: row };
    renderAnswer();
    setStatus(`${ledger.length} decisions in ${model}`);
  } catch (e) {
    showError(e.message);
  }
}

/* Wiring */

let model = '';

async function load(path) {
  setStatus(path === 'reset' ? 'Resetting the demo…' : 'Connecting to Ada Cloud…', true);
  try {
    const state = path === 'reset' ? await api('reset', {}) : await api('state');
    ledger = state.ledger;
    model = state.model;
    answer = null;
    asked = {};
    $('ms').textContent = '';
    $('answer').innerHTML = `<div class="empty"><p class="empty-big">Ask about an expense.</p><p>Ada answers from the decisions on the left, says how sure she is, and shows you which ones.</p></div>`;
    renderLedger();
    setStatus(`${ledger.length} decisions in ${model}`);
  } catch (e) {
    setStatus('Ada Cloud is not reachable');
    showError(e.message);
  }
}

$('presets').addEventListener('click', (e) => {
  const b = e.target.closest('[data-i]');
  if (!b) return;
  claim = { ...PRESETS[Number(b.dataset.i)].claim };
  fill();
});
for (const seg of document.querySelectorAll('.seg')) {
  seg.addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    claim[seg.dataset.for] = b.dataset.v === 'yes';
    fill();
  });
}
for (const id of ['employee', 'department', 'category', 'description', 'amount']) {
  $(id).addEventListener('input', () => {
    read();
    renderPolicy();
    renderPresets();
  });
}
$('form').addEventListener('submit', (e) => {
  e.preventDefault();
  ask();
});
$('answer').addEventListener('click', (e) => {
  const d = e.target.closest('[data-decide]');
  if (d) decide(d.dataset.decide);
  if (e.target.closest('[data-again]')) {
    claim = { ...answer.claim };
    fill();
    ask();
  }
});
$('reset').addEventListener('click', () => load('reset'));

renderForm();
load('state');
