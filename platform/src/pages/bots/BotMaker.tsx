import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { useNavigate } from 'react-router';
import { useBotModels, useConnections, useCreateBot, useDraftBot, type BotDraft, type BotScope, type Connection, type Said } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { plural } from '@/lib/format';
import { useConnect } from '@/pages/connections/useConnect';
import { Button, Chip, Dialog, Icon } from '@/ui';
import { MascotPicker } from './MascotPicker';
import { botPath, CatTile, toolWords } from './parts';
import styles from './maker.module.css';

const HELLO = 'Tell me what you want a bot to do, in your own words. For example: “every morning, sum up my unread email and send me the ones that need an answer”.';
const SPIKE = { head: 'classic', tail: 'spike', eye: 'dot', extra: 'antenna', accessory: 'none', pose: 'stand' } as const;

/** What the draft's apps are on the org now: each app's first connection, or none yet. */
function scoped(draft: BotDraft, connections: Connection[]): { scopes: BotScope[]; missing: string[] } {
  const first = new Map<string, Connection>();
  for (const c of connections) if (!first.has(c.app)) first.set(c.app, c);
  const scopes = draft.apps.flatMap((a) => (first.has(a.app) ? [{ connection_id: first.get(a.app)!.id, tools: a.tools }] : []));
  return { scopes, missing: draft.apps.filter((a) => !first.has(a.app)).map((a) => a.app) };
}

/** An app by its name: the org's connection's when it has one, else its slug in words (google_sheets: Google Sheets). */
const appName = (app: string, connections: Connection[] | undefined) =>
  connections?.find((c) => c.app === app)?.app_name ?? app.replace(/[_-]+/g, ' ').replace(/\b\w/g, (ch) => ch.toUpperCase());

function DraftCard({ draft, problems, onDraft }: { draft: BotDraft; problems: string[]; onDraft: (d: BotDraft) => void }) {
  const models = useBotModels();
  const connections = useConnections();
  const { connect, connecting, error, dialog } = useConnect({ onConnected: () => undefined });
  const linked = new Set((connections.data ?? []).map((c) => c.app));
  const steps = Array.isArray(draft.spec.loop) ? draft.spec.loop.length : 0;
  const gates = Object.keys(draft.spec.gates ?? {}).length;
  const model = models.data?.models.find((m) => m.id === draft.model)?.name ?? draft.model;
  return (
    <li className={styles.draft} aria-label={`Draft: ${draft.name}`}>
      <div className={styles.draftHead}>
        <CatTile look={draft.look} mascot={draft.mascot} size={48} />
        <div>
          <h3 className={styles.draftName}>{draft.name}</h3>
          <span className={styles.muted}>{draft.summary}</span>
        </div>
      </div>
      <span className={styles.muted}>
        {model} · {plural(steps, 'step')} · {plural(gates, 'gate')} · {plural(Object.keys(draft.skills).length, 'skill')}
      </span>
      {draft.apps.length > 0 && (
        <ul className={styles.apps} aria-label="Apps it needs">
          {draft.apps.map((a) => (
            <li key={a.app} className={styles.app}>
              <span>
                <strong>{appName(a.app, connections.data)}</strong> <span className={styles.muted}>{a.tools.map(toolWords).join(', ')}</span>
              </span>
              {linked.has(a.app) ? (
                <Chip tone="green">Connected</Chip>
              ) : (
                <Button
                  size="sm"
                  variant="secondary"
                  loading={connecting === a.app}
                  onClick={() => connect({ slug: a.app, name: appName(a.app, connections.data), description: null, icon: null })}
                >
                  Connect
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {problems.length > 0 && (
        <ul className={styles.problems} aria-label="Still to fix">
          {problems.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      )}
      <MascotPicker face={{ look: draft.look, mascot: draft.mascot }} onChange={(face) => onDraft({ ...draft, ...face })} />
      <ApiErrorNotice error={error} />
      {dialog}
    </li>
  );
}

/**
 * Create with AI: a chat with Glyphh's bot maker (Claude, on the server). The person says what they want; it asks a
 * few short questions, then drafts the whole bot, shown as a card they can change by talking or by picking its mascot;
 * Create makes it, its apps scoped to the org's connections (Connect for any not connected yet).
 */
export function BotMaker({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const ask = useDraftBot();
  const create = useCreateBot();
  const connections = useConnections();
  const [said, setSaid] = useState<Said[]>([]);
  const [typed, setTyped] = useState('');
  const [draft, setDraft] = useState<BotDraft | null>(null);
  const [problems, setProblems] = useState<string[]>([]);
  const end = useRef<HTMLLIElement>(null);
  useEffect(() => end.current?.scrollIntoView?.({ block: 'end' }), [said, ask.isPending, draft]);

  const send = () => {
    const text = typed.trim();
    if (!text || ask.isPending) return;
    const now: Said[] = [...said, { role: 'user', content: text }];
    setSaid(now);
    setTyped('');
    ask.mutate(
      { messages: now, draft },
      {
        onSuccess: (got) => {
          setSaid([...now, { role: 'assistant', content: got.reply }]);
          if (got.draft) setDraft(got.draft);
          setProblems(got.problems);
        },
      },
    );
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };
  const fit = draft ? scoped(draft, connections.data ?? []) : null;
  const make = () => {
    if (!draft || !fit) return;
    const { apps: _apps, connections: _given, ...bot } = draft;
    create.mutate({ ...bot, connections: fit.scopes }, { onSuccess: (made) => navigate(botPath(made.slug)) });
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="wide"
      title="Create with AI"
      description="Say what you want done. Glyphh’s bot maker asks a few questions, then drafts the bot for you to check."
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" icon="sparkle" disabled={!draft || problems.length > 0 || (fit?.missing.length ?? 0) > 0} loading={create.isPending} onClick={make}>
            Create bot
          </Button>
        </>
      }
    >
      <div className={styles.chat}>
        <ol className={styles.messages} aria-label="Conversation" aria-live="polite">
          {[{ role: 'assistant', content: HELLO } as Said, ...said].map((m, i) => (
            <li key={i} className={`${styles.message} ${m.role === 'user' ? styles.mine : ''}`}>
              {m.role === 'assistant' && <CatTile look={SPIKE} size={24} />}
              <div className={styles.bubble}>{m.content}</div>
            </li>
          ))}
          {ask.isPending && (
            <li className={styles.message} aria-label="The bot maker is writing">
              <CatTile look={SPIKE} size={24} busy />
              <div className={`${styles.bubble} ${styles.typing}`}>
                <span />
                <span />
                <span />
              </div>
            </li>
          )}
          {draft && <DraftCard draft={draft} problems={problems} onDraft={setDraft} />}
          <li ref={end} aria-hidden="true" />
        </ol>
        <ApiErrorNotice error={ask.error ?? create.error} />
        <div className={styles.composer}>
          <textarea
            className={styles.input}
            aria-label="Message"
            placeholder={draft ? 'Ask for a change…' : 'What should your bot do?'}
            rows={1}
            value={typed}
            maxLength={8000}
            onChange={(e) => setTyped(e.target.value)}
            onKeyDown={onKey}
          />
          <button type="button" className={styles.sendButton} aria-label="Send" disabled={!typed.trim() || ask.isPending} onClick={send}>
            <Icon name="send" size={18} />
          </button>
        </div>
      </div>
    </Dialog>
  );
}
