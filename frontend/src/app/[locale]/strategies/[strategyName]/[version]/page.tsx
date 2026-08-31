import { notFound } from 'next/navigation';

import StrategyDetail from '@/components/dashboard/strategy-detail';
import { getResearchStrategies } from '@/lib/api/client';
import { findStrategyMetadata } from '@/lib/strategies/catalog';

type StrategyDetailPageProps = {
  params: Promise<{
    locale: string;
    strategyName: string;
    version: string;
  }>;
};

export default async function StrategyDetailPage({ params }: StrategyDetailPageProps) {
  const { locale, strategyName, version } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const strategy = findStrategyMetadata(await getResearchStrategies(), strategyName, version);

  if (strategy === null) {
    notFound();
  }

  return <StrategyDetail locale={locale} strategy={strategy} />;
}
