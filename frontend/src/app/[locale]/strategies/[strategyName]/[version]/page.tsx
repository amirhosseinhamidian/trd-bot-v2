import { notFound } from 'next/navigation';

import StrategyDetail from '@/components/dashboard/strategy-detail';
import { ApiRequestError, getExperiments, getResearchStrategyVersion } from '@/lib/api/client';

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

  try {
    const [strategy, experimentHistory] = await Promise.all([
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

    return (
      <StrategyDetail locale={locale} strategy={strategy} experimentHistory={experimentHistory} />
    );
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) {
      notFound();
    }
    throw error;
  }
}
