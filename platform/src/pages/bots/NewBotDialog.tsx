import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { useBotModels, useCreateBot, type PermissionMode } from '@/api/bots';
import { randomLook } from '@/bots/cat/look';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Button, Dialog, TextField } from '@/ui';
import { MascotPicker, type Face } from './MascotPicker';
import { ModelAndMode, VoicePicker } from './ModelPicker';
import { botPath, TextArea } from './parts';
import styles from './bots.module.css';

/** A bot made by hand starts as one agent step on what it is given; its Loop tab adds the rest. */
const FIRST_SPEC = { touches: 'read_only', loop: [{ id: 'work', agent: 'Do your job with what you were given: $input' }] };

/** Makes a bot from nothing: its name, what it is for, its mascot, its instructions, model, permission mode and voice. */
export function NewBotDialog({ open, onClose, onAi }: { open: boolean; onClose: () => void; onAi?: () => void }) {
  const navigate = useNavigate();
  const models = useBotModels();
  const create = useCreateBot();
  const [name, setName] = useState('');
  const [summary, setSummary] = useState('');
  const [face, setFace] = useState<Face>(() => ({ look: randomLook(), mascot: '' }));
  const [instructions, setInstructions] = useState('');
  const [model, setModel] = useState('');
  const [mode, setMode] = useState<PermissionMode>('ask');
  const [voice, setVoice] = useState('');
  const chosen = model || models.data?.models.find((m) => m.default)?.id || models.data?.models[0]?.id || '';
  const ready = name.trim() !== '' && instructions.trim() !== '';

  const make = () =>
    create.mutate(
      {
        name: name.trim(),
        summary: summary.trim() || undefined,
        ...face,
        instructions: instructions.trim(),
        model: chosen || undefined,
        permission_mode: mode,
        voice,
        spec: FIRST_SPEC,
      },
      { onSuccess: (bot) => navigate(botPath(bot.slug)) },
    );

  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="wide"
      title="New bot"
      description="A bot runs a loop of steps on Glyphh: Claude where judgment is needed, gates that learn from your answers, and the tools you allow."
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" disabled={!ready} loading={create.isPending} onClick={make}>
            Make bot
          </Button>
        </>
      }
    >
      <div className={styles.form}>
        <div className={styles.spread}>
          <p className={styles.muted}>
            Or start from a ready one: <Link to="/bots?tab=browse" onClick={onClose}>browse bots</Link>.
          </p>
          {onAi && (
            <Button variant="secondary" size="sm" icon="sparkle" onClick={onAi}>
              Create with AI
            </Button>
          )}
        </div>
        <MascotPicker face={face} onChange={setFace} />
        <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
        <TextField label="What it is for" value={summary} onChange={(e) => setSummary(e.target.value)} maxLength={200} />
        <TextArea
          label="Instructions"
          hint="What the bot does when it runs, in plain words. It reads them before every run."
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
        />
        <ModelAndMode model={chosen} onModel={setModel} mode={mode} onMode={setMode} />
        <VoicePicker value={voice} onChange={setVoice} />
        <ApiErrorNotice error={create.error} />
      </div>
    </Dialog>
  );
}
