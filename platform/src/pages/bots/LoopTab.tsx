import { useState } from 'react';
import { problemsOf, useUpdateBot, type Bot, type BotSpec } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Button, Card, TextField, useToast } from '@/ui';
import { LoopSteps, SectionTitle, TextArea } from './parts';
import styles from './bots.module.css';

type Skill = { name: string; text: string };

/** What is wrong with the JSON as typed, before the server is asked; nothing when it is an object. */
function parseSpec(text: string): { spec?: BotSpec; error?: string } {
  try {
    const spec = JSON.parse(text) as unknown;
    if (spec === null || typeof spec !== 'object' || Array.isArray(spec)) return { error: 'The spec is a JSON object: { … }.' };
    return { spec: spec as BotSpec };
  } catch (e) {
    return { error: `Not JSON yet: ${(e as Error).message}` };
  }
}

/**
 * The bot's loop as the SDK walks it (its spec, as JSON) and its skills (named notes Claude reads), saved together.
 * The server checks the spec with the SDK; what it finds wrong is listed, one a line.
 */
export function LoopTab({ bot }: { bot: Bot }) {
  const toast = useToast();
  const update = useUpdateBot(bot.slug);
  const [text, setText] = useState(() => JSON.stringify(bot.spec, null, 2));
  const [skills, setSkills] = useState<Skill[]>(() => Object.entries(bot.skills).map(([name, t]) => ({ name, text: t })));
  const parsed = parseSpec(text);
  const problems = problemsOf(update.error);
  const names = skills.map((s) => s.name.trim());
  const clash = names.some((n, i) => n && names.indexOf(n) !== i);
  const ready = parsed.spec !== undefined && !clash && skills.every((s) => s.name.trim() && s.text.trim());

  const set = (i: number, change: Partial<Skill>) => setSkills((all) => all.map((s, j) => (j === i ? { ...s, ...change } : s)));
  const save = () =>
    update.mutate(
      { spec: parsed.spec, skills: Object.fromEntries(skills.map((s) => [s.name.trim(), s.text.trim()])) },
      { onSuccess: (saved) => toast.show(`${saved.name}’s loop is saved.`) },
    );

  return (
    <div className={styles.stack}>
      <Card>
        <div className={styles.form}>
          <SectionTitle>Loop</SectionTitle>
          <LoopSteps spec={parsed.spec ?? bot.spec} />
          <TextArea label="Spec" hint="The steps, gates and tools as JSON, as bot.json holds them." mono value={text} onChange={(e) => setText(e.target.value)} />
          {parsed.error && <p className={styles.muted} role="status">{parsed.error}</p>}
          {problems.length > 0 && (
            <ul className={styles.problems} aria-label="Problems">
              {problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          )}
        </div>
      </Card>
      <Card>
        <div className={styles.form}>
          <SectionTitle count={skills.length}>Skills</SectionTitle>
          <p className={styles.muted}>Notes Claude reads when a step needs them: how to write, what counts as urgent.</p>
          {skills.map((s, i) => (
            <div key={i} className={styles.skill}>
              <div className={styles.spread}>
                <div className={styles.grow}>
                  <TextField
                    label="Skill name"
                    value={s.name}
                    onChange={(e) => set(i, { name: e.target.value })}
                    error={clash && names.indexOf(s.name.trim()) !== i ? 'Another skill has this name.' : undefined}
                  />
                </div>
                <Button variant="ghost" size="sm" icon="trash" aria-label={`Remove ${s.name || 'skill'}`} onClick={() => setSkills((all) => all.filter((_, j) => j !== i))}>
                  Remove
                </Button>
              </div>
              <TextArea label="What it says" value={s.text} onChange={(e) => set(i, { text: e.target.value })} />
            </div>
          ))}
          <div className={styles.row}>
            <Button variant="secondary" icon="plus" onClick={() => setSkills((all) => [...all, { name: '', text: '' }])}>
              Add skill
            </Button>
          </div>
        </div>
      </Card>
      {problems.length === 0 && <ApiErrorNotice error={update.error} />}
      <div className={styles.row}>
        <Button variant="primary" disabled={!ready} loading={update.isPending} onClick={save}>
          Save loop and skills
        </Button>
      </div>
    </div>
  );
}
