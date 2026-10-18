import type { Machine, MachineSize } from '@/api/types';

/** The three sizes, as the server makes them on Fly: the guest and the volume under it. */
export const sizes: ReadonlyArray<{ value: MachineSize; label: string; cpu: string; ram: string; disk: string }> = [
  { value: 'small', label: 'Small', cpu: '1 shared CPU', ram: '1 GB RAM', disk: '3 GB disk' },
  { value: 'medium', label: 'Medium', cpu: '2 shared CPUs', ram: '4 GB RAM', disk: '10 GB disk' },
  { value: 'large', label: 'Large', cpu: '2 performance CPUs', ram: '8 GB RAM', disk: '20 GB disk' },
];

export const sizeLabel = (size: MachineSize) => sizes.find((s) => s.value === size)?.label ?? size;

/** Where Claude connects: the machine's address and /mcp, once it has one. */
export const connectorUrl = (machine: Pick<Machine, 'address'>) => (machine.address ? `${machine.address}/mcp` : null);
