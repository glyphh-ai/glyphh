// The screener demo's page: the form is sent as it is (the email, the role, the two files) to /api/screener/screen,
// and the verdict the Resume Screener plugin's code answered is drawn: is this a real person first, each signal with
// what it says, who said it and what it found; the fit second; how it was written as one line. The page holds no key
// and keeps nothing: the files leave it once, in that one request.

const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};
const pct = (p) => `${Math.round(100 * p)}%`;
const KIND = { 'real person': 'fine', fine: 'fine', suspect: 'suspect', unsure: 'unsure' };
const SAID_BY = { ada: 'Ada', rule: 'a rule: Ada holds no precedent close to it', you: 'you' };

function list(into, items) {
  into.replaceChildren(...(items || []).map((x) => el('li', '', x)));
}

function signal(s) {
  const row = el('div', 'signal');
  const head = el('div', 'signal-head');
  head.append(el('span', '', s.title), el('span', `chip ${KIND[s.says] || ''}`, s.says));
  const found = el('ul', 'found');
  list(found, s.found);
  row.append(head, found);
  if (s.says !== 'not checked') {
    const by = s.by === 'ada' && s.confidence != null ? `Ada, ${pct(s.confidence)} sure` : SAID_BY[s.by] || '';
    row.append(el('p', 'sub', `Said by ${by}.`));
  }
  return row;
}

function show(v) {
  $('empty').hidden = true;
  $('verdict').hidden = false;
  $('person').textContent = v.person.verdict;
  $('person').className = `big ${KIND[v.person.verdict] || ''}`;
  $('who').textContent = v.applicant;
  $('signals').replaceChildren(...v.person.signals.map(signal));
  const fit = v.fit.outcome === 'no answer' ? 'no answer' : `${v.fit.outcome}${v.fit.confidence != null ? ` · ${pct(v.fit.confidence)}` : ''}`;
  $('fit').textContent = v.fit.ask && v.fit.outcome !== 'no answer' ? `${fit} · Ada is unsure` : fit;
  list($('fit-found'), v.fit.found);
  $('made').textContent =
    v.made.ask || v.made.outcome === 'no answer'
      ? 'How it was written: Ada is unsure.'
      : `How it was written: reads as ${v.made.outcome} generated (${pct(v.made.confidence ?? 0)}).`;
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
    if (body.refused) throw new Error(`Not screened: ${body.refused.why}.`);
    show(body);
  } catch (e) {
    fail(e.message);
  } finally {
    $('go').disabled = false;
    $('busy').hidden = true;
  }
});
