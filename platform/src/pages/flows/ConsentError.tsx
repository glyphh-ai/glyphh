import { ApiError } from '@/api/client';
import { AuthLayout } from '@/layout/AuthLayout/AuthLayout';
import { ErrorNotice } from '@/ui';

/** A consent the server would not read, such as one that expired or began in another browser. */
export function ConsentError({ error }: { error: unknown }) {
  const message =
    error instanceof ApiError ? error.message : 'Glyphh could not be reached, or this browser blocked the request. Start again from the app that sent you here.';
  return (
    <AuthLayout title="This sign-in can’t continue">
      <ErrorNotice message={message} traceId={error instanceof ApiError ? error.traceId : undefined} />
    </AuthLayout>
  );
}
