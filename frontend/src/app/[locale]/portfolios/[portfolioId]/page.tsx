import { notFound } from 'next/navigation';

import {
  getPortfolioAnalytics,
  getSimulatedPortfolio,
  getSimulatedPortfolioPositions,
  getSimulatedPortfolioTimeline,
} from '@/features/portfolios/api/client';
import PortfolioDetail from '@/features/portfolios/portfolio-detail';

type PortfolioDetailPageProps = {
  params: Promise<{
    locale: string;
    portfolioId: string;
  }>;
};

export default async function PortfolioDetailPage({ params }: PortfolioDetailPageProps) {
  const { locale, portfolioId } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const [portfolio, initialPositions, initialTimeline, analytics] = await Promise.all([
    getSimulatedPortfolio(portfolioId),
    getSimulatedPortfolioPositions(portfolioId, { limit: 10, offset: 0 }),
    getSimulatedPortfolioTimeline(portfolioId, { limit: 10, offset: 0 }),
    getPortfolioAnalytics(portfolioId),
  ]);

  return (
    <PortfolioDetail
      portfolio={portfolio}
      initialPositions={initialPositions}
      initialTimeline={initialTimeline}
      analytics={analytics}
      locale={locale}
    />
  );
}
