import type { ReactNode } from 'react';
import { ApiError } from '@/api/client';
import { ErrorNotice } from '@/ui';

/** The server's own words for a refusal, with its trace id; anything else gets a plain line. */
export function ApiErrorNotice({ error, action }: { error: unknown; action?: ReactNode }) {
  if (!error) return null;
  if (error instanceof ApiError) return <ErrorNotice message={error.message} traceId={error.traceId} action={action} />;
  return <ErrorNotice message="Glyphh could not be reached. Check your connection and try again." action={action} />;
}
