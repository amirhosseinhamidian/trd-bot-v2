import { notFound } from 'next/navigation';

import PortfolioCatalog from '@/components/dashboard/portfolio-catalog';
import { getSimulatedPortfolios } from '@/lib/api/client';

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
