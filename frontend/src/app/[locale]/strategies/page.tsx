import { notFound } from 'next/navigation';

import StrategyCatalog from '@/components/dashboard/strategy-catalog';
import { getResearchStrategies } from '@/lib/api/client';

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
