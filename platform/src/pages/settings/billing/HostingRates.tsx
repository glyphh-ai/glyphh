import type { Rates } from '@/api/types';
import { usd, usdPerSecond } from '@/lib/format';
import { sizes } from '@/pages/machines/sizes';
import styles from './billing.module.css';

/** What a machine costs: billed by the second while it runs, its disk by the GB all month. */
export const ratesNote = 'A machine is billed by the second while it runs. Its disk is billed by the GB all month, running or not.';

/** The hosted machine rates for the plans named, one column each: a month and a second for each size, and the disk. */
export function HostingRates({ rates, plans }: { rates: Rates; plans: string[] }) {
  const shown = plans.filter((name) => rates.plans[name]);
  return (
    <div className={styles.ratesWrap}>
      <table className={styles.rates} aria-label="Hosted machine rates">
        <thead>
          <tr>
            <th scope="col">Size</th>
            {shown.map((name) => (
              <th scope="col" key={name}>
                {name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sizes.map((size) => (
            <tr key={size.value}>
              <th scope="row">
                <span className={styles.rateName}>{size.label}</span>
                <span className={styles.rateSpec}>{`${size.cpu} · ${size.ram} · ${size.disk}`}</span>
              </th>
              {shown.map((name) => {
                const rate = rates.plans[name]!.sizes.find((r) => r.size === size.value);
                return (
                  <td key={name}>
                    {rate ? (
                      <>
                        <span className={styles.rateName}>{`${usd(rate.usd_per_month)} / month`}</span>
                        <span className={styles.rateSpec}>{`${usdPerSecond(rate.usd_per_second)} / second`}</span>
                      </>
                    ) : (
                      '—'
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
          <tr>
            <th scope="row">
              <span className={styles.rateName}>Disk</span>
            </th>
            {shown.map((name) => (
              <td key={name}>
                <span className={styles.rateName}>{`${usd(rates.plans[name]!.volume_usd_per_gb_month)} / GB / month`}</span>
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}
