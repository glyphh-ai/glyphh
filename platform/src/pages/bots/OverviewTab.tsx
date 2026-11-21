import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useBotModels, useUpdateBot, type Bot } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Button, Card, Select, TextField, useToast } from '@/ui';
import { botPath, CatPicker, TextArea } from './parts';
import styles from './bots.module.css';

/** The bot's name, what it is for, its instructions, its model and its cat. */
export function OverviewTab({ bot }: { bot: Bot }) {
  const navigate = useNavigate();
  const toast = useToast();
  const models = useBotModels();
  const update = useUpdateBot(bot.slug);
  const [name, setName] = useState(bot.name);
  const [summary, setSummary] = useState(bot.summary ?? '');
  const [instructions, setInstructions] = useState(bot.instructions);
  const [model, setModel] = useState(bot.model);
  const [look, setLook] = useState(bot.look);
  const ready = name.trim() !== '' && instructions.trim() !== '';

  const save = () =>
    update.mutate(
      { name: name.trim(), summary: summary.trim(), instructions: instructions.trim(), model, look },
      {
        onSuccess: (saved) => {
          toast.show(`${saved.name} is saved.`);
          if (saved.slug !== bot.slug) navigate(botPath(saved.slug), { replace: true });
        },
      },
    );

  const options = (models.data ?? []).map((m) => ({ value: m.id, label: m.name }));
  if (model && !options.some((o) => o.value === model)) options.unshift({ value: model, label: model });

  return (
    <Card>
      <div className={styles.form}>
        <CatPicker look={look} onChange={setLook} />
        <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
        <TextField label="What it is for" value={summary} onChange={(e) => setSummary(e.target.value)} maxLength={200} />
        <TextArea label="Instructions" value={instructions} onChange={(e) => setInstructions(e.target.value)} />
        {options.length > 0 && <Select label="Model" value={model} onChange={(e) => setModel(e.target.value)} options={options} />}
        <ApiErrorNotice error={update.error} />
        <div className={styles.row}>
          <Button variant="primary" disabled={!ready} loading={update.isPending} onClick={save}>
            Save
          </Button>
        </div>
      </div>
    </Card>
  );
}
