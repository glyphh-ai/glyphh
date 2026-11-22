// The bot editor, a modal exactly as the Glyphh Bot app's (glyphh-bot src/renderer/src/Modals.tsx, BotEditor): on
// the left the card with the big cat, the name, the tagline, Shuffle the cat and Describe a new one; on the right the
// fields under mono caps labels. What only the platform has (permission mode, where it runs, the schedule, its gates
// in Ada, the loop as JSON and its skills) is folded away under Advanced.
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { api } from '@/api/client';
import {
  botKeys,
  problemsOf,
  useBotModels,
  useBotPlaces,
  useBotVoices,
  useConnections,
  useCreateBot,
  useDeleteBot,
  connectionToolsQuery,
  useDraftBot,
  useUpdateBot,
  type Bot,
  type BotDraft,
  type BotScope,
  type BotSpec,
  type ConnectionTool,
  type Every,
  type PermissionMode,
  type Said,
  type Schedule,
} from '@/api/bots';
import { PART_NAMES } from '@/bots/cat/catArt';
import { ACCESSORIES, EXTRAS, EYES, HEADS, POSES, randomLook, TAILS, type Look } from '@/bots/cat/look';
import { DescribeMascotModal } from '@/bots/mascot/DescribeMascotModal';
import { outcomesOf } from '../ada';
import { botPath } from '../parts';
import { DAYS, EVERY, scheduleOf, sentence, zones } from '../schedule';
import { BotCat, Modal, shortModel, useShell } from './bits';
import { MODES } from './Chat';

/** A bot made by hand starts as one agent step on what it is given; Advanced adds the rest. */
const FIRST_SPEC: BotSpec = { touches: 'read_only', loop: [{ id: 'work', agent: 'Do your job with what you were given: $input' }] };

const PARTS = [
  { key: 'head', list: HEADS },
  { key: 'tail', list: TAILS },
  { key: 'eye', list: EYES },
  { key: 'extra', list: EXTRAS },
  { key: 'accessory', list: ACCESSORIES },
  { key: 'pose', list: POSES },
] as const;

type Skill = { name: string; text: string };

function parseSpec(text: string): { spec?: BotSpec; error?: string } {
  try {
    const spec = JSON.parse(text) as unknown;
    if (spec === null || typeof spec !== 'object' || Array.isArray(spec)) return { error: 'The loop is a JSON object: { … }.' };
    return { spec: spec as BotSpec };
  } catch (e) {
    return { error: `Not JSON yet: ${(e as Error).message}` };
  }
}

export function BotEditor({ bot, advanced = false, onClose }: { bot: Bot | null; advanced?: boolean; onClose: () => void }) {
  const shell = useShell();
  const navigate = useNavigate();
  const queries = useQueryClient();
  const models = useBotModels();
  const voices = useBotVoices();
  const places = useBotPlaces();
  const connections = useConnections();
  const create = useCreateBot();
  const update = useUpdateBot(bot?.slug ?? '');
  const remove = useDeleteBot();
  const draft = useDraftBot();

  const [name, setName] = useState(bot?.name ?? '');
  const [summary, setSummary] = useState(bot?.summary ?? '');
  const [instructions, setInstructions] = useState(bot?.instructions ?? '');
  const [look, setLook] = useState<Look>(() => (bot?.look as Look | undefined) ?? randomLook());
  const [mascot, setMascot] = useState(bot?.mascot ?? '');
  const [voice, setVoice] = useState(bot?.voice ?? '');
  const [model, setModel] = useState(bot?.model ?? '');
  const [mode, setMode] = useState<PermissionMode>(bot?.permission_mode ?? 'ask');
  const [runsOn, setRunsOn] = useState<string | null>(bot?.runs_on ?? null);
  const [schedule, setSchedule] = useState<Schedule>(() => scheduleOf(bot?.schedule));
  const [specText, setSpecText] = useState(() => JSON.stringify(bot?.spec ?? FIRST_SPEC, null, 2));
  const [skills, setSkills] = useState<Skill[]>(() => Object.entries(bot?.skills ?? {}).map(([n, t]) => ({ name: n, text: t })));
  const [scopes, setScopes] = useState<BotScope[]>(() => (bot?.connections ?? []).map((c) => ({ connection_id: c.connection_id, tools: [...c.tools] })));
  const [scoped, setScoped] = useState(false);
  const [idea, setIdea] = useState('');
  const [said, setSaid] = useState<Said[]>([]);
  const [drafted, setDrafted] = useState<BotDraft | null>(null);
  const [describing, setDescribing] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const parsed = parseSpec(specText);
  const spec = parsed.spec ?? bot?.spec ?? FIRST_SPEC;
  const gates = Object.keys(spec.gates ?? {});
  const chosenModel = model || models.data?.models.find((m) => m.default)?.id || models.data?.models[0]?.id || '';
  const names = skills.map((s) => s.name.trim());
  const clash = names.some((n, i) => n && names.indexOf(n) !== i);
  const ready = name.trim() !== '' && instructions.trim() !== '' && parsed.spec !== undefined && !clash && skills.every((s) => s.name.trim() && s.text.trim());
  const saving = create.isPending || update.isPending;
  const failed = create.error ?? update.error;
  const problems = problemsOf(failed);
  const reply = said.at(-1)?.role === 'assistant' ? said.at(-1)!.content : '';
  const timed = schedule.every !== 'off' && schedule.every !== 'hour';

  /** Describe your bot and Claude makes it: the bot maker's next turn, a question or the bot drafted into the fields. */
  const make = () => {
    if (!idea.trim() || draft.isPending) return;
    const messages: Said[] = [...said, { role: 'user', content: idea.trim() }];
    draft.mutate(
      { messages, draft: drafted },
      {
        onSuccess: (r) => {
          setSaid([...messages, { role: 'assistant', content: r.reply }]);
          setIdea('');
          const d = r.draft;
          if (!d) return;
          setDrafted(d);
          setName(d.name);
          setSummary(d.summary);
          setInstructions(d.instructions);
          setLook(d.look);
          setMascot(d.mascot);
          if (d.model) setModel(d.model);
          setSpecText(JSON.stringify(d.spec, null, 2));
          setSkills(Object.entries(d.skills).map(([n, t]) => ({ name: n, text: t })));
          const first = new Map((connections.data ?? []).map((c) => [c.app, c.id] as const).reverse());
          setScopes(d.apps.flatMap((a) => (first.has(a.app) ? [{ connection_id: first.get(a.app)!, tools: a.tools }] : [])));
          setScoped(true);
        },
      },
    );
  };

  /** A connection's pill: on gives the bot every tool of it that is not blocked (the Tools panel narrows it). */
  const toggle = async (id: string) => {
    setScoped(true);
    if (scopes.some((s) => s.connection_id === id)) return setScopes((all) => all.filter((s) => s.connection_id !== id));
    const tools = await queries.fetchQuery(connectionToolsQuery(id)).catch(() => [] as ConnectionTool[]);
    setScopes((all) => (all.some((s) => s.connection_id === id) ? all : [...all, { connection_id: id, tools: tools.filter((t) => t.permission !== 'deny').map((t) => t.key) }]));
  };

  const done = (saved: Bot, text: string) => {
    shell.toast(text);
    onClose();
    if (!bot || saved.slug !== bot.slug) navigate(botPath(saved.slug), { replace: Boolean(bot) });
  };

  const save = () => {
    if (!ready || saving) return;
    const body = {
      name: name.trim(),
      summary: summary.trim(),
      instructions: instructions.trim(),
      look,
      mascot,
      voice,
      model: chosenModel || undefined,
      permission_mode: mode,
      schedule,
      runs_on: runsOn,
      spec: parsed.spec,
      skills: Object.fromEntries(skills.map((s) => [s.name.trim(), s.text.trim()])),
    };
    if (!bot) return create.mutate({ ...body, summary: body.summary || undefined, connections: scopes }, { onSuccess: (made) => done(made, `${made.name} is made.`) });
    update.mutate(body, {
      onSuccess: (saved) => {
        if (!scoped) return done(saved, `${saved.name} is saved.`);
        // Its slug follows its name, so the tools are saved to the bot as it is called now.
        void api
          .put<Bot>(`/bots/${encodeURIComponent(saved.slug)}/connections`, { connections: scopes })
          .then(() => queries.invalidateQueries({ queryKey: botKeys.bots }))
          .then(() => done(saved, `${saved.name} is saved.`))
          .catch((e: Error) => shell.toast(`Saved, but not its connectors: ${e.message}`));
      },
    });
  };

  const setSkill = (i: number, change: Partial<Skill>) => setSkills((all) => all.map((s, j) => (j === i ? { ...s, ...change } : s)));
  const sched = (change: Partial<Schedule>) => setSchedule((s) => ({ ...s, ...change }));

  return (
    <>
      <Modal title={bot ? `Edit ${bot.name}` : 'New bot'} wide onClose={describing || deleting ? () => undefined : onClose}>
        <div className="botedit">
          <div className="preview">
            <BotCat look={look} mascot={mascot} size={190} mode="full" />
            <b>{name || 'Your bot'}</b>
            <small>{summary || 'What it is for'}</small>
            <div className="previewbtns">
              <button
                type="button"
                className="btn ghost"
                onClick={() => {
                  setLook(randomLook());
                  setMascot('');
                }}
              >
                Shuffle the cat
              </button>
              <button type="button" className="btn ghost" onClick={() => setDescribing(true)}>
                Describe a new one
              </button>
            </div>
          </div>

          <div className="form">
            <label>
              Describe your bot and Claude makes it
              <div className="row">
                <input aria-label="Describe your bot and Claude makes it" value={idea} placeholder="a careful sorter of my unread email, every morning" onChange={(e) => setIdea(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && make()} />
                <button type="button" className="btn" disabled={draft.isPending || !idea.trim()} onClick={make}>
                  {draft.isPending ? 'Making…' : 'Make it'}
                </button>
              </div>
              {reply && <small role="status">{reply}</small>}
              {draft.error && <small className="err">{draft.error.message}</small>}
            </label>

            <div className="two">
              <label>
                Name
                <input value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
              </label>
              <label>
                Tagline
                <input value={summary} maxLength={200} placeholder="What it is for" onChange={(e) => setSummary(e.target.value)} />
              </label>
            </div>
            <label>
              Instructions
              <textarea rows={4} value={instructions} placeholder="What the bot does when it runs, in plain words. Claude reads this before every step that needs judgment." onChange={(e) => setInstructions(e.target.value)} />
            </label>

            <div className="two voice-model">
              <label>
                Voice
                <div className="row">
                  <select aria-label="Voice" value={voice} onChange={(e) => setVoice(e.target.value)}>
                    <option value="">No voice</option>
                    {(voices.data?.voices ?? []).map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.name} ({v.gender}, {v.accent})
                      </option>
                    ))}
                  </select>
                  <button type="button" className="btn ghost" disabled title="You can hear it once bots speak: samples are not out yet" aria-label="Play the voice">
                    ▶
                  </button>
                </div>
              </label>
              <label>
                Model
                <select value={chosenModel} onChange={(e) => setModel(e.target.value)}>
                  {(models.data?.models ?? [{ id: chosenModel, name: chosenModel || 'Loading…', default: false }]).map((m) => (
                    <option key={m.id} value={m.id}>
                      {shortModel(m.name)}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <label htmlFor="look-head">Look</label>
            <div className="looks">
              {PARTS.map((p) => (
                <select
                  key={p.key}
                  id={`look-${p.key}`}
                  aria-label={`Look: ${p.key}`}
                  value={look[p.key]}
                  onChange={(e) => {
                    setLook({ ...look, [p.key]: e.target.value } as Look);
                    setMascot('');
                  }}
                >
                  {p.list.map((m) => (
                    <option key={m} value={m}>
                      {(PART_NAMES[p.key] as Record<string, string>)[m] ?? m}
                    </option>
                  ))}
                </select>
              ))}
            </div>

            <label>Connectors this bot can use</label>
            <div className="swatches" role="group" aria-label="Connectors this bot can use">
              {connections.data?.length === 0 && <small className="dim">No connections yet: connect an app under Connections first.</small>}
              {(connections.data ?? []).map((c) => {
                const on = scopes.some((s) => s.connection_id === c.id);
                return (
                  <button key={c.id} type="button" aria-pressed={on} title={c.label ?? undefined} className={on ? 'pill on' : 'pill'} onClick={() => void toggle(c.id)}>
                    {c.app_name}
                  </button>
                );
              })}
            </div>

            <details className="adv" open={advanced || undefined}>
              <summary>
                Advanced <small>Permission mode, where it runs, schedule, Ada gates, the loop and skills</small>
              </summary>
              <div className="form">
                <div className="two">
                  <label>
                    Permission mode
                    <select aria-label="Permission mode" value={mode} onChange={(e) => setMode(e.target.value as PermissionMode)}>
                      {MODES.map((m) => (
                        <option key={m.value} value={m.value}>
                          {m.label}
                        </option>
                      ))}
                    </select>
                    <small>{MODES.find((m) => m.value === mode)?.hint}</small>
                  </label>
                  <label>
                    Runs on
                    <select aria-label="Runs on" value={runsOn ?? ''} onChange={(e) => setRunsOn(e.target.value || null)}>
                      {(places.data ?? [{ id: null, name: 'Glyphh cloud', mode: 'cloud' as const, linked: true }]).map((p) => (
                        <option key={p.id ?? ''} value={p.id ?? ''} disabled={!p.linked && p.id !== runsOn}>
                          {p.linked ? p.name : `${p.name} (offline)`}
                        </option>
                      ))}
                    </select>
                    <small>{runsOn ? 'On that machine, on the Claude key set there. Its tools still go through Glyphh.' : 'On Glyphh, on the org’s Claude key.'}</small>
                  </label>
                </div>

                <h3>Schedule</h3>
                <div className="looks">
                  <select aria-label="Runs" value={schedule.every} onChange={(e) => sched({ every: e.target.value as Every })}>
                    {EVERY.map((e) => (
                      <option key={e.value} value={e.value}>
                        {e.label}
                      </option>
                    ))}
                  </select>
                  {schedule.every === 'week' && (
                    <select aria-label="On" value={String(schedule.weekday)} onChange={(e) => sched({ weekday: Number(e.target.value) })}>
                      {DAYS.map((d, i) => (
                        <option key={d} value={i}>
                          {d}
                        </option>
                      ))}
                    </select>
                  )}
                  {schedule.every === 'month' && (
                    <select aria-label="On day" value={String(schedule.day)} onChange={(e) => sched({ day: Number(e.target.value) })}>
                      {Array.from({ length: 31 }, (_, i) => (
                        <option key={i} value={i + 1}>
                          Day {i + 1}
                        </option>
                      ))}
                    </select>
                  )}
                  {timed && <input aria-label="At" type="time" step={60} value={schedule.at} onChange={(e) => e.target.value && sched({ at: e.target.value })} />}
                  {timed && (
                    <select aria-label="Time zone" value={schedule.timezone} onChange={(e) => sched({ timezone: e.target.value })}>
                      {zones(schedule.timezone).map((z) => (
                        <option key={z} value={z}>
                          {z.replace(/_/g, ' ')}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
                {schedule.every !== 'off' && (
                  <label>
                    What each run is given
                    <input value={schedule.input} placeholder="is:unread" maxLength={20_000} onChange={(e) => sched({ input: e.target.value })} />
                  </label>
                )}
                <small className="dim" role="status">
                  {sentence(schedule, bot && JSON.stringify(schedule) === JSON.stringify(scheduleOf(bot.schedule)) ? bot.next_run : undefined)}
                </small>

                <h3>Ada gates</h3>
                {gates.length === 0 ? (
                  <small className="dim">No gates: it decides nothing in Ada, so it learns nothing from your answers. Add one to the loop below.</small>
                ) : (
                  <ul className="gatelist" aria-label="Ada gates">
                    {gates.map((g) => (
                      <li key={g}>
                        <b>{g}</b>
                        {outcomesOf(spec, g).map((o) => (
                          <span key={o} className="pill">
                            {o}
                          </span>
                        ))}
                      </li>
                    ))}
                  </ul>
                )}
                {bot && gates.length > 0 && (
                  <button
                    type="button"
                    className="link"
                    onClick={() => {
                      onClose();
                      shell.openPanel('gates');
                    }}
                  >
                    What its gates learned in Ada
                  </button>
                )}

                <h3>Loop</h3>
                <label>
                  The loop as JSON
                  <textarea aria-label="The loop as JSON" className="mono" rows={10} spellCheck={false} value={specText} onChange={(e) => setSpecText(e.target.value)} />
                  <small>{parsed.error ?? 'Its steps, gates and tools, as bot.json holds them. The server checks it when you save.'}</small>
                </label>
                {problems.length > 0 && (
                  <ul className="problems" aria-label="Problems">
                    {problems.map((p) => (
                      <li key={p}>{p}</li>
                    ))}
                  </ul>
                )}

                <h3>Skills</h3>
                <small className="dim">Notes Claude reads when a step needs them: how to write, what counts as urgent.</small>
                {skills.map((s, i) => (
                  <div key={i} className="skill">
                    <div className="row">
                      <input aria-label="Skill name" placeholder="Skill name" value={s.name} onChange={(e) => setSkill(i, { name: e.target.value })} />
                      <button type="button" className="btn ghost danger" aria-label={`Remove ${s.name || 'skill'}`} onClick={() => setSkills((all) => all.filter((_, j) => j !== i))}>
                        Remove
                      </button>
                    </div>
                    <textarea aria-label="What it says" rows={2} placeholder="What it says" value={s.text} onChange={(e) => setSkill(i, { text: e.target.value })} />
                  </div>
                ))}
                {clash && <small className="err">Two skills have the same name.</small>}
                <div className="row">
                  <button type="button" className="btn ghost" onClick={() => setSkills((all) => [...all, { name: '', text: '' }])}>
                    + Add skill
                  </button>
                </div>
              </div>
            </details>

            {failed && problems.length === 0 && <div className="err">{failed.message}</div>}
            <div className="row end">
              {bot && (
                <button type="button" className="btn ghost danger" onClick={() => setDeleting(true)}>
                  Delete bot
                </button>
              )}
              <button type="button" className="btn primary" disabled={!ready || saving} onClick={save}>
                {saving ? 'Saving…' : 'Save bot'}
              </button>
            </div>
          </div>
        </div>
      </Modal>
      {/* The modal where a new mascot is drawn from words is the platform's own (bots/mascot), in its own look. */}
      <div className="gb-plain" data-theme="dark-hc">
        <DescribeMascotModal open={describing} look={look} onClose={() => setDescribing(false)} onUse={setMascot} />
      </div>
      {bot && deleting && (
        <Modal title={`Delete ${bot.name}?`} small front onClose={() => setDeleting(false)}>
          <p className="dim">Its runs and gates go with it. Your connections stay. This cannot be undone.</p>
          {remove.error && <div className="err">{remove.error.message}</div>}
          <div className="row end">
            <button type="button" className="btn ghost" onClick={() => setDeleting(false)}>
              Cancel
            </button>
            <button
              type="button"
              className="btn danger solid"
              disabled={remove.isPending}
              onClick={() =>
                remove.mutate(bot.slug, {
                  onSuccess: () => {
                    shell.toast(`${bot.name} is deleted.`);
                    onClose();
                    navigate('/bots', { replace: true });
                  },
                })
              }
            >
              Delete
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
