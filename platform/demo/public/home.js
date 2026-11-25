// demo.glyphh.ai's front page: a card per demo (demos.js), filtered by the search box.
import { DEMOS } from '/demos.js';

const esc = (s) => String(s).replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]);

export function matches(demo, query) {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const text = [demo.title, demo.blurb, ...demo.tags].join(' ').toLowerCase();
  return words.every((w) => text.includes(w));
}

function card(d) {
  const tags = d.tags.map((t) => `<span class="tag">${esc(t)}</span>`).join('');
  const inner = `
    <div class="card-top"><h2>${esc(d.title)}</h2>${d.soon ? '<span class="soon">Coming soon</span>' : '<span class="go" aria-hidden="true">→</span>'}</div>
    <p>${esc(d.blurb)}</p>
    <div class="tags">${tags}</div>`;
  return d.soon ? `<div class="card is-soon">${inner}</div>` : `<a class="card" href="${esc(d.href)}">${inner}</a>`;
}

const cards = document.getElementById('cards');
const none = document.getElementById('none');
const q = document.getElementById('q');

function render() {
  const shown = DEMOS.filter((d) => matches(d, q.value));
  cards.innerHTML = shown.map(card).join('');
  none.hidden = shown.length > 0;
}

q.addEventListener('input', render);
render();
