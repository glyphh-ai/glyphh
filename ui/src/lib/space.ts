/** A step on the spacing scale (tokens --space-1 … --space-10). */
export type Space = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10;

export function space(step: Space): string {
  return step === 0 ? "0" : `var(--space-${step})`;
}
