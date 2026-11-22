import { useConfirm, useRelabel, type Decision } from '@/api/botDecisions';
import { Menu, MenuItem, useToast } from '@/ui';
import { others } from './words';
import styles from './decisions.module.css';

/**
 * One click to train a gate on one decision: Right keeps it as a precedent; Wrong opens the gate's other outcomes and
 * the one chosen is learned instead. Both go through the gate's Ada model on the server.
 */
export function RightWrong({ slug, decision }: { slug: string; decision: Decision }) {
  const toast = useToast();
  const confirm = useConfirm(slug);
  const relabel = useRelabel(slug);
  const busy = confirm.isPending || relabel.isPending;
  const failed = (error: Error) => toast.show(error.message);
  const right = () => confirm.mutate([decision.id], { onSuccess: () => toast.show(`Kept: ${decision.label} is ${decision.now}.`), onError: failed });
  const wrong = (outcome: string) =>
    relabel.mutate({ ids: [decision.id], outcome }, { onSuccess: () => toast.show(`Learned: ${decision.label} is ${outcome}.`), onError: failed });
  return (
    <span className={styles.rightWrong}>
      <button
        type="button"
        className={styles.right}
        aria-pressed={decision.confirmed}
        aria-label={`Right: ${decision.label}`}
        disabled={busy}
        onClick={(e) => {
          e.stopPropagation();
          right();
        }}
      >
        Right
      </button>
      <Menu
        label={`It should be, for ${decision.label}`}
        trigger={({ open, toggle, id }) => (
          <button
            type="button"
            className={styles.wrong}
            aria-haspopup="menu"
            aria-expanded={open}
            aria-controls={open ? id : undefined}
            aria-label={`Wrong: ${decision.label}`}
            aria-pressed={decision.corrected !== null && decision.corrected !== decision.outcome}
            disabled={busy || others(decision).length === 0}
            onClick={(e) => {
              e.stopPropagation();
              toggle();
            }}
          >
            Wrong
          </button>
        )}
      >
        {others(decision).map((o) => (
          <MenuItem key={o} onSelect={() => wrong(o)}>
            It should be {o}
          </MenuItem>
        ))}
      </Menu>
    </span>
  );
}
