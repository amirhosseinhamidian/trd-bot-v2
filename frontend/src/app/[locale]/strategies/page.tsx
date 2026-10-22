import { notFound } from 'next/navigation';

import { getResearchStrategies } from '@/features/strategies/api/client';
import StrategyCatalog from '@/features/strategies/strategy-catalog';

type StrategiesPageProps = {
  params: Promise<{
    locale: string;
  }>;
};

export default async function StrategiesPage({ params }: StrategiesPageProps) {
  const { locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const strategies = await getResearchStrategies();

  return <StrategyCatalog locale={locale} strategies={strategies} />;
}
