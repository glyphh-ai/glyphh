// The Terminal panel, drawn as the Glyphh Bot app's (glyphh-bot src/renderer/src/panels/Terminal.tsx: xterm, its
// theme and font), over what a rrotor serves: the live record of the commands a bot's turn ran in the repository and
// what they printed. It is read-only: nothing typed here is run on the machine. It asks for the new lines every
// second or so while a turn is running, less often when none is.
import { useEffect, useRef, useState } from 'react';
import type { TermLine, WorkClient, Workspace } from '@/api/work';
import { why } from './bits';
import { Ready } from './data';
import type { Term } from './term';

export const LIVE_MS = 1500;
export const IDLE_MS = 6000;
const DIM = '\x1b[2m';
const BOLD = '\x1b[1;97m';
const RED = '\x1b[31m';
const OFF = '\x1b[0m';

/** One line of the record as the terminal draws it: a command bright after its "$", what it printed plain, a note dim. */
export function drawn(line: TermLine): string {
  const text = line.text.replace(/\r?\n$/, '');
  if (line.kind === 'cmd') return `${DIM}$${OFF} ${BOLD}${text}${OFF}\n`;
  if (line.kind === 'note') return `${DIM}${text}${OFF}\n`;
  if (line.kind === 'err') return `${RED}${text}${OFF}\n`;
  return `${text}\n`;
}

function Log({ client, workspace }: { client: WorkClient; workspace: Workspace }) {
  const host = useRef<HTMLDivElement>(null);
  const [live, setLive] = useState(false);
  const [failed, setFailed] = useState('');
  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let term: Term | null = null;
    let gone = false;
    let next = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      let wait = IDLE_MS;
      try {
        const got = await client.terminal(workspace.id, next);
        if (gone) return;
        // A record cut shorter (trimmed when a turn starts) is drawn again from its start.
        if (got.next < next) term?.clear();
        for (const line of got.lines) term?.write(drawn(line));
        next = got.next;
        setLive(got.live);
        setFailed('');
        if (got.live) wait = LIVE_MS;
      } catch (e) {
        if (gone) return;
        setFailed(why(e));
      }
      timer = setTimeout(() => void poll(), wait);
    };
    void import('./term').then(({ makeTerm }) => {
      if (gone) return;
      term = makeTerm(el);
      term.write(`${DIM}What the bots ran in ${workspace.name}. Read-only: nothing typed here runs on the machine.${OFF}\n`);
      void poll();
    });
    return () => {
      gone = true;
      clearTimeout(timer);
      term?.dispose();
    };
  }, [client, workspace.id, workspace.name]);
  return (
    <div className="pane term" aria-label={`Commands run in ${workspace.name}, read-only`}>
      <span className={`wk-live ${live ? 'on' : ''}`} role="status">
        {failed ? failed : live ? 'a turn is running' : 'read-only'}
      </span>
      <div className="termhost" ref={host} />
    </div>
  );
}

export function TerminalPanel() {
  return <Ready>{(client, workspace) => <Log key={workspace.id} client={client} workspace={workspace} />}</Ready>;
}
