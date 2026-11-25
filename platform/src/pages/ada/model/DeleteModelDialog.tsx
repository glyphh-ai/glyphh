import { useState } from 'react';
import { useDeleteAdaModel, type AdaModelRow } from '@/api/ada';
import { AdaErrorNotice } from '../AdaErrorNotice';
import { plural } from '@/lib/format';
import { Button, Dialog, TextField } from '@/ui';

/**
 * Deleting a model takes its name typed again: every precedent and version goes, and it is not undone. The model's
 * page and the models list both open this one.
 */
export function DeleteModelDialog({ model, onClose, onDeleted }: { model: AdaModelRow; onClose: () => void; onDeleted: () => void }) {
  const remove = useDeleteAdaModel();
  const [typed, setTyped] = useState('');
  return (
    <Dialog
      open
      onClose={onClose}
      title="Delete this model?"
      description={
        <>
          <strong>{model.name}</strong>, its {plural(model.precedents, 'precedent')} and every version are deleted. This cannot be undone.
        </>
      }
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="danger" loading={remove.isPending} disabled={typed !== model.name} onClick={() => remove.mutate(model.name, { onSuccess: onDeleted })}>
            Delete
          </Button>
        </>
      }
    >
      <TextField label="Type the model’s name" mono value={typed} onChange={(e) => setTyped(e.target.value)} autoFocus />
      <AdaErrorNotice error={remove.error} />
    </Dialog>
  );
}
