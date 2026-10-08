import { notFound } from 'next/navigation';

import { getRiskDashboard } from '@/features/risk/api/client';
import RiskDashboard from '@/features/risk/risk-dashboard';
import { getSimulatedPortfolios } from '@/lib/api/client';

type RiskPageProps = {
  params: Promise<{
    locale: string;
  }>;
};

export default async function RiskPage({ params }: RiskPageProps) {
  const { locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const [initialReport, portfolioPage] = await Promise.all([
    getRiskDashboard(),
    getSimulatedPortfolios({ limit: 100, offset: 0 }),
  ]);

  return (
    <RiskDashboard initialReport={initialReport} locale={locale} portfolios={portfolioPage.items} />
  );
}
