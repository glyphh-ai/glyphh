import { useQuery } from '@tanstack/react-query';
import { api } from './client';
import type { Me } from './types';

/** One key per server resource. Only the person is left: the products' resources went with them (2026-11-18). */
export const keys = {
  me: ['me'] as const,
};

export const useMe = () => useQuery({ queryKey: keys.me, queryFn: () => api.get<Me>('/me') });
