import { useCopy } from '@/lib/useCopy';
import { Icon } from '../Icon/Icon';
import styles from './CodeBlock.module.css';

type CodeBlockProps = {
  code: string;
  /** What the code is, for the Copy button's name: "Copy install command". */
  label: string;
};

/** Lines to paste into a terminal or a file, with a Copy button for all of them. */
export function CodeBlock({ code, label }: CodeBlockProps) {
  const { copied, copy } = useCopy();
  return (
    <div className={styles.block}>
      <pre className={styles.code}>
        <code>{code}</code>
      </pre>
      <button type="button" className={styles.copy} onClick={() => void copy(code)} aria-label={`Copy ${label}`}>
        <Icon name={copied ? 'check' : 'copy'} size={14} />
        {copied ? 'Copied' : 'Copy'}
      </button>
    </div>
  );
}
