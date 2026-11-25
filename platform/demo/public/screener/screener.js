// The page of the simple check: the two files are sent once to /api/screener/screen, and what the Resume Screener
// plugin's code answered is drawn: for the resume, and for the cover letter apart, how alike the nearest fake and the
// nearest real one are with the nearest few; then Ada's decision, its confidence, and Ada's fact tree for it as Ada
// gave it (each key with its weight and how alike the two are there; a leaf says what each had). The page holds no
// key and keeps nothing.

const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};
const pct = (p) => `${Math.round(100 * (p || 0))}%`;
const two = (n) => (n == null ? 'none held' : n.toFixed(2));
const said = (v) => (v == null ? 'nothing' : Array.isArray(v) ? v.join(' ') : String(v));
const KIND = { 'reads like the fakes': 'fake', 'reads like real people': 'real' };

function side(title, s) {
  const box = el('div', 'side');
  const track = el('div', 'track');
  const fill = el('div', 'fill');
  fill.style.width = pct(s.closeness);
  track.append(fill);
  const list = el('ul', 'found');
  for (const n of s.nearest || []) list.append(el('li', '', `${two(n.closeness)} · ${n.like}`));
  box.append(el('span', 'label', title), el('span', 'num', two(s.closeness)), track, list);
  return box;
}

function part(title, p) {
  const box = el('div', 'part');
  const head = el('div', 'part-head');
  head.append(el('span', 'label', title), el('span', `big ${KIND[p.reads] || ''}`, p.reads));
  const sides = el('div', 'sides');
  sides.append(side('Closest fake', p.fake), side('Closest real', p.real));
  box.append(head, sides);
  return box;
}

function node(f, depth) {
  const box = el('details', 'node');
  box.open = depth < 2;
  const head = el('summary');
  const alike = f.status && f.status !== 'both' ? (f.status === 'query_only' ? 'only this one has it' : 'only the precedent has it') : `${pct(f.score)} alike`;
  head.append(el('span', 'key', f.key || 'the whole resume'), el('span', 'sub', `${alike} · weight ${Number(f.weight ?? 0).toFixed(2)}`));
  box.append(head);
  const kids = f.children || [];
  for (const k of kids) box.append(node(k, depth + 1));
  if (!kids.length) box.append(el('div', 'leaf', `this one: ${said(f.query)}`), el('div', 'leaf', `the precedent: ${said(f.record)}`));
  return box;
}

function decision(d) {
  const box = el('div', 'part');
  const head = el('div', 'part-head');
  head.append(el('span', 'label', `Ada's decision on the ${d.on || 'resume'}`));
  const chips = el('div', 'row');
  chips.append(el('span', `chip ${d.outcome || ''}`, d.outcome ? `${d.outcome} · ${d.confidence != null ? pct(d.confidence) : 'no confidence given'}` : 'no answer'));
  if (d.ask) chips.append(el('span', 'chip unsure', 'Ada would ask a person first'));
  head.append(chips);
  box.append(head);
  for (const f of d.facts || []) {
    if (!f || !f.tree) continue;
    box.append(el('p', 'sub', `Ada's fact tree, against its nearest precedent (${f.outcome ?? 'no outcome'}):`), node(f.tree, 0));
  }
  return box;
}

function show(a) {
  $('empty').hidden = true;
  const parts = [];
  if (a.resume) parts.push(part('The resume', a.resume));
  if (a.letter) parts.push(part('The cover letter', a.letter));
  if (a.decision) parts.push(decision(a.decision));
  if (!a.resume && !a.letter) parts.push(el('p', 'hint', a.reads || 'There was nothing to read.'));
  if (a.note) parts.push(el('p', 'sub', a.note));
  for (const problem of a['could not read'] || []) parts.push(el('p', 'sub', problem));
  $('answer').replaceChildren(...parts);
  $('answer').hidden = false;
}

function fail(message) {
  $('error').textContent = message;
  $('error').hidden = !message;
}

$('form').addEventListener('submit', async (event) => {
  event.preventDefault();
  fail('');
  $('go').disabled = true;
  $('busy').hidden = false;
  try {
    const res = await fetch('/api/screener/screen', { method: 'POST', body: new FormData($('form')) });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.error || 'The screener hit a snag. Try again.');
    show(body);
  } catch (e) {
    fail(e.message);
  } finally {
    $('go').disabled = false;
    $('busy').hidden = true;
  }
});
