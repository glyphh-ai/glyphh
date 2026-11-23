// When something runs on its own, chosen in plain words (never cron): how often, the day, the time and the time zone.
// One control for every schedule in the Bots area: a bot's (its editor, under When it runs) and a program's.
import type { Every, Schedule } from '@/api/bots';
import { DAYS, EVERY, zones } from '../schedule';

export function ScheduleFields({ schedule, onChange, label = 'When it runs' }: { schedule: Schedule; onChange: (change: Partial<Schedule>) => void; label?: string }) {
  const timed = schedule.every !== 'off' && schedule.every !== 'hour';
  return (
    <div className="looks">
      <select aria-label={label} value={schedule.every} onChange={(e) => onChange({ every: e.target.value as Every })}>
        {EVERY.map((e) => (
          <option key={e.value} value={e.value}>
            {e.value === 'off' ? 'Only when I run it' : e.label}
          </option>
        ))}
      </select>
      {schedule.every === 'week' && (
        <select aria-label="On" value={String(schedule.weekday)} onChange={(e) => onChange({ weekday: Number(e.target.value) })}>
          {DAYS.map((d, i) => (
            <option key={d} value={i}>
              {d}
            </option>
          ))}
        </select>
      )}
      {schedule.every === 'month' && (
        <select aria-label="On day" value={String(schedule.day)} onChange={(e) => onChange({ day: Number(e.target.value) })}>
          {Array.from({ length: 31 }, (_, i) => (
            <option key={i} value={i + 1}>
              Day {i + 1}
            </option>
          ))}
        </select>
      )}
      {timed && <input aria-label="At" type="time" step={60} value={schedule.at} onChange={(e) => e.target.value && onChange({ at: e.target.value })} />}
      {timed && (
        <select aria-label="Time zone" value={schedule.timezone} onChange={(e) => onChange({ timezone: e.target.value })}>
          {zones(schedule.timezone).map((z) => (
            <option key={z} value={z}>
              {z.replace(/_/g, ' ')}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}
