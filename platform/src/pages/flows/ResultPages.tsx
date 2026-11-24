import { Link, useSearchParams } from 'react-router';
import { AuthLayout } from '@/layout/AuthLayout/AuthLayout';
import { CopyField, ErrorNotice } from '@/ui';
import styles from './flows.module.css';

export function DeviceDonePage() {
  const [params] = useSearchParams();
  const approved = params.get('result') === 'approved';
  return (
    <AuthLayout title={approved ? 'Signed in' : 'Nothing was signed in'}>
      <p className={styles.text}>{approved ? 'Go back to Claude. You can close this tab.' : 'You denied the sign-in. You can close this tab.'}</p>
    </AuthLayout>
  );
}

/** Any refusal the server met in a browser step: its message, and the trace id to quote. */
export function ErrorPage() {
  const [params] = useSearchParams();
  const message = params.get('message') ?? 'Something went wrong.';
  const trace = params.get('trace');
  return (
    <AuthLayout title="That didn’t work">
      <ErrorNotice message={message} />
      {trace && (
        <>
          <p className={styles.text}>If you contact us, quote this trace id.</p>
          <CopyField value={trace} label="trace id" />
        </>
      )}
    </AuthLayout>
  );
}

export function NotFoundPage() {
  return (
    <AuthLayout title="Page not found">
      <p className={styles.text}>There is nothing at this address.</p>
      <Link to="/" className={styles.text}>
        Go to Glyphh
      </Link>
    </AuthLayout>
  );
}
