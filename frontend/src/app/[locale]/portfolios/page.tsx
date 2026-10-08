import { notFound } from 'next/navigation';

import { getSimulatedPortfolios } from '@/features/portfolios/api/client';
import PortfolioCatalog from '@/features/portfolios/portfolio-catalog';

type PortfoliosPageProps = {
  params: Promise<{
    locale: string;
  }>;
};

export default async function PortfoliosPage({ params }: PortfoliosPageProps) {
  const { locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const initialPage = await getSimulatedPortfolios({
    limit: 12,
    offset: 0,
  });

  return <PortfolioCatalog locale={locale} initialPage={initialPage} />;
}
