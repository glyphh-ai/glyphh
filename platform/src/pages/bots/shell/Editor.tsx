// The bot editor, a modal as the Glyphh Bot app's (glyphh-bot src/renderer/src/Modals.tsx, BotEditor), in words a
// business person knows: on the left the card with the big cat, the name, what it is for, Shuffle the cat and Describe
// a new one; on the right plain fields under mono caps labels: Access (its apps as on/off pills, its folders on a
// rrotor, and when it must ask), then when it runs, where it runs, its voice, model and effort. Nothing is folded
// away. How the bot works inside is never shown: Claude writes it from the top field ("Tell Claude what to change")
// and it is kept here as loaded and saved back as it is.
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { api } from '@/api/client';
import {
  botKeys,
  isOrchestrator,
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
  type BotFolder,
  type BotScope,
  type BotSpec,
  type ConnectionTool,
  type PermissionMode,
  type Place,
  type Said,
  type Schedule,
} from '@/api/bots';
import { useMachineFolders } from '@/api/rrotorFolders';
import { randomLook, type Look } from '@/bots/cat/look';
import { DescribeMascotModal } from '@/bots/mascot/DescribeMascotModal';
import { outcomesOf } from '../ada';
import { scheduleOf, sentence } from '../schedule';
import { botPath, BotCat, effortOptions, Modal, shortModel, useShell } from './bits';
import { MODES } from './Chat';
import { ConnectorIcon } from './Connections';
import { ScheduleFields } from './ScheduleFields';

/** A bot made by hand starts by only reading; Claude writes the rest of how it works from the top field. */
const FIRST_SPEC: BotSpec = { touches: 'read_only' };
/** The most a standing task holds (the server's limit). */
const TASK_MAX = 4000;

/** What the server found wrong, as a sentence: without where in the bot's insides it found it. */
function plain(problem: string): string {
  const said = problem.replace(/^[\w.[\]$-]+:\s*/, '').trim() || problem.trim();
  const sentence = said.charAt(0).toUpperCase() + said.slice(1);
  return /[.!?]$/.test(sentence) ? sentence : `${sentence}.`;
}

/** What the bot decides, in a line: "urgency (urgent, normal, spam), tone". Empty when it decides nothing. */
function decides(spec: BotSpec): string {
  return Object.keys(spec.gates ?? {})
    .map((g) => {
      const outcomes = outcomesOf(spec, g);
      const name = g.replace(/[_-]+/g, ' ');
      return outcomes.length ? `${name} (${outcomes.join(', ')})` : name;
    })
    .join(', ');
}

/** The folders on the machine the bot runs on, read from that machine itself: open one, or add it. */
function FolderPicker({ place, taken, onAdd, onClose }: { place: Place; taken: string[]; onAdd: (path: string) => void; onClose: () => void }) {
  const [trail, setTrail] = useState<string[]>([]);
  const [typed, setTyped] = useState('');
  const under = trail.at(-1) ?? '';
  const folders = useMachineFolders(place.id, under);
  const add = (path: string) => {
    onAdd(path);
    onClose();
  };
  const unreachable = folders.isError;
  return (
    <Modal title={`Folders on ${place.name}`} front onClose={onClose}>
      <div className="form">
        {!unreachable && (
          <>
            <div className="row">
              <button type="button" className="btn ghost tiny" disabled={trail.length === 0} onClick={() => setTrail((t) => t.slice(0, -1))}>
                ← Back
              </button>
              <code className="folderpath">{under || 'Its folders'}</code>
              {under && (
                <button type="button" className="btn tiny" disabled={taken.includes(under)} onClick={() => add(under)}>
                  Add this folder
                </button>
              )}
            </div>
            <ul className="folderlist" aria-label="Folders">
              {folders.isPending && <li className="dim">Reading its folders…</li>}
              {folders.data?.length === 0 && (
                <li className="dim">{under ? 'No folders in here.' : `${place.name} shares no folders yet. Whoever runs it chooses which folders bots may be given.`}</li>
              )}
              {(folders.data ?? []).map((f) => (
                <li key={f.path}>
                  <button type="button" className="folderopen" title={f.path} aria-label={`Open ${f.name}`} onClick={() => setTrail((t) => [...t, f.path])}>
                    {f.name}
                  </button>
                  <button type="button" className="btn ghost tiny" disabled={taken.includes(f.path)} aria-label={`Add ${f.name}`} onClick={() => add(f.path)}>
                    {taken.includes(f.path) ? 'Added' : 'Add'}
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
        {unreachable && (
          <>
            <div className="err">{folders.error?.message ?? `${place.name} cannot show its folders from here.`}</div>
            <label>
              Type the folder’s path instead
              <div className="row">
                <input aria-label="Type the folder’s path instead" value={typed} placeholder="/Users/you/Documents/Invoices" onChange={(e) => setTyped(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && typed.trim() && add(typed.trim())} />
                <button type="button" className="btn" disabled={!typed.trim() || taken.includes(typed.trim())} onClick={() => add(typed.trim())}>
                  Add
                </button>
              </div>
            </label>
          </>
        )}
      </div>
    </Modal>
  );
}

export function BotEditor({ bot, onClose }: { bot: Bot | null; onClose: () => void }) {
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
  const [task, setTask] = useState(bot?.task ?? '');
  const [look, setLook] = useState<Look>(() => (bot?.look as Look | undefined) ?? randomLook());
  const [mascot, setMascot] = useState(bot?.mascot ?? '');
  const [voice, setVoice] = useState(bot?.voice ?? '');
  const [model, setModel] = useState(bot?.model ?? '');
  const [mode, setMode] = useState<PermissionMode>(bot?.permission_mode ?? 'ask');
  const [effort, setEffort] = useState(bot?.effort ?? '');
  const [runsOn, setRunsOn] = useState<string | null>(bot?.runs_on ?? null);
  const [folders, setFolders] = useState<BotFolder[]>(() => (bot?.folders ?? []).map((f) => ({ ...f })));
  const [schedule, setSchedule] = useState<Schedule>(() => scheduleOf(bot?.schedule));
  // How it works inside, never shown: kept as loaded (or as Claude drafted it) and saved back as it is.
  const [spec, setSpec] = useState<BotSpec>(() => bot?.spec ?? FIRST_SPEC);
  const [skills, setSkills] = useState<Record<string, string>>(() => bot?.skills ?? {});
  const [scopes, setScopes] = useState<BotScope[]>(() => (bot?.connections ?? []).map((c) => ({ connection_id: c.connection_id, tools: [...c.tools] })));
  const [scoped, setScoped] = useState(false);
  const [idea, setIdea] = useState('');
  const [said, setSaid] = useState<Said[]>([]);
  const [drafted, setDrafted] = useState<BotDraft | null>(null);
  const [describing, setDescribing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [picking, setPicking] = useState(false);

  const chosenModel = model || models.data?.models.find((m) => m.default)?.id || models.data?.models[0]?.id || '';
  const chosenEffort = effort || models.data?.default_effort || 'medium';
  const ready = name.trim() !== '' && instructions.trim() !== '';
  const saving = create.isPending || update.isPending;
  const failed = create.error ?? update.error;
  const problems = problemsOf(failed);
  const reply = said.at(-1)?.role === 'assistant' ? said.at(-1)!.content : '';
  const ask = bot ? 'Tell Claude what to change' : 'Describe your bot and Claude makes it';
  const decided = decides(spec);
  // Where it may run is the bot's own: one that needs a machine's files and commands is not offered Glyphh cloud.
  const mayRunOn = bot?.can_run_on?.length ? bot.can_run_on : (['cloud', 'rrotor'] as const);
  const cloudOk = mayRunOn.includes('cloud');
  const everywhere = (places.data ?? [{ id: null, name: 'Glyphh cloud', mode: 'cloud' as const, linked: true }]).filter((p) => (p.id === null ? cloudOk : mayRunOn.includes('rrotor') || p.id === runsOn));
  const place = runsOn ? everywhere.find((p) => p.id === runsOn) : undefined;
  const orchestrator = isOrchestrator(bot);
  const under = describing || deleting || picking;

  /** The bot as it stands in the fields, for Claude to change: its apps are those of the connections it has. */
  const current = (): BotDraft => {
    const apps = new Map([...(bot?.connections ?? []).map((c) => [c.connection_id, c.app] as const), ...(connections.data ?? []).map((c) => [c.id, c.app] as const)]);
    return {
      name: name.trim(),
      summary: summary.trim(),
      look,
      mascot,
      instructions: instructions.trim(),
      model: chosenModel,
      spec,
      skills,
      apps: scopes.flatMap((s) => (apps.has(s.connection_id) ? [{ app: apps.get(s.connection_id)!, tools: s.tools }] : [])),
      connections: scopes,
    };
  };

  /** The top field: the bot maker's next turn, a question or the bot drafted (or changed) into the fields. */
  const make = () => {
    if (!idea.trim() || draft.isPending) return;
    const messages: Said[] = [...said, { role: 'user', content: idea.trim() }];
    draft.mutate(
      { messages, draft: bot ? current() : drafted },
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
          setSpec(d.spec);
          setSkills(d.skills);
          const first = new Map((connections.data ?? []).map((c) => [c.app, c.id] as const).reverse());
          setScopes(d.apps.flatMap((a) => (first.has(a.app) ? [{ connection_id: first.get(a.app)!, tools: a.tools }] : [])));
          setScoped(true);
        },
      },
    );
  };

  /** An app's pill: on gives the bot every tool of it that is not switched off for the org (in the app's own connection). */
  const toggle = async (id: string) => {
    setScoped(true);
    if (scopes.some((s) => s.connection_id === id)) return setScopes((all) => all.filter((s) => s.connection_id !== id));
    const tools = await queries.fetchQuery(connectionToolsQuery(id)).catch(() => [] as ConnectionTool[]);
    setScopes((all) => (all.some((s) => s.connection_id === id) ? all : [...all, { connection_id: id, tools: tools.filter((t) => t.permission !== 'deny').map((t) => t.key) }]));
  };

  /** Folders are a machine's own: on another machine, or on Glyphh cloud, the bot has none of them. */
  const moveTo = (id: string | null) => {
    if (id !== runsOn) setFolders([]);
    setRunsOn(id);
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
      task: task.trim(),
      look,
      mascot,
      voice,
      model: chosenModel || undefined,
      permission_mode: mode,
      effort: chosenEffort,
      schedule,
      runs_on: runsOn,
      folders: runsOn ? folders : [],
      spec,
      skills,
    };
    if (!bot) return create.mutate({ ...body, summary: body.summary || undefined, connections: scopes }, { onSuccess: (made) => done(made, `${made.name} is made.`) });
    update.mutate(body, {
      onSuccess: (saved) => {
        if (!scoped) return done(saved, `${saved.name} is saved.`);
        // Its slug follows its name, so its apps are saved to the bot as it is called now.
        void api
          .put<Bot>(`/bots/${encodeURIComponent(saved.slug)}/connections`, { connections: scopes })
          .then(() => queries.invalidateQueries({ queryKey: botKeys.bots }))
          .then(() => done(saved, `${saved.name} is saved.`))
          .catch((e: Error) => shell.toast(`Saved, but not its apps: ${e.message}`));
      },
    });
  };

  const sched = (change: Partial<Schedule>) => setSchedule((s) => ({ ...s, ...change }));

  return (
    <>
      <Modal title={bot ? `Edit ${bot.name}` : 'New bot'} wide onClose={under ? () => undefined : onClose}>
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

          <div className="editside">
            <div className="form">
              <label>
                {ask}
                <div className="row">
                  <input
                    aria-label={ask}
                    value={idea}
                    placeholder={bot ? 'also post anything from a customer who is stuck to Slack' : 'a careful sorter of my unread email, every morning'}
                    onChange={(e) => setIdea(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && make()}
                  />
                  <button type="button" className="btn" disabled={draft.isPending || !idea.trim()} onClick={make}>
                    {bot ? (draft.isPending ? 'Changing…' : 'Change it') : draft.isPending ? 'Making…' : 'Make it'}
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
                  What it is for
                  <input value={summary} maxLength={200} placeholder="Answers the easy emails" onChange={(e) => setSummary(e.target.value)} />
                </label>
              </div>
              <label>
                Instructions
                <textarea rows={4} value={instructions} placeholder="What it does, in plain words, as you would tell a new colleague." onChange={(e) => setInstructions(e.target.value)} />
              </label>

              <h3>Access</h3>
              <label id="apps-label">Apps it can use</label>
              <div className="swatches" role="group" aria-labelledby="apps-label">
                {connections.data?.length === 0 && <small className="dim">No apps connected yet.</small>}
                {(connections.data ?? []).map((c) => {
                  const on = scopes.some((s) => s.connection_id === c.id);
                  return (
                    <button key={c.id} type="button" aria-pressed={on} className={on ? 'pill apppill on' : 'pill apppill'} title={`${c.app_name}${c.label ? ` · ${c.label}` : ''}: ${on ? 'it can use it' : 'it cannot use it'}`} onClick={() => void toggle(c.id)}>
                      <ConnectorIcon name={c.app_name} icon={c.app_icon} size={14} />
                      {c.app_name}
                    </button>
                  );
                })}
                <button type="button" className="pill apppill more" onClick={() => shell.openConnections(true)}>
                  + Connect an app
                </button>
              </div>

              <label id="folders-label">Folders it can use</label>
              {!runsOn ? (
                <small className="dim">Glyphh cloud has no folders. To give it files, choose a rrotor under Where it runs.</small>
              ) : (
                <>
                  <ul className="approws" aria-labelledby="folders-label">
                    {folders.length === 0 && <li className="dim">No folders yet: it can use no files on {place?.name ?? 'that machine'}.</li>}
                    {folders.map((f) => (
                      <li key={f.path} className="approw on">
                        <code className="folderpath" title={f.path}>
                          {f.path}
                        </code>
                        <select aria-label={`Access to ${f.path}`} value={f.access} onChange={(e) => setFolders((all) => all.map((x) => (x.path === f.path ? { ...x, access: e.target.value as BotFolder['access'] } : x)))}>
                          <option value="read">Read only</option>
                          <option value="write">Read and change</option>
                        </select>
                        <button type="button" className="btn ghost tiny" aria-label={`Remove ${f.path}`} onClick={() => setFolders((all) => all.filter((x) => x.path !== f.path))}>
                          Remove
                        </button>
                      </li>
                    ))}
                  </ul>
                  <div className="row">
                    <button type="button" className="btn ghost tiny" onClick={() => setPicking(true)}>
                      + Add a folder
                    </button>
                  </div>
                </>
              )}

              <label id="asks-label">Before it acts</label>
              <div className="modes" role="radiogroup" aria-labelledby="asks-label">
                {MODES.map((m) => (
                  <button key={m.value} type="button" role="radio" aria-checked={mode === m.value} className={mode === m.value ? 'mode on' : 'mode'} onClick={() => setMode(m.value)}>
                    <b>{m.label}</b>
                    <small>{m.hint}</small>
                  </button>
                ))}
              </div>

              <h3>When it runs</h3>
              <ScheduleFields schedule={schedule} onChange={sched} />
              <small className="dim" role="status">
                {sentence(schedule, bot && JSON.stringify(schedule) === JSON.stringify(scheduleOf(bot.schedule)) ? bot.next_run : undefined)}
              </small>
              <label>
                What it does when it runs on its own
                <textarea aria-label="What it does when it runs on its own" rows={3} value={task} maxLength={TASK_MAX} placeholder="Go through my unread email and tell me what needs an answer today." onChange={(e) => setTask(e.target.value)} />
                <small>{schedule.every === 'off' ? 'Its standing task. Nothing happens on its own until you choose when it runs.' : 'Its standing task: what it is told each time, as if you had typed it.'}</small>
              </label>

              <h3>Where it runs</h3>
              <label>
                <select aria-label="Where it runs" value={runsOn ?? ''} onChange={(e) => moveTo(e.target.value || null)}>
                  {!cloudOk && runsOn === null && (
                    <option value="" disabled>
                      Choose a rrotor
                    </option>
                  )}
                  {everywhere.map((p) => (
                    <option key={p.id ?? ''} value={p.id ?? ''} disabled={!p.linked && p.id !== runsOn}>
                      {p.linked ? p.name : `${p.name} (offline)`}
                    </option>
                  ))}
                </select>
                <small>
                  {runsOn
                    ? `On that machine, through its rrotor, so it can use the folders you choose there.${cloudOk ? '' : ' It needs a rrotor: it cannot run on Glyphh cloud.'}`
                    : cloudOk
                      ? 'On Glyphh. Nothing to install.'
                      : 'It needs a rrotor: it cannot run on Glyphh cloud.'}
                </small>
              </label>

              <h3>Voice, model and effort</h3>
              <div className="three voice-model">
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
                <label>
                  Effort
                  <select value={chosenEffort} onChange={(e) => setEffort(e.target.value)}>
                    {effortOptions(chosenEffort).map((e) => (
                      <option key={e.value} value={e.value}>
                        {e.label.replace(' effort', '')}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>

            <div className="editfoot">
              {decided && (
                <p className="decides">
                  Decides: {decided} · learned from your answers
                  {bot && (
                    <button
                      type="button"
                      className="link"
                      onClick={() => shell.openDecisions()}
                    >
                      See its decisions
                    </button>
                  )}
                </p>
              )}
              <div className="row end">
                {/* The orchestrator is always there: it is changed like any bot, never deleted. */}
                {bot && !orchestrator && (
                  <button type="button" className="btn ghost danger" onClick={() => setDeleting(true)}>
                    Delete bot
                  </button>
                )}
                <button type="button" className="btn primary" disabled={!ready || saving} onClick={save}>
                  {saving ? 'Saving…' : 'Save bot'}
                </button>
              </div>
              {failed && problems.length === 0 && <div className="err">{failed.message}</div>}
              {problems.length > 0 && (
                <div className="problems" role="alert">
                  <b>It was not saved.</b> Tell Claude what to change, above, and it will put this right:
                  <ul aria-label="Problems">
                    {problems.map((p) => (
                      <li key={p}>{plain(p)}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </div>
      </Modal>
      {/* The modal where a new mascot is drawn from words is the platform's own (bots/mascot), in its own look. */}
      <div className="gb-plain" data-theme="dark-hc">
        <DescribeMascotModal open={describing} look={look} onClose={() => setDescribing(false)} onUse={setMascot} />
      </div>
      {picking && place && (
        <FolderPicker place={place} taken={folders.map((f) => f.path)} onAdd={(path) => setFolders((all) => (all.some((f) => f.path === path) ? all : [...all, { path, access: 'read' }]))} onClose={() => setPicking(false)} />
      )}
      {bot && !orchestrator && deleting && (
        <Modal title={`Delete ${bot.name}?`} small front onClose={() => setDeleting(false)}>
          <p className="dim">Its runs and what it has learned go with it. Your connections stay. This cannot be undone.</p>
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
