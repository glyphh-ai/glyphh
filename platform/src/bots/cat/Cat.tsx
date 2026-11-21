import { useMemo } from 'react';
import { catMarkup } from './catArt';
import { normalizeLook, type Look } from './look';
import './cat.css';

type Props = {
  look: Partial<Look> | null | undefined;
  size?: number;
  /** 'head' crops to the head; 'full' shows the whole cat. */
  mode?: 'head' | 'full';
  /** Running: the cat bobs faster. */
  busy?: boolean;
  className?: string;
  /** Read out for the cat; none, and the cat is decoration. */
  label?: string;
};

/** A bot: Spike, the Glyphh cat, in black and white, with the bot's own parts (as the Glyphh Bot app draws him). */
export function Cat({ look, size = 48, mode = 'head', busy, className = '', label }: Props) {
  const whole = normalizeLook(look);
  const key = JSON.stringify(whole);
  const html = useMemo(() => catMarkup(whole), [key]); // eslint-disable-line react-hooks/exhaustive-deps
  const full = mode === 'full';
  return (
    <svg
      className={`cat-svg ${whole.pose === 'hop' ? 'pose-hop' : ''} ${busy ? 'busy' : ''} ${className}`}
      width={size}
      height={full ? size * 1.21 : size}
      viewBox={full ? '-6 -8 177 214' : '6 -4 158 158'}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
