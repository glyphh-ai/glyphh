import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useDeleteBot, useUpdateBot, type Bot, type PermissionMode } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { Button, TextField, useToast } from '@/ui';
import { LoopTab } from './LoopTab';
import { MascotPicker, type Face } from './MascotPicker';
import { ModelAndMode, VoicePicker } from './ModelPicker';
import { botPath, TextArea } from './parts';
import { scheduleOf, same } from './schedule';
import { SchedulePicker } from './SchedulePicker';
import styles from './bots.module.css';
import look from './look.module.css';

/**
 * The bot's settings, as the Glyphh Bot app's editor: its cat, name, what it is for, its instructions and when it runs,
 * saved together. Under Advanced, folded away: the model, permission mode and where it runs, its voice (saved with
 * the rest), and its loop as JSON with its skills (saved on their own). Then deleting it.
 */
export function SettingsTab({ bot, advanced = false }: { bot: Bot; advanced?: boolean }) {
  const navigate = useNavigate();
  const toast = useToast();
  const update = useUpdateBot(bot.slug);
  const remove = useDeleteBot();
  const [deleting, setDeleting] = useState(false);
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

  const save = () =>
    update.mutate(
      { name: name.trim(), summary: summary.trim(), instructions: instructions.trim(), model, permission_mode: mode, voice, ...face, schedule, runs_on: runsOn },
      {
        onSuccess: (saved) => {
          toast.show(`${saved.name} is saved.`);
          if (saved.slug !== bot.slug) navigate(`${botPath(saved.slug)}?tab=settings`, { replace: true });
        },
      },
    );

  return (
    <div className={look.stack}>
      <section className={look.section} aria-label="The bot">
        <div className={look.labelRow}>
          <h2 className={look.label}>The bot</h2>
        </div>
        <div className={`${look.panel} ${look.panelBody}`}>
          <div className={styles.form}>
            <MascotPicker face={face} onChange={setFace} />
            <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
            <TextField label="What it is for" value={summary} onChange={(e) => setSummary(e.target.value)} maxLength={200} />
            <TextArea label="Instructions" hint="What Claude reads before each step that needs judgment." value={instructions} onChange={(e) => setInstructions(e.target.value)} />
            <SchedulePicker value={schedule} onChange={setSchedule} next={same(schedule, scheduleOf(bot.schedule)) ? bot.next_run : undefined} />
            <details className={look.advanced} open={advanced || undefined}>
              <summary>
                <span className={look.tight}>
                  <span className={look.label}>Advanced</span>
                  <span className={look.muted}>Model, permission mode, where it runs and voice</span>
                </span>
              </summary>
              <div className={look.advancedBody}>
                <ModelAndMode model={model} onModel={setModel} mode={mode} onMode={setMode} runsOn={runsOn} onRunsOn={setRunsOn} />
                <VoicePicker value={voice} onChange={setVoice} />
              </div>
            </details>
            <ApiErrorNotice error={update.error} />
            <div className={styles.row}>
              <Button variant="primary" disabled={!ready} loading={update.isPending} onClick={save}>
                Save
              </Button>
            </div>
          </div>
        </div>
      </section>
      <section className={look.section} aria-label="Loop and skills">
        <details className={look.advanced} open={advanced || undefined}>
          <summary>
            <span className={look.tight}>
              <span className={look.label}>Advanced · loop and skills</span>
              <span className={look.muted}>Its steps, gates and tools as JSON, and the notes Claude reads</span>
            </span>
          </summary>
          <div className={look.advancedBody}>
            <LoopTab key={bot.updated_at} bot={bot} />
          </div>
        </details>
      </section>
      <section className={look.section} aria-label="Delete">
        <div className={look.labelRow}>
          <h2 className={look.label}>Delete</h2>
        </div>
        <div className={`${look.panel} ${look.panelBody} ${look.runHead}`}>
          <p className={look.sub}>Its runs and gates go with it. Your connections stay.</p>
          <Button variant="danger" icon="trash" onClick={() => setDeleting(true)}>
            Delete bot
          </Button>
        </div>
      </section>
      <ConfirmDialog
        open={deleting}
        title={`Delete ${bot.name}?`}
        description="Its runs and gates go with it. This cannot be undone."
        confirmLabel="Delete"
        pending={remove.isPending}
        error={remove.error}
        onConfirm={() =>
          remove.mutate(bot.slug, {
            onSuccess: () => {
              toast.show(`${bot.name} is deleted.`);
              navigate('/bots', { replace: true });
            },
          })
        }
        onClose={() => setDeleting(false)}
      />
    </div>
  );
}
