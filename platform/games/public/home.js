// games.glyphh.ai's front page: a card per game (games.js).
import { GAMES } from '/games.js';

const esc = (s) => String(s).replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]);

function card(g) {
  const tags = g.tags.map((t) => `<span class="tag">${esc(t)}</span>`).join('');
  const art = g.art ? `<img class="card-art" src="${esc(g.art)}" alt="">` : '<div class="card-art empty">Coming soon</div>';
  const inner = `${art}
    <div class="card-body">
      <div class="card-top"><h2>${esc(g.title)}</h2>${g.soon ? '<span class="soon">Coming soon</span>' : '<span class="go" aria-hidden="true">→</span>'}</div>
      <p>${esc(g.blurb)}</p>
      ${tags ? `<div class="tags">${tags}</div>` : ''}
    </div>`;
  return g.soon ? `<div class="card is-soon">${inner}</div>` : `<a class="card" href="${esc(g.href)}">${inner}</a>`;
}

document.getElementById('cards').innerHTML = GAMES.map(card).join('');
