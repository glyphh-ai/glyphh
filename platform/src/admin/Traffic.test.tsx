import { screen, waitFor, within } from '@testing-library/react';
import type { Traffic, TrafficZone } from '@/api/admin';
import * as fake from '@/test/admin';
import { staffHandlers } from '@/test/admin';
import { renderApp } from '@/test/render';
import { http, HttpResponse, server, v1 } from '@/test/server';
import { change, share } from './traffic';

function staff(traffic: Traffic = fake.traffic) {
  server.use(...staffHandlers());
  server.use(http.get(v1('/admin/traffic'), () => HttpResponse.json(traffic)));
}

const app = fake.traffic.zones[1]!;
const withApp = (over: Partial<TrafficZone>): Traffic => ({ ...fake.traffic, zones: [fake.traffic.zones[0]!, { ...app, ...over }] });

describe('Traffic on the dashboard', () => {
  it('shows visitors, page views and the visitor to sign-up rate against the period before', async () => {
    staff();
    renderApp('/admin');
    expect(await screen.findByText('Visitors, last 7 days')).toBeInTheDocument();
    expect(screen.getByText('4,200')).toBeInTheDocument();
    expect(screen.getByText('+20% on the 7 days before (3,500)')).toBeInTheDocument();
    expect(screen.getByText('−5% on the 7 days before (9,500)')).toBeInTheDocument();
    expect(screen.getAllByText('– on the 30 days before (0)')).toHaveLength(2);
    expect(screen.getByText('1.0%')).toBeInTheDocument();
    expect(screen.getByText('42 sign-ups')).toBeInTheDocument();
    expect(screen.getByText(/Last pulled 23 Oct 11:05:00 UTC/)).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Visitors and page views by day' })).toBeInTheDocument();
    const links = screen.getAllByRole('link', { name: 'Traffic' }); // the sidebar's and the card's
    expect(links.map((l) => l.getAttribute('href'))).toEqual(['/admin/traffic', '/admin/traffic']);
  });

  it('says when Cloudflare is not connected', async () => {
    staff({ ...fake.traffic, connected: false, zones: [], pulled_at: null });
    renderApp('/admin');
    expect(await screen.findByText('Cloudflare is not connected.')).toBeInTheDocument();
  });
});

describe('The Traffic page', () => {
  it('shows a domain by day, its countries, pages and referrers, and when it was pulled', async () => {
    staff();
    renderApp('/admin/traffic');
    expect(await screen.findByRole('img', { name: 'Visitors and page views on glyphh.ai by day' })).toBeInTheDocument();
    expect(screen.getByText(/Last pulled 23 Oct 11:05:00 UTC/)).toBeInTheDocument();
    expect(within(screen.getByRole('table', { name: 'Top countries' })).getByText('3,000')).toBeInTheDocument();
    const pages = screen.getByRole('table', { name: 'Top pages' });
    expect(within(pages).getByText('/pricing')).toBeInTheDocument();
    expect(within(pages).getByText('docs.glyphh.ai')).toBeInTheDocument();
    expect(within(screen.getByRole('table', { name: 'Top referrers' })).getByText('www.google.com')).toBeInTheDocument();
  });

  it('narrows to one hostname, and shows Web Analytics where the plan has no pages', async () => {
    staff();
    const { user } = renderApp('/admin/traffic');
    const domain = await screen.findByLabelText('Domain');
    expect(within(domain).getAllByRole('option').map((o) => o.textContent)).toEqual(['glyphh.ai (whole domain)', 'docs.glyphh.ai', 'glyphh.ai', 'glyphh.app (whole domain)']);
    await user.selectOptions(domain, 'glyphh.ai|docs.glyphh.ai');
    expect(await screen.findByRole('img', { name: 'Requests and visits to docs.glyphh.ai by day' })).toBeInTheDocument();
    expect(screen.getByText('Top countries, all of glyphh.ai')).toBeInTheDocument();
    const pages = screen.getByRole('table', { name: 'Top pages' });
    expect(within(pages).getByText('/quickstart')).toBeInTheDocument();
    expect(within(pages).queryByText('/pricing')).not.toBeInTheDocument();
    await user.selectOptions(domain, 'glyphh.app');
    expect(await screen.findByRole('img', { name: 'Visitors and page views on glyphh.app by day' })).toBeInTheDocument();
    expect(within(screen.getByRole('table', { name: 'Top pages' })).getByText('/sign-in')).toBeInTheDocument();
    expect(screen.getAllByText('From Web Analytics')).toHaveLength(2);
    expect(screen.getAllByRole('columnheader', { name: 'Page loads' })).toHaveLength(2);
    expect(screen.getAllByText('None in this period.')).toHaveLength(1); // its countries
  });

  it('says what the plan does not provide', async () => {
    staff(withApp({ available: { ...app.available, rum: { ok: false } } }));
    const { user } = renderApp('/admin/traffic');
    await user.selectOptions(await screen.findByLabelText('Domain'), 'glyphh.app');
    expect(await screen.findByText('Not provided by this zone’s Cloudflare plan.')).toBeInTheDocument();
    expect(screen.getByText('Not provided by this zone’s Cloudflare plan: unknown field.')).toBeInTheDocument();
  });

  it('asks again for another period', async () => {
    const asked: string[] = [];
    server.use(...staffHandlers());
    server.use(
      http.get(v1('/admin/traffic'), ({ request }) => {
        asked.push(new URL(request.url).searchParams.get('days')!);
        return HttpResponse.json(fake.traffic);
      }),
    );
    const { user } = renderApp('/admin/traffic');
    await user.selectOptions(await screen.findByLabelText('Period'), '7');
    await waitFor(() => expect(asked).toEqual(['30', '7']));
  });

  it('says when Cloudflare is not connected, or nothing is pulled yet', async () => {
    staff({ ...fake.traffic, connected: false, zones: [], pulled_at: null });
    renderApp('/admin/traffic');
    expect(await screen.findByText('Cloudflare is not connected')).toBeInTheDocument();
    expect(screen.getByText(/Not pulled yet/)).toBeInTheDocument();
  });

  it('says when nothing is pulled yet', async () => {
    staff({ ...fake.traffic, zones: [], pulled_at: null });
    renderApp('/admin/traffic');
    expect(await screen.findByText('Nothing pulled yet')).toBeInTheDocument();
  });
});

describe('Visitors by referrer on Marketing links', () => {
  it('adds up every domain’s referrers beside sign-ups by source', async () => {
    staff();
    renderApp('/admin/marketing');
    const table = await screen.findByRole('table', { name: 'Visitors by referrer' });
    const rows = within(table).getAllByRole('row').slice(1).map((r) => r.textContent);
    expect(rows).toEqual(['www.google.com410', 'github.com60']);
    expect(screen.getByText('From Web Analytics')).toBeInTheDocument();
  });

  it('says why there are none', async () => {
    const first = fake.traffic.zones[0]!;
    staff({ ...fake.traffic, zones: [{ ...first, available: { ...first.available, referrers: { ok: false, note: 'not on Free' } } }] });
    renderApp('/admin/marketing');
    expect(await screen.findByText('Not provided by this zone’s Cloudflare plan: not on Free.')).toBeInTheDocument();
  });

  it('says when Cloudflare is not connected, or nothing is pulled yet', async () => {
    staff({ ...fake.traffic, connected: false, zones: [] });
    const { unmount } = renderApp('/admin/marketing');
    expect(await screen.findByText('Cloudflare is not connected.')).toBeInTheDocument();
    unmount();
    staff({ ...fake.traffic, zones: [] });
    renderApp('/admin/marketing');
    expect(await screen.findByText('Nothing pulled yet.')).toBeInTheDocument();
  });
});

describe('Traffic numbers', () => {
  it('reads a change and a share', () => {
    expect([change(0.2), change(-0.05), change(0), change(null)]).toEqual(['+20%', '−5%', '0%', '–']);
    expect([share(0.0123), share(null)]).toEqual(['1.2%', '–']);
  });
});
