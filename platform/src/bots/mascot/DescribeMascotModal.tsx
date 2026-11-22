import { useState } from 'react';
import { useDrawMascot } from '@/api/bots';
import { Cat } from '@/bots/cat/Cat';
import type { Look } from '@/bots/cat/look';
import { mascotSrc } from '@/bots/cat/mascots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Button, Dialog, TextField } from '@/ui';
import styles from './DescribeMascotModal.module.css';

type Props = {
  open: boolean;
  /** The bot's cat as it is now, shown thinking while the new one is drawn. */
  look?: Look | null;
  onClose: () => void;
  /** The drawing the person chose, as the server sent it (black-and-white shapes); the modal closes itself after. */
  onUse: (mascot: string) => void;
};

/**
 * Drawing a new mascot from a few words, in its own modal: the words, Draw it, the drawing as it comes, then Use it or
 * Try again. Nothing changes on the bot until Use it. It stands alone: mount it beside any button that opens it.
 */
export function DescribeMascotModal({ open, look, onClose, onUse }: Props) {
  const draw = useDrawMascot();
  const [words, setWords] = useState('');
  const [drawn, setDrawn] = useState('');
  const ready = words.trim().length > 0;
  const drawIt = () => draw.mutate(words.trim(), { onSuccess: ({ mascot }) => setDrawn(mascot) });
  const close = () => {
    setWords('');
    setDrawn('');
    draw.reset();
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={close}
      title="Describe a new mascot"
      description="A few words; Claude draws it in black and white."
      actions={
        drawn ? (
          <>
            <Button variant="secondary" icon="undo" loading={draw.isPending} disabled={!ready} onClick={drawIt}>
              Try again
            </Button>
            <Button
              variant="primary"
              icon="check"
              disabled={draw.isPending}
              onClick={() => {
                onUse(drawn);
                close();
              }}
            >
              Use it
            </Button>
          </>
        ) : (
          <>
            <Button variant="secondary" onClick={close}>
              Cancel
            </Button>
            <Button variant="primary" icon="sparkle" disabled={!ready} loading={draw.isPending} onClick={drawIt}>
              Draw it
            </Button>
          </>
        )
      }
    >
      <TextField
        label="Describe it"
        placeholder="A sleepy cat in a tiny chef’s hat"
        value={words}
        maxLength={300}
        onChange={(e) => setWords(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && ready && !draw.isPending) {
            e.preventDefault();
            drawIt();
          }
        }}
      />
      <div className={styles.stage} aria-live="polite" aria-busy={draw.isPending || undefined}>
        {draw.isPending ? (
          <>
            <span className={styles.tile}>
              <Cat look={look} size={120} busy label="Drawing" />
            </span>
            <span className={styles.note}>Drawing…</span>
          </>
        ) : drawn ? (
          <span className={styles.tile}>
            <img src={mascotSrc(drawn)} width={120} height={120} alt="The new mascot" />
          </span>
        ) : (
          <span className={styles.note}>The drawing shows here.</span>
        )}
      </div>
      <ApiErrorNotice error={draw.error} />
    </Dialog>
  );
}
