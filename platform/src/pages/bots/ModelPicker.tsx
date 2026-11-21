import { Link } from 'react-router';
import { useBotKey, useBotModels, useBotVoices, type BotModel, type PermissionMode } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { rate } from '@/lib/format';
import { Select } from '@/ui';
import styles from './bots.module.css';

export const MODES: ReadonlyArray<{ value: PermissionMode; label: string; hint: string }> = [
  { value: 'ask', label: 'Ask first', hint: 'Every tool step waits for your yes, unless its connection allows that tool.' },
  { value: 'connection', label: 'Follow connections', hint: 'Only the tools a connection says to ask about wait for you.' },
  { value: 'auto', label: 'Run on its own', hint: 'Allowed tools run without asking. Blocked tools still never run.' },
];

const per = (m: BotModel, own: boolean) =>
  own
    ? `${rate(m.own_key_input_cents_per_mtok)} in · ${rate(m.own_key_output_cents_per_mtok)} out`
    : `${rate(m.input_cents_per_mtok)} in · ${rate(m.output_cents_per_mtok)} out`;

type Props = { model: string; onModel: (id: string) => void; mode: PermissionMode; onMode: (mode: PermissionMode) => void };

/**
 * The Claude model a bot runs on, as a plain list of names (what the org pays for the chosen one under it, per million
 * tokens: on its own Claude key the markup only, else the rate and the markup), and beside it the permission mode.
 */
export function ModelAndMode({ model, onModel, mode, onMode }: Props) {
  const models = useBotModels();
  const key = useBotKey();
  const own = key.data?.set ?? false;
  const list = models.data?.models ?? [];
  const chosen = list.find((m) => m.id === model);
  const options = list.length
    ? list.map((m) => ({ value: m.id, label: m.default ? `${m.name} (default)` : m.name }))
    : [{ value: model, label: model || 'Loading models…' }];

  return (
    <div className={styles.field}>
      <div className={styles.pair}>
        <Select label="Model" value={model} onChange={(e) => onModel(e.target.value)} options={options} disabled={!list.length} />
        <Select
          label="Permission mode"
          value={mode}
          onChange={(e) => onMode(e.target.value as PermissionMode)}
          options={MODES.map(({ value, label }) => ({ value, label }))}
        />
      </div>
      <span className={styles.muted}>
        {chosen ? `${per(chosen, own)} per million tokens on ${own ? 'your' : 'Glyphh’s'} Claude key. ` : ''}
        {MODES.find((m) => m.value === mode)?.hint} <Link to="/settings/claude-key">Claude key</Link>
      </span>
      <ApiErrorNotice error={models.error} />
    </div>
  );
}

/**
 * The voice a bot speaks in, out of the open voices the server lists. Glyphh does not make speech yet, so there is no
 * sample to play: the choice is kept for when bots speak.
 */
export function VoicePicker({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const voices = useBotVoices();
  const options = [
    { value: '', label: 'No voice' },
    ...(voices.data?.voices ?? []).map((v) => ({ value: v.id, label: `${v.name} · ${v.accent} ${v.gender}` })),
  ];
  return (
    <div className={styles.field}>
      <Select
        label="Voice"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        options={options}
        hint={voices.data?.samples ? undefined : 'You can hear it once bots speak: samples are not out yet.'}
      />
      <ApiErrorNotice error={voices.error} />
    </div>
  );
}
