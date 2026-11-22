import { useState } from 'react';
import { useDrawMascot } from '@/api/bots';
import { randomLook, type Look } from '@/bots/cat/look';
import { MASCOTS, mascotOf } from '@/bots/cat/mascots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Button, TextField } from '@/ui';
import { CatTile } from './parts';
import styles from './maker.module.css';

export type Face = { look: Look; mascot: string };

/**
 * A bot's mascot: one of Glyphh's own black-and-white cats, a shuffled one, or a new one drawn from a few words (Claude
 * draws it on the server, which keeps only safe black-and-white shapes; it is shown as an image).
 */
export function MascotPicker({ face, onChange }: { face: Face; onChange: (face: Face) => void }) {
  const draw = useDrawMascot();
  const [words, setWords] = useState('');
  const crew = face.mascot ? undefined : mascotOf(face.look);
  const drawIt = () => draw.mutate(words.trim(), { onSuccess: ({ mascot }) => onChange({ look: face.look, mascot }) });

  return (
    <div className={styles.picker} role="group" aria-label="Mascot">
      <span className={styles.label}>Mascot</span>
      <div className={styles.pickRow}>
        <CatTile look={face.look} mascot={face.mascot} size={72} label={face.mascot ? 'Its own mascot' : (crew?.name ?? 'Its cat')} />
        <ul className={styles.crew} aria-label="Glyphh cats">
          {MASCOTS.map((m) => (
            <li key={m.name}>
              <button
                type="button"
                className={styles.crewCat}
                aria-pressed={crew?.name === m.name}
                title={m.tagline}
                onClick={() => onChange({ look: m.look, mascot: '' })}
              >
                <CatTile look={m.look} size={36} />
                <span>{m.name}</span>
              </button>
            </li>
          ))}
          <li>
            <Button variant="secondary" size="sm" onClick={() => onChange({ look: randomLook(), mascot: '' })}>
              Shuffle
            </Button>
          </li>
        </ul>
      </div>
      <div className={styles.pickRow}>
        <div className={styles.grow}>
          <TextField
            label="Describe a new one"
            placeholder="A sleepy cat in a tiny chef’s hat"
            value={words}
            maxLength={300}
            onChange={(e) => setWords(e.target.value)}
          />
        </div>
        <Button variant="secondary" icon="sparkle" disabled={!words.trim()} loading={draw.isPending} onClick={drawIt}>
          Draw it
        </Button>
      </div>
      <ApiErrorNotice error={draw.error} />
    </div>
  );
}
