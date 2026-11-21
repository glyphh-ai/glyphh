import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { useBotModels, useCreateBot } from '@/api/bots';
import { randomLook } from '@/bots/cat/look';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Button, Dialog, TextField } from '@/ui';
import { ModelPicker } from './ModelPicker';
import { botPath, CatPicker, TextArea } from './parts';
import styles from './bots.module.css';

/** Makes a bot from nothing: its name, what it is for, its cat, its instructions and the Claude model it runs on. */
export function NewBotDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const models = useBotModels();
  const create = useCreateBot();
  const [name, setName] = useState('');
  const [summary, setSummary] = useState('');
  const [look, setLook] = useState(randomLook);
  const [instructions, setInstructions] = useState('');
  const [model, setModel] = useState('');
  const chosen = model || models.data?.models.find((m) => m.default)?.id || models.data?.models[0]?.id || '';
  const ready = name.trim() !== '' && instructions.trim() !== '';

  const make = () =>
    create.mutate(
      { name: name.trim(), summary: summary.trim() || undefined, look, instructions: instructions.trim(), model: chosen || undefined },
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
        <p className={styles.muted}>
          Or start from a ready one: <Link to="/bots?tab=browse" onClick={onClose}>browse bots</Link>.
        </p>
        <CatPicker look={look} onChange={setLook} />
        <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
        <TextField label="What it is for" value={summary} onChange={(e) => setSummary(e.target.value)} maxLength={200} />
        <TextArea
          label="Instructions"
          hint="What the bot does when it runs, in plain words. It reads them before every run."
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
        />
        <ModelPicker value={chosen} onChange={setModel} />
        <ApiErrorNotice error={create.error} />
      </div>
    </Dialog>
  );
}
