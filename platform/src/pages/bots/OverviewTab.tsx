import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useUpdateBot, type Bot } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { plural } from '@/lib/format';
import { Button, Card, TextField, useToast } from '@/ui';
import { ModelPicker } from './ModelPicker';
import { botPath, CatPicker, TextArea } from './parts';
import cs from '../connections/connections.module.css';
import styles from './bots.module.css';

/** The bot's name, what it is for, its cat, its instructions and its model; beside them what it has. */
export function OverviewTab({ bot }: { bot: Bot }) {
  const navigate = useNavigate();
  const toast = useToast();
  const update = useUpdateBot(bot.slug);
  const [name, setName] = useState(bot.name);
  const [summary, setSummary] = useState(bot.summary ?? '');
  const [instructions, setInstructions] = useState(bot.instructions);
  const [model, setModel] = useState(bot.model);
  const [look, setLook] = useState(bot.look);
  const ready = name.trim() !== '' && instructions.trim() !== '';
  const tools = bot.connections.reduce((n, c) => n + c.tools.length, 0);

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

  return (
    <div className={`${cs.layout} ${styles.flush}`}>
      <Card>
        <div className={styles.form}>
          <CatPicker look={look} onChange={setLook} />
          <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
          <TextField label="What it is for" value={summary} onChange={(e) => setSummary(e.target.value)} maxLength={200} />
          <TextArea label="Instructions" hint="What Claude reads before each step that needs judgment." value={instructions} onChange={(e) => setInstructions(e.target.value)} />
          <ModelPicker value={model} onChange={setModel} />
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
  );
}
