import { useState } from 'react';
import { randomLook, type Look } from '@/bots/cat/look';
import { MASCOTS, mascotOf } from '@/bots/cat/mascots';
import { DescribeMascotModal } from '@/bots/mascot/DescribeMascotModal';
import { Button } from '@/ui';
import { CatTile } from './parts';
import styles from './maker.module.css';

export type Face = { look: Look; mascot: string };

/**
 * A bot's mascot: one of Glyphh's own black-and-white cats, a shuffled one, or a new one drawn from a few words in a
 * modal (Claude draws it on the server, which keeps only safe black-and-white shapes; it is shown as an image).
 */
export function MascotPicker({ face, onChange }: { face: Face; onChange: (face: Face) => void }) {
  const [describing, setDescribing] = useState(false);
  const crew = face.mascot ? undefined : mascotOf(face.look);

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
          <li className={styles.crewActions}>
            <Button variant="secondary" size="sm"onClick={() => onChange({ look: randomLook(), mascot: '' })}>
              Shuffle
            </Button>
            <Button variant="secondary" size="sm" icon="sparkle" onClick={() => setDescribing(true)}>
              Describe a new one
            </Button>
          </li>
        </ul>
      </div>
      <DescribeMascotModal open={describing} look={face.look} onClose={() => setDescribing(false)} onUse={(mascot) => onChange({ look: face.look, mascot })} />
    </div>
  );
}
