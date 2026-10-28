// The voice game: learn the visitor's voice from three set phrases, then read each take for truth, a lie, stress or
// anger, as likelihoods. Measuring happens here (measure.js); /api/voice (the platform's server/voice.ts) asks Ada.
// Kept in this browser only: the name, Ada's ids for the visitor's takes, and the numbers of their true takes.

import { against, listen, usual } from './measure.js';

const SETS = [
  { phrase: 'self', what: 'Who you are', say: (name) => `My name is ${name}. This is my voice, it is my voice alone.` },
  { phrase: 'truth', what: 'Something true', say: () => 'I am sitting in front of a screen right now.' },
  { phrase: 'lie', what: 'Something false, said as if it were true', say: () => 'I have walked on the moon.' },
];
const PROMPTS = [
  'I have never cheated at a board game.',
  'I always reply to messages the same day.',
  'I read the terms and conditions before I agree.',
  'I did not eat the last biscuit.',
  'I love my job.',
];
const MOODS = { truth: 'Truth', lie: 'Lie', stressed: 'Stressed', angry: 'Angry' };
const KEPT = 'glyphh_voice';
const MAX_SECONDS = 10;
const TRUE_KEPT = 20;

const $ = (id) => document.getElementById(id);
const pct = (p) => `${Math.round(p * 100)}%`;
const words = (s) => s.split(/\s+/).filter(Boolean).length;
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

let me = load(); // { name, ids, truths } once enrolled
let enrolled = [];
let prompt = 0; // index into PROMPTS, or -1 for anything
let last = null; // the take Ada just read: { raw, take }
let busy = false;

function load() {
  try {
    const v = JSON.parse(localStorage.getItem(KEPT) || 'null');
    return v && typeof v.name === 'string' && Array.isArray(v.ids) && Array.isArray(v.truths) ? v : null;
  } catch {
    return null;
  }
}
const save = () => localStorage.setItem(KEPT, JSON.stringify(me));

async function api(path, body) {
  const res = await fetch(`/api/voice/${path}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.error || `The demo server answered ${res.status}.`);
  return json;
}

function showError(message) {
  $('error').hidden = !message;
  $('error').textContent = message || '';
}

function show(id) {
  for (const s of ['start', 'enrol', 'game']) $(s).hidden = s !== id;
  $('who').textContent = me ? `Listening to ${me.name}` : '';
  $('forget').hidden = !me?.ids.length;
}

/** Records one take with the given button; resolves to its numbers, or null when nothing clear was heard. */
function record(button, level) {
  return new Promise((resolve, reject) => {
    let mic = null;
    let timer = null;
    const label = button.textContent;
    const finish = async () => {
      clearTimeout(timer);
      button.onclick = null;
      button.textContent = 'Measuring…';
      button.disabled = true;
      try {
        resolve(await mic.stop());
      } catch (e) {
        reject(e);
      } finally {
        level.style.width = '0';
        button.textContent = label;
        button.disabled = false;
        button.classList.remove('live');
      }
    };
    listen((v) => (level.style.width = `${Math.min(100, v * 600)}%`))
      .then((m) => {
        mic = m;
        button.textContent = 'Stop';
        button.classList.add('live');
        button.onclick = finish;
        timer = setTimeout(finish, MAX_SECONDS * 1000);
      })
      .catch(() => reject(new Error('The page needs your microphone. Allow it in the browser and try again.')));
  });
}

const NOT_HEARD = 'Ada could not hear enough of that. Speak the whole phrase, a little closer to the microphone.';

/* Enrolling: the three set phrases */

function showStep() {
  const step = SETS[enrolled.length];
  $('enrol-step').textContent = `Phrase ${enrolled.length + 1} of 3`;
  $('enrol-what').textContent = step.what;
  $('enrol-phrase').textContent = step.say(me.name);
  show('enrol');
}

$('start-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const name = $('name').value.trim().replace(/\s+/g, ' ');
  if (!name || !$('consent').checked) return;
  me = { name, ids: [], truths: [] };
  enrolled = [];
  showError('');
  showStep();
});

$('enrol-rec').addEventListener('click', async () => {
  if (busy) return;
  busy = true;
  showError('');
  try {
    const step = SETS[enrolled.length];
    const raw = await record($('enrol-rec'), $('enrol-level'));
    if (!raw) throw new Error(NOT_HEARD);
    enrolled.push({ phrase: step.phrase, raw: { ...raw, perWord: raw.seconds / words(step.say(me.name)) } });
    if (enrolled.length < 3) return showStep();
    const truths = enrolled.filter((t) => t.phrase !== 'lie').map((t) => t.raw);
    const base = usual(truths);
    const { ids } = await api('enrol', { takes: enrolled.map((t) => ({ phrase: t.phrase, measures: against(t.raw, base) })) });
    me = { name: me.name, ids, truths };
    save();
    startGame();
  } catch (err) {
    showError(err.message);
  } finally {
    busy = false;
  }
});

/* The game */

function startGame() {
  renderPrompts();
  renderTakes();
  show('game');
}

function renderTakes() {
  $('takes').textContent = `${me.ids.length} takes known · ${me.truths.length} true`;
}

function renderPrompts() {
  $('prompts').innerHTML = [...PROMPTS.map((p, i) => [i, p.replace(/\.$/, '')]), [-1, 'Say anything']]
    .map(([i, label]) => `<button type="button" class="chip ${i === prompt ? 'on' : ''}" data-i="${i}">${esc(label)}</button>`)
    .join('');
  $('phrase').textContent = prompt >= 0 ? PROMPTS[prompt] : 'Anything you like, a sentence or two.';
}

$('prompts').addEventListener('click', (e) => {
  const b = e.target.closest('button[data-i]');
  if (!b) return;
  prompt = Number(b.dataset.i);
  renderPrompts();
});

$('rec').addEventListener('click', async () => {
  if (busy) return;
  busy = true;
  showError('');
  try {
    const raw = await record($('rec'), $('level'));
    if (!raw) throw new Error(NOT_HEARD);
    if (prompt >= 0) raw.perWord = raw.seconds / words(PROMPTS[prompt]);
    // A game prompt is neither the enrolment's truth nor its lie: Ada reads it as said freely, its length known.
    const take = { phrase: 'free', measures: against(raw, usual(me.truths)) };
    const answer = await api('read', { take });
    last = { raw, take };
    renderAnswer(answer);
  } catch (err) {
    showError(err.message);
  } finally {
    busy = false;
  }
});

function renderAnswer(a) {
  const ranked = Object.entries(a.probabilities).sort((x, y) => y[1] - x[1]);
  const [top, p] = ranked[0];
  $('ms').innerHTML = `${a.ms} ms <i>Ada Cloud</i>`;
  $('answer').innerHTML = `
    <p class="verdict ${a.ask ? 'ask' : top}">${a.ask ? 'Ada cannot tell' : `Sounds like <b>${MOODS[top].toLowerCase()}</b>`}</p>
    <div class="bars">${ranked
      .map(([m, v]) => `<div class="bar ${m}"><span>${MOODS[m]}</span><div><i style="width:${Math.round(v * 100)}%"></i></div><b>${pct(v)}</b></div>`)
      .join('')}</div>
    <p class="sub">${a.ask ? `Nothing above ${pct(0.6)}: your take sits between moods she knows.` : `${pct(p)} likely, from the ${a.receipts.length === 1 ? 'take' : `${a.receipts.length} takes`} it sounds closest to.`}</p>`;
  $('moods').innerHTML = Object.entries(MOODS).map(([m, label]) => `<button type="button" class="chip mood ${m}" data-m="${m}">${label}</button>`).join('');
  $('teach').hidden = false;
}

$('moods').addEventListener('click', async (e) => {
  const b = e.target.closest('button[data-m]');
  if (!b || busy || !last) return;
  busy = true;
  showError('');
  try {
    const mood = b.dataset.m;
    const { id } = await api('teach', { take: last.take, mood });
    me.ids.push(id);
    if (mood === 'truth') me.truths = [...me.truths, last.raw].slice(-TRUE_KEPT);
    save();
    last = null;
    $('teach').hidden = true;
    $('answer').innerHTML = `<p class="empty-big">Thanks. Ada knows your voice a little better.</p><p class="sub">Say another.</p>`;
    renderTakes();
  } catch (err) {
    showError(err.message);
  } finally {
    busy = false;
  }
});

$('forget').addEventListener('click', async () => {
  if (busy || !me) return;
  if (!confirm(`Forget ${me.name}? Ada deletes every take of yours and this browser forgets your name.`)) return;
  busy = true;
  showError('');
  try {
    await api('forget', { ids: me.ids });
    localStorage.removeItem(KEPT);
    me = null;
    $('name').value = '';
    $('consent').checked = false;
    show('start');
  } catch (err) {
    showError(err.message);
  } finally {
    busy = false;
  }
});

if (me) startGame();
else show('start');
