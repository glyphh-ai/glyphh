import { useQueryClient } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router';
import { keys, useSelfRuntimes } from '@/api/queries';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { Button, EmptyState, LoadingCard } from '@/ui';
import { AddRuntimeDialog } from './add-runtime/AddRuntimeDialog';
import { InstallRrotor } from './InstallRrotor';
import { SelfRuntimes } from './SelfRuntimes';
import styles from './RuntimesPage.module.css';

/**
 * Runtimes, in Runtimes & licences: how to install rrotor on your own computer, and the runtimes you run at your own
 * address (`GET /v1/runtimes/self`), with their token, offline licence and removal. Glyphh hosts none. Add a runtime
 * opens over the page; `?add=1` opens it on load, as older links do.
 */
export function RuntimesPage() {
  const [params, setParams] = useSearchParams();
  const adding = params.get('add') === '1';
  const client = useQueryClient();
  const self = useSelfRuntimes();
  const openAdd = () =>
    setParams((current) => {
      const next = new URLSearchParams(current);
      next.set('add', '1');
      return next;
    });
  const closeAdd = () => {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.delete('add');
        return next;
      },
      { replace: true },
    );
    // A runtime registered in it shows at once.
    void client.invalidateQueries({ queryKey: keys.selfRuntimes });
  };

  return (
    <>
      <PageHeader
        title="Runtimes"
        description={
          <>
            The rrotors you run for your programs and CLIs, on your own machines. Glyphh hosts none: it grants their{' '}
            <Link to="/licence">licence</Link>.
          </>
        }
        actions={
          <Button icon="plus" onClick={openAdd}>
            Add a runtime
          </Button>
        }
      />

      <div className={styles.stack}>
        <InstallRrotor />

        {self.isPending && <LoadingCard />}
        {self.data?.length === 0 && (
          <EmptyState
            icon="home"
            title="No self-hosted runtime yet"
            action={
              <Button variant="primary" onClick={openAdd}>
                Run rrotor on a server
              </Button>
            }
          >
            Run it at your own address with Docker, Helm or Terraform and register it here, free on every plan.
          </EmptyState>
        )}
        <SelfRuntimes />
      </div>

      <AddRuntimeDialog open={adding} onClose={closeAdd} />
    </>
  );
}
