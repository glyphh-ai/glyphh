import { CopyButton } from "../CopyButton/CopyButton";
import styles from "./CodeBlock.module.css";

export interface CodeBlockProps {
  code: string;
  /** What it is: "Terminal", "config.toml". */
  label?: string;
}

/** A block of code or a command, with a copy button. */
export function CodeBlock({ code, label }: CodeBlockProps) {
  return (
    <figure className={styles.block}>
      <figcaption className={styles.bar}>
        <span>{label}</span>
        <CopyButton text={code} />
      </figcaption>
      <pre className={styles.pre}><code>{code}</code></pre>
    </figure>
  );
}
