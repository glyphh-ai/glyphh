import type { ReactNode } from 'react';
import type { Plan, Rates } from '@/api/types';
import { usd, usdPerSecond } from '@/lib/format';
import { sizes } from '@/pages/machines/sizes';
import styles from './billing.module.css';

/** What a machine costs: billed by the second while it runs, its disk by the GB all month. */
export const ratesNote = 'A machine is billed by the second while it runs. Its disk is billed by the GB all month, running or not.';

/** A plan sold by contract has its rates in the contract, never on a page. */
export const contractRates = 'Set in your contract.';

/**
 * The hosted machine rates for the plans given, one column each: a month and a second for each size, and the disk. A
 * plan sold by contract (Enterprise) says its rates are set in the contract; a size the server gives no rate is a dash.
 */
export function HostingRates({ rates, plans }: { rates: Rates; plans: Plan[] }) {
  const cell = (plan: Plan, text: (rates: Rates['plans'][string]) => ReactNode) => {
    const own = rates.plans[plan.name];
    if (!plan.self_serve) return <span className={styles.rateSpec}>{contractRates}</span>;
    return own ? text(own) : '—';
  };
  return (
    <div className={styles.ratesWrap}>
      <table className={styles.rates} aria-label="Hosted machine rates">
        <thead>
          <tr>
            <th scope="col">Size</th>
            {plans.map((plan) => (
              <th scope="col" key={plan.name}>
                {plan.name}
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
              {plans.map((plan) => (
                <td key={plan.name}>
                  {cell(plan, (own) => {
                    const rate = own.sizes.find((r) => r.size === size.value);
                    return rate ? (
                      <>
                        <span className={styles.rateName}>{`${usd(rate.usd_per_month)} / month`}</span>
                        <span className={styles.rateSpec}>{`${usdPerSecond(rate.usd_per_second)} / second`}</span>
                      </>
                    ) : (
                      '—'
                    );
                  })}
                </td>
              ))}
            </tr>
          ))}
          <tr>
            <th scope="row">
              <span className={styles.rateName}>Disk</span>
            </th>
            {plans.map((plan) => (
              <td key={plan.name}>
                {cell(plan, (own) => (
                  <span className={styles.rateName}>{`${usd(own.volume_usd_per_gb_month)} / GB / month`}</span>
                ))}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}
