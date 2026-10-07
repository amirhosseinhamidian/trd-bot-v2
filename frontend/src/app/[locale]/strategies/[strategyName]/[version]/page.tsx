import { notFound } from 'next/navigation';

import { getResearchStrategyVersion } from '@/features/strategies/api/client';
import StrategyDetail from '@/features/strategies/strategy-detail';
import { getExperiments } from '@/lib/api/client';
import { ApiRequestError } from '@/lib/api/core/transport';

type StrategyDetailPageProps = {
  params: Promise<{
    locale: string;
    strategyName: string;
    version: string;
  }>;
};

async function loadStrategyDetail(strategyName: string, version: string) {
  try {
    return await Promise.all([
      getResearchStrategyVersion(strategyName, version),
      getExperiments({
        strategyName,
        strategyVersion: version,
        sortBy: 'created_at',
        sortDirection: 'desc',
        limit: 5,
        offset: 0,
      }),
    ]);
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) {
      notFound();
    }

    throw error;
  }
}

export default async function StrategyDetailPage({ params }: StrategyDetailPageProps) {
  const { locale, strategyName, version } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const [strategy, experimentHistory] = await loadStrategyDetail(strategyName, version);

  return (
    <StrategyDetail locale={locale} strategy={strategy} experimentHistory={experimentHistory} />
  );
}
