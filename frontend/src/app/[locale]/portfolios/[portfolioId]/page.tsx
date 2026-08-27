import { notFound } from 'next/navigation';

import PortfolioDetail from '@/components/dashboard/portfolio-detail';
import {
  getSimulatedPortfolio,
  getSimulatedPortfolioPositions,
  getSimulatedPortfolioTimeline,
} from '@/lib/api/client';

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

  const [portfolio, initialPositions, initialTimeline] = await Promise.all([
    getSimulatedPortfolio(portfolioId),
    getSimulatedPortfolioPositions(portfolioId, { limit: 10, offset: 0 }),
    getSimulatedPortfolioTimeline(portfolioId, { limit: 10, offset: 0 }),
  ]);

  return (
    <PortfolioDetail
      portfolio={portfolio}
      initialPositions={initialPositions}
      initialTimeline={initialTimeline}
      locale={locale}
    />
  );
}
