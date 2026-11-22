import type { Every, Schedule } from '@/api/bots';
import { Select, TextField } from '@/ui';
import { DAYS, EVERY, sentence, zones } from './schedule';
import styles from './bots.module.css';

type Props = { value: Schedule; onChange: (s: Schedule) => void; next?: string };

const DAY_OPTIONS = Array.from({ length: 31 }, (_, i) => ({ value: String(i + 1), label: String(i + 1) }));

/**
 * When the bot runs on its own, chosen in plain words: how often, then (as that needs) the weekday or the day of the
 * month and the time, in the person's time zone (the browser's, which they can change), and what each run is given.
 * One line under it says it back.
 */
export function SchedulePicker({ value, onChange, next }: Props) {
  const set = (change: Partial<Schedule>) => onChange({ ...value, ...change });
  const timed = value.every !== 'off' && value.every !== 'hour';

  return (
    <fieldset className={styles.schedule}>
      <legend className={`${styles.label} ${styles.scheduleLegend}`}>Schedule</legend>
      <div className={styles.scheduleRow}>
        <Select label="Runs" value={value.every} onChange={(e) => set({ every: e.target.value as Every })} options={EVERY} />
        {value.every === 'week' && (
          <Select
            label="On"
            value={String(value.weekday)}
            onChange={(e) => set({ weekday: Number(e.target.value) })}
            options={DAYS.map((d, i) => ({ value: String(i), label: d }))}
          />
        )}
        {value.every === 'month' && (
          <Select label="On day" value={String(value.day)} onChange={(e) => set({ day: Number(e.target.value) })} options={DAY_OPTIONS} />
        )}
        {timed && <TextField label="At" type="time" step={60} value={value.at} onChange={(e) => e.target.value && set({ at: e.target.value })} />}
        {timed && (
          <Select
            label="Time zone"
            value={value.timezone}
            onChange={(e) => set({ timezone: e.target.value })}
            options={zones(value.timezone).map((z) => ({ value: z, label: z.replace(/_/g, ' ') }))}
          />
        )}
      </div>
      {value.every !== 'off' && (
        <TextField
          label="What each run is given"
          placeholder="is:unread"
          value={value.input}
          maxLength={20_000}
          onChange={(e) => set({ input: e.target.value })}
        />
      )}
      <span className={styles.muted} role="status">
        {sentence(value, next)}
      </span>
    </fieldset>
  );
}
