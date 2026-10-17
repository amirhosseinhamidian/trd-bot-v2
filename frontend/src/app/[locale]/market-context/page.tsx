import { notFound } from 'next/navigation';

import { getMarketContexts } from '@/features/market-context/api/client';
import MarketContextDashboard from '@/features/market-context/market-context-dashboard';

type MarketContextPageProps = {
  params: Promise<{
    locale: string;
  }>;
};

export default async function MarketContextPage({ params }: MarketContextPageProps) {
  const { locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const initialPage = await getMarketContexts({ limit: 12, offset: 0 });

  return <MarketContextDashboard initialPage={initialPage} locale={locale} />;
}
