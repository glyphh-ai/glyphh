import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { Icon, ICON, Reactor } from './icons';

/** A chip with a native select laid over it, so it stays small (glyphh-bot Chat.tsx). */
export function SelectChip<T extends string>({
  value,
  options,
  onPick,
  title,
  warn,
  busy,
  wide,
}: {
  value: T;
  options: ReadonlyArray<{ value: T; label: string; disabled?: boolean }>;
  onPick: (v: T) => void;
  /** What the chip sets, read out for the select and shown on hover. */
  title: string;
  warn?: boolean;
  busy?: boolean;
  /** Its words are shown whole, however long (Orchestrator: a bot's name). */
  wide?: boolean;
}) {
  const cur = options.find((o) => o.value === value) ?? options[0];
  return (
    <label className={`ctl sel ${warn ? 'warn' : ''} ${wide ? 'wide' : ''}`} title={title}>
      <span>{cur?.label ?? value}</span>
      <span className="dim">▾</span>
      <select aria-label={title} value={value} disabled={busy} onChange={(e) => onPick(e.target.value as T)}>
        {options.map((o) => (
          <option key={o.value} value={o.value} disabled={o.disabled}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

type Recognition = { start: () => void; stop: () => void; continuous: boolean; interimResults: boolean; onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null; onend: (() => void) | null };
const recognition = (): (new () => Recognition) | undefined => {
  const w = window as unknown as { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
};

type Props = {
  hero: boolean;
  placeholder: string;
  /** A run is going: Send becomes Stop. */
  busy: boolean;
  sending?: boolean;
  onSend: (text: string) => void;
  onStop?: () => void;
  /** The three small pills under the bar, at its bottom right: Model, Effort, Permission mode. Nothing else goes here. */
  children: ReactNode;
  /** Why nothing can be sent right now, said under the bar. */
  note?: ReactNode;
  focusKey: string;
  /** Send works with nothing typed (the crew then works from the repository's own instructions); Enter still needs words. */
  allowEmpty?: boolean;
  /** Nothing can be sent yet (the note says why). */
  off?: boolean;
};

/**
 * The composer, as the Glyphh Bot app's: + (a text file's words join the task), the box that grows with what is typed,
 * the mic (the browser's own dictation, where it has one) and Send, or Stop while a run is going; under it the pills.
 */
export function Composer({ hero, placeholder, busy, sending, onSend, onStop, children, note, focusKey, allowEmpty, off }: Props) {
  const [text, setText] = useState('');
  const [listening, setListening] = useState(false);
  const ref = useRef<HTMLTextAreaElement>(null);
  const picker = useRef<HTMLInputElement>(null);
  const hearing = useRef<Recognition | null>(null);
  const canHear = typeof window !== 'undefined' && recognition() !== undefined;

  useEffect(() => {
    ref.current?.focus();
    return () => hearing.current?.stop();
  }, [focusKey]);

  // The box grows with what is typed, up to a few lines.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [text]);

  const go = (empty = false) => {
    if ((!text.trim() && !empty) || busy || sending || off) return;
    onSend(text.trim());
    setText('');
  };

  const attach = async (files: FileList) => {
    const read = await Promise.all(Array.from(files).map(async (f) => `${f.name}:\n${(await f.text()).slice(0, 20_000)}`));
    setText((t) => [t.trim(), ...read].filter(Boolean).join('\n\n'));
  };

  const mic = () => {
    if (listening) return hearing.current?.stop();
    const Hear = recognition();
    if (!Hear) return;
    const r = new Hear();
    r.continuous = false;
    r.interimResults = false;
    r.onresult = (e) => {
      const said = Array.from(e.results, (alt) => alt[0]?.transcript ?? '').join(' ').trim();
      if (said) setText((t) => (t.trim() ? `${t.trim()} ${said}` : said));
    };
    r.onend = () => setListening(false);
    hearing.current = r;
    setListening(true);
    r.start();
  };

  return (
    <div className={hero ? 'composer hero' : 'composer'}>
      <div className={`inputbar ${listening ? 'listening' : ''}`}>
        <button type="button" className="attach" title="Attach a text file: its words go with the task" aria-label="Attach a text file" onClick={() => picker.current?.click()}>
          <Icon d={ICON.plus} size={18} />
        </button>
        <input
          ref={picker}
          type="file"
          multiple
          hidden
          accept="text/*,.md,.csv,.json,.txt,.log"
          onChange={(e) => {
            if (e.target.files?.length) void attach(e.target.files);
            e.target.value = '';
          }}
        />
        <textarea
          ref={ref}
          rows={1}
          aria-label={placeholder}
          value={text}
          placeholder={listening ? 'Listening… just talk' : placeholder}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              go();
            }
          }}
        />
        <button
          type="button"
          className={`orb ${listening ? 'on' : ''}`}
          title={!canHear ? 'This browser has no dictation' : listening ? 'Stop listening' : 'Talk'}
          aria-label={listening ? 'Stop listening' : 'Talk'}
          disabled={!canHear}
          onClick={mic}
        >
          <span className="orb-core" />
          <Reactor size={44} />
          <Icon d={ICON.mic} size={17} />
        </button>
        {busy && onStop ? (
          <button type="button" className="send stop" title="Stop" aria-label="Stop" onClick={onStop}>
            ■
          </button>
        ) : (
          <button
            type="button"
            className="send"
            title={allowEmpty && !text.trim() ? 'Send nothing: the crew works from the repository’s own instructions' : 'Send'}
            aria-label="Send"
            onClick={() => go(allowEmpty)}
            disabled={(!text.trim() && !allowEmpty) || busy || sending || off}
          >
            ↑
          </button>
        )}
      </div>
      <div className="controls" role="group" aria-label="For this chat">
        {children}
      </div>
      {note && <p className="cnote">{note}</p>}
    </div>
  );
}
