import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { adaApi, readResponse } from './client';
import { useMe } from './queries';
import type { IsoDate, Uuid } from './types';

/**
 * Ada Cloud's API (`glyphh_ada/api` in the server, at https://ada.glyphh.ai), reached through /api/ada/v1 with the
 * platform's own sign-in. Shapes as the server answers them; dates are ISO strings.
 */

/**
 * Whether Ada Cloud is on, as the account API says (`ada_cloud` on /v1/me); undefined until it is read. A refusal is
 * off, so today's pages show it (and asking again on their mount does not hide them meanwhile).
 */
export function useAdaCloud(): boolean | undefined {
  const me = useMe();
  if (me.data) return me.data.ada_cloud === true;
  return me.errorUpdateCount > 0 ? false : undefined;
}

// The spec, as far as the platform reads it; the kernel checks the rest.
export type SpecRole = {
  name: string;
  similarity_weight?: number;
  security_weight?: number;
  key_part?: boolean;
  numeric_config?: { min_value: number; max_value: number; bin_width: number } | null;
  text_encoding?: 'bag_of_words' | null;
  lexicons?: string[];
};
export type SpecSegment = { name: string; roles: SpecRole[]; similarity_weight?: number; security_weight?: number };
export type SpecLayer = { name: string; segments: SpecSegment[]; similarity_weight?: number; security_weight?: number };
export type SpecOutput = { report?: string[]; costs?: Record<string, Record<string, number>>; ask?: number; ask_below?: number; values?: string[] };
export type Spec = {
  name: string;
  layers: SpecLayer[];
  dimension?: number;
  seed?: number;
  output?: SpecOutput;
  outputs?: Record<string, SpecOutput>;
  settings?: Record<string, unknown>;
  [field: string]: unknown;
};

/** One of the org's models, as `GET /v1/models` lists it. */
export type AdaModelRow = { name: string; id: Uuid; version: number; precedents: number; created_at: IsoDate };
/** One model with its active spec. */
export type AdaModel = AdaModelRow & { spec: Spec };

/** A version: who made it and why, active or not, made on a store of its own (re-encoded), dropped after 7 days unread (gone). */
export type AdaVersion = {
  version: number;
  note: string;
  made_by: string;
  made_at: IsoDate;
  active: boolean;
  backtest: string | null;
  ready: boolean;
  gone: boolean;
  retired_at: IsoDate | null;
  reencoded: boolean;
};

export type JobState = 'awaiting' | 'queued' | 'running' | 'done' | 'failed';
export type AdaJob = {
  id: Uuid;
  model: string;
  kind: 'import' | 'export' | 'learn' | 'calibrate' | 'reencode' | 'backtest' | string;
  state: JobState;
  percent: number | null;
  args: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: { code: string; message: string; [detail: string]: unknown } | null;
  created_at: IsoDate;
  started_at: IsoDate | null;
  finished_at: IsoDate | null;
  made_by: string;
  /** A done export's one-hour link. */
  download?: { url: string; expires_at: number };
};
export const jobEnded = (job: AdaJob | undefined) => job?.state === 'done' || job?.state === 'failed';

/** A spec or settings change, or a rollback: active at once, or once its job (a re-encode or calibration) is done. */
export type VersionChange = { version: number; active: boolean; job: AdaJob | null };

export type LeverValue = number | boolean | string | null;
/** Every lever as it stands on the active version. */
export type Levers = { version: number; settings: Record<string, LeverValue> };

export type Receipt = { id: string; sim: number; outcome: string | null; hash: string; author: string };
/** `POST /v1/decide`: the outcome of least expected cost, its probabilities, whether a person should decide, and the precedents. */
export type Decision = {
  outcome: string | null;
  expected_cost: number | null;
  probabilities: Record<string, number>;
  ask: boolean;
  receipts: Receipt[];
  model: string;
  version: number;
};

/** `GET /v1/usage`: the precedents the org's models hold against its plan's cap (null: none); requests null until counted. */
export type AdaUsage = {
  plan: string | null;
  models: number;
  precedents: { used: number; max: number | null };
  requests: { used: number; max: number | null } | null;
};

export type CloudKey = { id: Uuid; name: string; clearance: number; created_at: IsoDate; expires_at: IsoDate | null; revoked_at: IsoDate | null };
export type NewCloudKey = CloudKey & { key: string };

export type ImportFormat = 'csv' | 'jsonl';
export type ImportStarted = AdaJob & { upload: { url: string; expires_at: number } };
/** A done import's result. */
export type Imported = { rows: number; recorded: number; added: number; replaced: number; refused: number; refusals: Array<{ row: number; path: string; message: string }> };

export type Candidate = { settings?: Record<string, LeverValue>; spec_version?: number; name?: string };
export type Scores = {
  candidate: Candidate;
  n?: number;
  accuracy?: number;
  top_accuracy?: number;
  log_loss?: number;
  ask_rate?: number;
  accuracy_answered?: number | null;
  coverage?: number;
  calibration_error?: number;
  cost?: number;
  cost_mean?: number;
  change?: Record<string, number>;
  learn?: true | string;
  error?: { code: string; message: string };
};
/** A done backtest's result. */
export type BacktestResult = { version: number; trained: number; held_out: number; output: string; active: Scores; candidates: Scores[] };

const jobPoll = 1000;

export const adaKeys = {
  all: ['ada'] as const,
  models: ['ada', 'models'] as const,
  model: (name: string) => ['ada', 'models', name] as const,
  usage: ['ada', 'usage'] as const,
  keys: ['ada', 'keys'] as const,
  job: (id: string) => ['ada', 'jobs', id] as const,
};

const path = (name: string) => `/models/${encodeURIComponent(name)}`;

// Reads

export const useAdaModels = () =>
  useQuery({ queryKey: adaKeys.models, queryFn: async () => (await adaApi.get<{ models: AdaModelRow[] }>('/models')).models });
export const useAdaModel = (name: string) => useQuery({ queryKey: [...adaKeys.model(name), 'view'], queryFn: () => adaApi.get<AdaModel>(path(name)) });
export const useAdaVersions = (name: string) =>
  useQuery({ queryKey: [...adaKeys.model(name), 'versions'], queryFn: async () => (await adaApi.get<{ versions: AdaVersion[] }>(`${path(name)}/versions`)).versions });
export const useAdaLevers = (name: string) => useQuery({ queryKey: [...adaKeys.model(name), 'settings'], queryFn: () => adaApi.get<Levers>(`${path(name)}/settings`) });
export const useAdaUsage = () => useQuery({ queryKey: adaKeys.usage, queryFn: () => adaApi.get<AdaUsage>('/usage') });
export const useCloudKeys = () => useQuery({ queryKey: adaKeys.keys, queryFn: () => adaApi.get<CloudKey[]>('/keys') });

/** A job, read again every second until it is done or failed. */
export const useAdaJob = (id: string | null) =>
  useQuery({
    queryKey: adaKeys.job(id ?? ''),
    enabled: Boolean(id),
    queryFn: () => adaApi.get<AdaJob>(`/jobs/${id}`),
    refetchInterval: (query) => (jobEnded(query.state.data) ? false : jobPoll),
    staleTime: 0,
  });

// Writes: each refreshes what it changed.

function useAdaWrite<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>, refresh: (args: TArgs) => ReadonlyArray<readonly string[]>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (_, args) => Promise.all(refresh(args).map((queryKey) => client.invalidateQueries({ queryKey }))),
  });
}

/** Everything about a model: its view, versions and settings, the list and the usage. */
export const modelReads = (name: string) => [adaKeys.model(name), adaKeys.models, adaKeys.usage];

export const useCreateAdaModel = () =>
  useAdaWrite((body: { name: string; spec: Spec }) => adaApi.post<AdaModel>('/models', body), () => [adaKeys.models, adaKeys.usage]);
export const useDeleteAdaModel = () =>
  useAdaWrite((name: string) => adaApi.delete(`${path(name)}?confirm=${encodeURIComponent(name)}`), () => [adaKeys.models, adaKeys.usage]);
export const usePutSpec = (name: string) =>
  useAdaWrite((body: { spec: Spec; note?: string }) => adaApi.put<VersionChange>(`${path(name)}/spec`, body), () => modelReads(name));
export const usePatchSettings = (name: string) =>
  useAdaWrite(
    (body: { changes: Record<string, LeverValue>; note?: string; backtest?: string }) => adaApi.patch<VersionChange>(`${path(name)}/settings`, body),
    () => modelReads(name),
  );
export const useActivate = (name: string) =>
  useAdaWrite((version: number) => adaApi.post<VersionChange>(`${path(name)}/versions/${version}/activate`), () => modelReads(name));
export const useDecide = () =>
  useMutation({ mutationFn: (body: { model: string; data: Record<string, unknown>; output?: string }) => adaApi.post<Decision>('/decide', body) });
export const useStartImport = (name: string) =>
  useMutation({
    mutationFn: (body: { format: ImportFormat; mapping?: Record<string, string | null> }) => adaApi.post<ImportStarted>(`${path(name)}/imports`, body),
  });
export const useStartBacktest = (name: string) =>
  useMutation({
    mutationFn: (body: { candidates: Candidate[]; holdout: { newest: number }; output?: string }) => adaApi.post<AdaJob>(`${path(name)}/backtest`, body),
  });
export const useStartExport = (name: string) =>
  useMutation({ mutationFn: (format: 'jsonl' | 'ada_sqlite') => adaApi.post<AdaJob>(`${path(name)}/export`, { format }) });

export const useCreateCloudKey = () =>
  useAdaWrite(
    (body: { name: string; expires_in_days: number | null; clearance: number }) =>
      adaApi.post<NewCloudKey>('/keys', body.expires_in_days === null ? { name: body.name, clearance: body.clearance } : body),
    () => [adaKeys.keys],
  );
export const useRevokeCloudKey = () => useAdaWrite((id: string) => adaApi.delete<CloudKey>(`/keys/${id}`), () => [adaKeys.keys]);

/**
 * An import's file, to its upload link through the platform (`PUT /api/ada/v1/uploads/<link>`): the link the server
 * answers is at Ada's host; its last part is the link itself.
 */
export async function uploadFile(uploadUrl: string, file: Blob, contentType: string): Promise<AdaJob> {
  const link = uploadUrl.slice(uploadUrl.lastIndexOf('/') + 1);
  const response = await fetch(`/api/ada/v1/uploads/${link}`, {
    method: 'PUT',
    credentials: 'same-origin',
    headers: { accept: 'application/json', 'content-type': contentType },
    body: file,
  });
  return readResponse<AdaJob>(response);
}
