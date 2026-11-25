/** "Good morning" before noon, "Good afternoon" before six, "Good evening" after, by the person's own clock. */
export function greeting(now: Date = new Date()): string {
  const hour = now.getHours();
  return hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
}

/** The greeting with the person's first name, when the profile has one: "Good afternoon, Ada". */
export function greetingFor(name: string | null | undefined, now: Date = new Date()): string {
  const first = name?.trim().split(/\s+/)[0];
  return first ? `${greeting(now)}, ${first}` : greeting(now);
}
