// Crew settings: the one modal for how the crew works. Which bots are in it, where it runs, how turns are taken, how
// its pull requests are reviewed, whether a watched run is read aloud, and its safety caps. Nothing else of the crew
// is set anywhere but the ticks on its card and the three pills under the composer.
import { useState } from 'react';
import { useBotPlaces, type Bot } from '@/api/bots';
import type { Review, TurnMode } from '@/api/projects';
import { BotCat, CLOUD_NOTE, Modal } from './bits';
import { CREW_MAX, type Crew } from './crew';

const TURNS: ReadonlyArray<{ value: TurnMode; label: string; hint: string }> = [
  { value: 'wait', label: 'Wait your turn', hint: 'One bot at a time. The next free bot with something to do goes.' },
  { value: 'orchestrator', label: 'An orchestrator picks', hint: 'It reads the work so far, names the next bot and says why.' },
];
export const REVIEWS: ReadonlyArray<{ value: Review; label: string; hint: string }> = [
  { value: 'each_turn', label: 'Each turn', hint: 'Every pull request waits for your merge or reject.' },
  { value: 'end', label: 'At the end', hint: 'The turns add up to one pull request, which waits for you at the end.' },
];

export function CrewSettings({ crew, bots, onClose }: { crew: Crew; bots: Bot[]; onClose: () => void }) {
  const places = useBotPlaces();
  const [members, setMembers] = useState<string[]>(crew.members);
  const [runsOn, setRunsOn] = useState(crew.settings.runs_on);
  const [mode, setMode] = useState(crew.settings.turn_mode);
  const [orchestrator, setOrchestrator] = useState(crew.settings.orchestrator);
  const [review, setReview] = useState(crew.settings.review);
  const [narrate, setNarrate] = useState(crew.settings.narrate);
  const [turns, setTurns] = useState(String(crew.settings.max_turns));
  const [spend, setSpend] = useState(crew.settings.max_spend_cents == null ? '' : (crew.settings.max_spend_cents / 100).toFixed(2));

  const everywhere = places.data ?? [{ id: null, name: 'Glyphh cloud', mode: 'cloud' as const, linked: true }];
  const toggle = (id: string) => {
    const next = members.includes(id) ? members.filter((x) => x !== id) : [...members, id];
    if (next.length > CREW_MAX) return;
    setMembers(next);
    if (orchestrator && !next.includes(orchestrator)) setOrchestrator(null);
  };
  const maxTurns = Number(turns);
  const cents = spend.trim() === '' ? null : Math.round(Number(spend) * 100);
  const capsOk = Number.isInteger(maxTurns) && maxTurns >= 1 && maxTurns <= 200 && (cents === null || (Number.isFinite(cents) && cents > 0));
  const ready = members.length > 0 && capsOk;
  const save = () =>
    crew.save(
      {
        // A set: sent in the bots' own order, whatever order the cats were clicked in.
        members: bots.map((b) => b.id).filter((id) => members.includes(id)),
        settings: { runs_on: runsOn, turn_mode: mode, orchestrator: mode === 'orchestrator' ? orchestrator : null, review, narrate, max_turns: maxTurns, max_spend_cents: cents },
      },
      onClose,
    );

  return (
    <Modal title="Crew settings" onClose={onClose}>
      <div className="form">
        <label id="crew-bots">Bots in the crew</label>
        <div className="pickcats" role="group" aria-labelledby="crew-bots">
          {bots.length === 0 && <small className="dim">You have no bots yet. Make one first.</small>}
          {bots.map((b) => (
            <button key={b.id} type="button" aria-pressed={members.includes(b.id)} className={members.includes(b.id) ? 'pickcat on' : 'pickcat'} onClick={() => toggle(b.id)}>
              <span className="mini">
                <BotCat look={b.look} mascot={b.mascot} size={34} />
              </span>
              {b.name}
            </button>
          ))}
        </div>

        <label>
          Where it runs
          <select aria-label="Where the crew runs" value={runsOn ?? ''} onChange={(e) => setRunsOn(e.target.value || null)}>
            {everywhere.map((p) => (
              <option key={p.id ?? ''} value={p.id ?? ''} disabled={!p.linked && p.id !== runsOn}>
                {p.linked ? p.name : `${p.name} (offline)`}
              </option>
            ))}
          </select>
          {runsOn === null && <small>{CLOUD_NOTE}</small>}
        </label>

        <label id="crew-turns">How turns are taken</label>
        <div className="modes two-up" role="radiogroup" aria-labelledby="crew-turns">
          {TURNS.map((m) => (
            <button key={m.value} type="button" role="radio" aria-checked={mode === m.value} className={mode === m.value ? 'mode on' : 'mode'} onClick={() => setMode(m.value)}>
              <b>{m.label}</b>
              <small>{m.hint}</small>
            </button>
          ))}
        </div>
        {mode === 'orchestrator' && (
          <label>
            Who picks
            <select aria-label="Who picks" value={orchestrator ?? ''} onChange={(e) => setOrchestrator(e.target.value || null)}>
              <option value="">Claude</option>
              {bots
                .filter((b) => members.includes(b.id))
                .map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
            </select>
          </label>
        )}

        <label id="crew-review">How pull requests are reviewed</label>
        <div className="modes two-up" role="radiogroup" aria-labelledby="crew-review">
          {REVIEWS.map((m) => (
            <button key={m.value} type="button" role="radio" aria-checked={review === m.value} className={review === m.value ? 'mode on' : 'mode'} onClick={() => setReview(m.value)}>
              <b>{m.label}</b>
              <small>{m.hint}</small>
            </button>
          ))}
        </div>

        <div className="switchrow">
          <span>
            <b id="crew-narrate">Narrate when watched</b>
            <small>Each new turn is read aloud while you have the chat open. Otherwise it works in silence.</small>
          </span>
          <button type="button" role="switch" aria-checked={narrate} aria-labelledby="crew-narrate" className="sw" onClick={() => setNarrate(!narrate)}>
            <i />
          </button>
        </div>

        <label id="crew-caps">Safety caps</label>
        <div className="two" role="group" aria-labelledby="crew-caps">
          <label>
            Most turns
            <input type="number" min={1} max={200} step={1} value={turns} onChange={(e) => setTurns(e.target.value)} />
            <small>It stops here if no one has said it is done.</small>
          </label>
          <label>
            Most spend, in dollars
            <input inputMode="decimal" value={spend} placeholder="No cap" onChange={(e) => setSpend(e.target.value)} />
            <small>It stops once it has cost this much.</small>
          </label>
        </div>

        {crew.error && <div className="err">{crew.error.message}</div>}
        <div className="row end">
          <button type="button" className="btn ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn primary" disabled={!ready || crew.pending} onClick={save}>
            {crew.pending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </Modal>
  );
}
