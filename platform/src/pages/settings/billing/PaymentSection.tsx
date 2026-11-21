import { useChangeCard, usePayment, usePortal } from '@/api/queries';
import type { Invoice, PaymentCard } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { date, money } from '@/lib/format';
import { Button, Card, Chip, EmptyState, LoadingCard, type ChipTone } from '@/ui';
import tokens from '../tokens/tokens.module.css';
import styles from './billing.module.css';

const brands: Record<string, string> = {
  visa: 'Visa',
  mastercard: 'Mastercard',
  amex: 'American Express',
  discover: 'Discover',
  diners: 'Diners Club',
  jcb: 'JCB',
  unionpay: 'UnionPay',
};

export const brandName = (brand: string) => brands[brand] ?? brand.charAt(0).toUpperCase() + brand.slice(1);

const statuses: Record<string, { label: string; tone: ChipTone }> = {
  paid: { label: 'Paid', tone: 'green' },
  open: { label: 'Due', tone: 'amber' },
  draft: { label: 'Draft', tone: 'neutral' },
  uncollectible: { label: 'Unpaid', tone: 'red' },
  void: { label: 'Void', tone: 'neutral' },
};

const go = ({ url }: { url: string }) => window.location.assign(url);

/** The card on file, and the way to add or replace it in Stripe's page (the card itself is Stripe's, never Glyphh's). */
function CardOnFile({ card }: { card: PaymentCard | null }) {
  const change = useChangeCard();
  return (
    <Card aria-label="Card on file">
      <div className={styles.headLine}>
        <div className={styles.headText}>
          {card ? (
            <>
              <span className={styles.itemName}>{`${brandName(card.brand)} ending ${card.last4}`}</span>
              <span className={tokens.meta}>{`Expires ${String(card.exp_month).padStart(2, '0')}/${String(card.exp_year).slice(-2)}`}</span>
            </>
          ) : (
            <>
              <span className={styles.itemName}>No card on file</span>
              <span className={tokens.meta}>Add one for your plan’s invoices. Top-ups are paid in Stripe’s checkout either way.</span>
            </>
          )}
        </div>
        <Button icon={card ? 'pencil' : 'plus'} loading={change.isPending} onClick={() => change.mutate(undefined, { onSuccess: go })}>
          {card ? 'Replace card' : 'Add a card'}
        </Button>
      </div>
      <ApiErrorNotice error={change.error} />
    </Card>
  );
}

function InvoiceTable({ invoices }: { invoices: Invoice[] }) {
  return (
    <Card>
      <div className={tokens.tableBox}>
        <table className={tokens.table} aria-label="Invoices">
          <thead>
            <tr>
              <th>Date</th>
              <th>Invoice</th>
              <th>Status</th>
              <th className={tokens.num}>Amount</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {invoices.map((invoice) => {
              const status = statuses[invoice.status] ?? { label: invoice.status, tone: 'neutral' as const };
              return (
                <tr key={invoice.id}>
                  <td className={tokens.date}>{date(invoice.created)}</td>
                  <td>{invoice.number ?? '–'}</td>
                  <td>
                    <Chip tone={status.tone}>{status.label}</Chip>
                  </td>
                  <td className={tokens.num}>{money(invoice.total_cents, invoice.currency)}</td>
                  <td className={tokens.num}>
                    {invoice.url && (
                      <a href={invoice.url} aria-label={`View invoice ${invoice.number ?? invoice.id}`}>
                        View
                      </a>
                    )}
                    {invoice.pdf && (
                      <>
                        {' · '}
                        <a href={invoice.pdf} aria-label={`Invoice ${invoice.number ?? invoice.id} as a PDF`}>
                          PDF
                        </a>
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/** Billing's card on file and invoices: the admin's, read from Stripe through the server. */
export function PaymentSection() {
  const payment = usePayment(true);
  const portal = usePortal();
  const portalButton = (
    <Button variant="ghost" iconEnd="external" loading={portal.isPending} onClick={() => portal.mutate(undefined, { onSuccess: go })}>
      All in Stripe
    </Button>
  );
  const hasInvoices = (payment.data?.invoices.length ?? 0) > 0;
  return (
    <>
      <SettingsSection title="Payment method" description="The card your plan’s invoices are charged to. Glyphh never sees or keeps the card number.">
        {payment.isPending && <LoadingCard lines={2} />}
        <ApiErrorNotice error={payment.error} />
        {payment.data && <CardOnFile card={payment.data.card} />}
      </SettingsSection>
      {payment.data && (
        <SettingsSection title="Invoices" description="The last twelve, newest first.">
          {hasInvoices ? <InvoiceTable invoices={payment.data.invoices} /> : <EmptyState icon="card" title="No invoices yet" />}
          {hasInvoices && <div className={tokens.actions}>{portalButton}</div>}
          <ApiErrorNotice error={portal.error} />
        </SettingsSection>
      )}
    </>
  );
}
