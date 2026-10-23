import type { AdaRelease } from '@/api/ada';
import { inlineParts, notesBlocks, statusText } from '@/lib/releases';
import { Chip, type ChipTone } from '@/ui';
import styles from './ada.module.css';

const tones: Record<AdaRelease['status'], ChipTone> = { stable: 'green', beta: 'violet', deprecated: 'amber', retired: 'neutral' };

/** An Ada version's status: Stable, Beta, Deprecated with its end, or Retired. */
export function AdaStatusChip({ release }: { release: Pick<AdaRelease, 'status' | 'ends'> }) {
  return <Chip tone={tones[release.status]}>{statusText(release)}</Chip>;
}

/** An Ada version's name, with Beta beside a beta's, wherever a name is shown. */
export function AdaName({ name, beta }: { name: string; beta: boolean }) {
  return (
    <span className={styles.adaName}>
      <span className={styles.mono}>{name}</span>
      {beta && <Chip tone="violet">Beta</Chip>}
    </span>
  );
}

function Line({ text }: { text: string }) {
  return (
    <>
      {inlineParts(text).map((part, i) =>
        part.kind === 'bold' ? <strong key={i}>{part.text}</strong> : part.kind === 'code' ? <code key={i}>{part.text}</code> : <span key={i}>{part.text}</span>,
      )}
    </>
  );
}

/** Release notes as prose: their paragraphs, their lists, their **bold** and `code`. */
export function ReleaseNotes({ notes }: { notes: string }) {
  return (
    <div className={styles.notes}>
      {notesBlocks(notes).map((block, i) =>
        block.kind === 'p' ? (
          <p key={i}>
            <Line text={block.text} />
          </p>
        ) : (
          <ul key={i}>
            {block.items.map((item, j) => (
              <li key={j}>
                <Line text={item} />
              </li>
            ))}
          </ul>
        ),
      )}
    </div>
  );
}
