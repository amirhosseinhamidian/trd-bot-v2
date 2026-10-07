import { notFound } from 'next/navigation';

import MarketDataConnectionsPanel from '@/features/connections/market-data-connections-panel';
import {
  getMarketDataConnections,
  getMarketDataProviders,
} from '@/features/connections/api/client';

type ConnectionsPageProps = {
  params: Promise<{
    locale: string;
  }>;
};

export default async function ConnectionsPage({ params }: ConnectionsPageProps) {
  const { locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const [providers, initialPage] = await Promise.all([
    getMarketDataProviders(),
    getMarketDataConnections({
      limit: 12,
      offset: 0,
    }),
  ]);

  return (
    <MarketDataConnectionsPanel
      locale={locale}
      initialProviders={providers}
      initialPage={initialPage}
    />
  );
}
