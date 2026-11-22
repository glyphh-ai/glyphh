// The one door to Monaco: the editor itself (monacoSetup.ts, the Glyphh Bot app's setup) is fetched only when the
// Editor or the Diff first opens, so the Bots area does not carry it until then, and a test can stand in for it here.
export type Monaco = (typeof import('./monacoSetup'))['monaco'];

export const loadMonaco = async (): Promise<Monaco> => (await import('./monacoSetup')).monaco;
