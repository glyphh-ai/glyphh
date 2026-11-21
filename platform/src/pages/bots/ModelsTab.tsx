import { useState } from 'react';
import { useAdaModels } from '@/api/ada';
import { useUpdateBot, type Bot } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { plural } from '@/lib/format';
import { Button, Card, EmptyState, LoadingCard, useToast } from '@/ui';
import styles from './bots.module.css';

/** The org's Ada models the bot may ask, to decide the way it was decided before. */
export function ModelsTab({ bot }: { bot: Bot }) {
  const toast = useToast();
  const models = useAdaModels();
  const update = useUpdateBot(bot.slug);
  const [chosen, setChosen] = useState(() => new Set(bot.models));
  const toggle = (name: string) =>
    setChosen((all) => {
      const next = new Set(all);
      if (!next.delete(name)) next.add(name);
      return next;
    });
  const save = () => update.mutate({ models: [...chosen] }, { onSuccess: () => toast.show(`${bot.name}’s Ada models are saved.`) });

  if (models.isPending) return <LoadingCard />;
  if (models.error) return <ApiErrorNotice error={models.error} />;
  if (models.data.length === 0 && chosen.size === 0) {
    return (
      <EmptyState icon="model" title="No Ada models yet">
        Make an Ada model from past decisions, then let the bot ask it here.
      </EmptyState>
    );
  }
  const names = [...new Set([...models.data.map((m) => m.name), ...chosen])];

  return (
    <Card>
      <div className={styles.form}>
        <p className={styles.muted}>The bot may ask these models for a decision as it works. {plural(chosen.size, 'model')} chosen.</p>
        <ul className={styles.tools} aria-label="Ada models">
          {names.map((name) => {
            const row = models.data.find((m) => m.name === name);
            return (
              <li key={name}>
                <label className={styles.tool}>
                  <input type="checkbox" checked={chosen.has(name)} onChange={() => toggle(name)} />
                  <span>
                    <span className={styles.toolName}>{name}</span>
                    <span className={`${styles.muted} ${styles.block}`}>{row ? plural(row.precedents, 'precedent') : 'Not found'}</span>
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
        <ApiErrorNotice error={update.error} />
        <div className={styles.row}>
          <Button variant="primary" loading={update.isPending} onClick={save}>
            Save models
          </Button>
        </div>
      </div>
    </Card>
  );
}
