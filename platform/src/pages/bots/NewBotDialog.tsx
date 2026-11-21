import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useBotModels, useCreateBot } from '@/api/bots';
import { randomLook } from '@/bots/cat/look';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Button, Dialog, Select, TextField } from '@/ui';
import { botPath, CatPicker, TextArea } from './parts';
import styles from './bots.module.css';

/** Makes a bot: its name, what it is for, its cat, what it does (its instructions) and the Claude model it runs on. */
export function NewBotDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const models = useBotModels();
  const create = useCreateBot();
  const [name, setName] = useState('');
  const [summary, setSummary] = useState('');
  const [look, setLook] = useState(randomLook);
  const [instructions, setInstructions] = useState('');
  const [model, setModel] = useState('');
  const chosen = model || models.data?.find((m) => m.default)?.id || models.data?.[0]?.id || '';
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
      description="A bot is a Claude agent that runs on Glyphh, with the tools you allow it and your Ada models."
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
        <CatPicker look={look} onChange={setLook} />
        <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
        <TextField label="What it is for" value={summary} onChange={(e) => setSummary(e.target.value)} maxLength={200} />
        <TextArea
          label="Instructions"
          hint="What the bot does when it runs, in plain words. It reads them before every run."
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
        />
        {models.data && models.data.length > 0 && (
          <Select label="Model" value={chosen} onChange={(e) => setModel(e.target.value)} options={models.data.map((m) => ({ value: m.id, label: m.name }))} />
        )}
        <ApiErrorNotice error={create.error} />
      </div>
    </Dialog>
  );
}
