import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useUpdateBot, type Bot, type PermissionMode } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { plural } from '@/lib/format';
import { Button, Card, TextField, useToast } from '@/ui';
import { MascotPicker, type Face } from './MascotPicker';
import { ModelAndMode, VoicePicker } from './ModelPicker';
import { botPath, TextArea } from './parts';
import { scheduleOf, same } from './schedule';
import { SchedulePicker } from './SchedulePicker';
import { ToolsTab } from './ToolsTab';
import cs from '../connections/connections.module.css';
import styles from './bots.module.css';

/**
 * The bot's editor: its mascot, name, what it is for, instructions, model, permission mode and where it runs, voice,
 * its schedule, and (folded away
 * under their count) its connections and the tools it may use on each; beside them what it has.
 */
type Props = { bot: Bot; connectionsOpen?: boolean; onConnections?: (open: boolean) => void };

export function OverviewTab({ bot, connectionsOpen = false, onConnections }: Props) {
  const navigate = useNavigate();
  const toast = useToast();
  const update = useUpdateBot(bot.slug);
  const [name, setName] = useState(bot.name);
  const [summary, setSummary] = useState(bot.summary ?? '');
  const [instructions, setInstructions] = useState(bot.instructions);
  const [model, setModel] = useState(bot.model);
  const [mode, setMode] = useState<PermissionMode>(bot.permission_mode ?? 'ask');
  const [voice, setVoice] = useState(bot.voice ?? '');
  const [face, setFace] = useState<Face>({ look: bot.look, mascot: bot.mascot ?? '' });
  const [schedule, setSchedule] = useState(() => scheduleOf(bot.schedule));
  const [runsOn, setRunsOn] = useState<string | null>(bot.runs_on ?? null);
  const ready = name.trim() !== '' && instructions.trim() !== '';
  const tools = bot.connections.reduce((n, c) => n + c.tools.length, 0);

  const save = () =>
    update.mutate(
      { name: name.trim(), summary: summary.trim(), instructions: instructions.trim(), model, permission_mode: mode, voice, ...face, schedule, runs_on: runsOn },
      {
        onSuccess: (saved) => {
          toast.show(`${saved.name} is saved.`);
          if (saved.slug !== bot.slug) navigate(botPath(saved.slug), { replace: true });
        },
      },
    );

  return (
    <div className={styles.stack}>
      <div className={`${cs.layout} ${styles.flush}`}>
        <Card>
          <div className={styles.form}>
            <MascotPicker face={face} onChange={setFace} />
            <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
            <TextField label="What it is for" value={summary} onChange={(e) => setSummary(e.target.value)} maxLength={200} />
            <TextArea label="Instructions" hint="What Claude reads before each step that needs judgment." value={instructions} onChange={(e) => setInstructions(e.target.value)} />
            <ModelAndMode model={model} onModel={setModel} mode={mode} onMode={setMode} runsOn={runsOn} onRunsOn={setRunsOn} />
            <VoicePicker value={voice} onChange={setVoice} />
            <SchedulePicker value={schedule} onChange={setSchedule} next={same(schedule, scheduleOf(bot.schedule)) ? bot.next_run : undefined} />
            <ApiErrorNotice error={update.error} />
            <div className={styles.row}>
              <Button variant="primary" disabled={!ready} loading={update.isPending} onClick={save}>
                Save
              </Button>
            </div>
          </div>
        </Card>
        <dl className={cs.facts}>
          <div className={cs.fact}>
            <dt>Connections</dt>
            <dd>{bot.connections.length ? bot.connections.map((c) => c.app_name).join(', ') : 'None yet'}</dd>
          </div>
          <div className={cs.fact}>
            <dt>Tools</dt>
            <dd>{plural(tools, 'tool')}</dd>
          </div>
          <div className={cs.fact}>
            <dt>Skills</dt>
            <dd>{Object.keys(bot.skills).join(', ') || 'None'}</dd>
          </div>
          <div className={cs.fact}>
            <dt>Gates</dt>
            <dd>{plural(bot.gate_models.length, 'gate')}</dd>
          </div>
        </dl>
      </div>
      <details className={styles.fold} open={connectionsOpen} onToggle={(e) => onConnections?.(e.currentTarget.open)}>
        <summary>
          Connections <span className={styles.muted}>({bot.connections.length} · {plural(tools, 'tool')})</span>
        </summary>
        <div className={styles.foldBody}>
          <ToolsTab bot={bot} />
        </div>
      </details>
    </div>
  );
}
