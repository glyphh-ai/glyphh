import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type {
  Install,
  Machine,
  MachineSize,
  Invite,
  Me,
  Member,
  Model,
  NewInvite,
  NewRuntimeKey,
  NewSelfRuntime,
  OfflineLicence,
  Org,
  Plan,
  Provider,
  Rates,
  Runtime,
  RuntimeKey,
  SelfRuntime,
} from './types';

/** One key per server resource, so a write can refresh exactly what it changed. */
export const keys = {
  me: ['me'] as const,
  installs: ['installs'] as const,
  runtime: ['runtime'] as const,
  runtimeKeys: ['runtime', 'keys'] as const,
  machines: ['machines'] as const,
  selfRuntimes: ['runtimes', 'self'] as const,
  models: ['models'] as const,
  plans: ['plans'] as const,
  rates: ['rates'] as const,
  org: ['org'] as const,
  members: ['org', 'members'] as const,
  invites: ['org', 'invites'] as const,
};

// Reads

export const useMe = () => useQuery({ queryKey: keys.me, queryFn: () => api.get<Me>('/me') });
export const useInstalls = () => useQuery({ queryKey: keys.installs, queryFn: () => api.get<Install[]>('/installs') });
export const useRuntime = () => useQuery({ queryKey: keys.runtime, queryFn: () => api.get<Runtime>('/runtime') });
export const useRuntimeKeys = () => useQuery({ queryKey: keys.runtimeKeys, queryFn: () => api.get<RuntimeKey[]>('/runtime/keys') });
export const useMachines = () => useQuery({ queryKey: keys.machines, queryFn: () => api.get<Machine[]>('/runtimes') });
export const useMachine = (id: string) =>
  useQuery({ queryKey: [...keys.machines, id], queryFn: () => api.get<Machine>(`/runtimes/${id}`) });
export const useSelfRuntimes = () => useQuery({ queryKey: keys.selfRuntimes, queryFn: () => api.get<SelfRuntime[]>('/runtimes/self') });
export const useModels = () => useQuery({ queryKey: keys.models, queryFn: () => api.get<Model[]>('/models') });
export const usePlans = () => useQuery({ queryKey: keys.plans, queryFn: () => api.get<Plan[]>('/plans') });
export const useRates = () => useQuery({ queryKey: keys.rates, queryFn: () => api.get<Rates>('/rates') });
export const useOrg = () => useQuery({ queryKey: keys.org, queryFn: () => api.get<Org>('/org') });
export const useMembers = () => useQuery({ queryKey: keys.members, queryFn: () => api.get<Member[]>('/org/members') });
export const useInvites = () => useQuery({ queryKey: keys.invites, queryFn: () => api.get<Invite[]>('/org/invites') });

// Writes

function useWrite<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>, refresh: ReadonlyArray<readonly string[]>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => Promise.all(refresh.map((queryKey) => client.invalidateQueries({ queryKey }))),
  });
}

export const useStartRuntime = () => useWrite(() => api.post<Runtime>('/runtime/start'), [keys.runtime]);
export const useStopRuntime = () => useWrite(() => api.post<Runtime>('/runtime/stop'), [keys.runtime]);

// A person's first machine is also the old /v1/runtime, which Home reads; a change to any machine refreshes both.
const machineReads = [keys.machines, keys.runtime];
export const useCreateMachine = () =>
  useWrite((body: { name: string; size: MachineSize }) => api.post<Machine>('/runtimes', body), machineReads);
export const useStartMachine = () => useWrite((id: string) => api.post<Machine>(`/runtimes/${id}/start`), machineReads);
export const useStopMachine = () => useWrite((id: string) => api.post<Machine>(`/runtimes/${id}/stop`), machineReads);
export const useRestartMachine = () => useWrite((id: string) => api.post<Machine>(`/runtimes/${id}/restart`), machineReads);
export const useDeleteMachine = () =>
  useWrite(({ id, confirm }: { id: string; confirm: string }) => api.delete(`/runtimes/${id}?confirm=${encodeURIComponent(confirm)}`), machineReads);

export const useCreateRuntimeKey = () =>
  useWrite(
    (body: { name: string; expires_in_days: number | null }) =>
      api.post<NewRuntimeKey>('/runtime/keys', body.expires_in_days === null ? { name: body.name } : body),
    [keys.runtimeKeys],
  );
export const useRevokeRuntimeKey = () =>
  useWrite((id: string) => api.delete<RuntimeKey>(`/runtime/keys/${id}`), [keys.runtimeKeys]);

export const useDeleteRuntimeKey = () => useWrite((id: string) => api.delete(`/runtime/keys/${id}/record`), [keys.runtimeKeys]);

export const useRegisterSelfRuntime = () =>
  useWrite((body: { name: string; public_url: string }) => api.post<NewSelfRuntime>('/runtimes/self', body), [keys.selfRuntimes]);
export const useRotateSelfRuntimeToken = () =>
  useWrite((id: string) => api.post<{ token: string }>(`/runtimes/self/${id}/token`), [keys.selfRuntimes]);
export const useDeleteSelfRuntime = () => useWrite((id: string) => api.delete(`/runtimes/self/${id}`), [keys.selfRuntimes]);
export const useIssueOfflineLicence = () =>
  useWrite(({ id, days }: { id: string; days: number }) => api.post<OfflineLicence>(`/runtimes/${id}/offline-licence`, { days }), []);

export const useDeleteModel = () => useWrite((id: string) => api.delete(`/models/${id}`), [keys.models]);

export const useRenameMe = () => useWrite((name: string) => api.patch<Me>('/me', { name }), [keys.me]);
export const useLinkProvider = () =>
  useWrite((provider: Provider) => api.post<{ url: string }>('/me/identities', { provider }), []);
export const useUnlinkProvider = () =>
  useWrite((provider: Provider) => api.delete(`/me/identities/${provider}`), [keys.me]);
export const useSignOutInstall = () => useWrite((id: string) => api.delete(`/installs/${id}`), [keys.installs, keys.me]);

export const useRenameOrg = () => useWrite((name: string) => api.patch<Org>('/org', { name }), [keys.org, keys.me]);
export const useInvite = () => useWrite((email: string) => api.post<NewInvite>('/org/invites', { email }), [keys.invites, keys.org]);
export const useCancelInvite = () => useWrite((id: string) => api.delete(`/org/invites/${id}`), [keys.invites, keys.org]);
export const useRemoveMember = () => useWrite((id: string) => api.delete(`/org/members/${id}`), [keys.members, keys.org]);

export const useCheckout = () => useWrite((plan: string) => api.post<{ url: string }>('/billing/checkout', { plan }), []);
export const usePortal = () => useWrite(() => api.post<{ url: string }>('/billing/portal'), []);
export const useChangePlan = () => useWrite((plan: string) => api.post<Org>('/billing/plan', { plan }), [keys.org, keys.me]);
