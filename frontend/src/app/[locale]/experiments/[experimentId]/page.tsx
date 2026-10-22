import { notFound } from 'next/navigation';

import {
  getAcceptancePolicyPresets,
  getExperimentAnalytics,
  getExperimentPerformanceSeries,
  getExperimentSummary,
} from '@/features/experiments/api/client';
import { ExperimentDetail } from '@/features/experiments/experiment-detail';
import { ApiRequestError } from '@/lib/api/core/transport';

type ExperimentDetailPageProps = {
  params: Promise<{
    experimentId: string;
    locale: string;
  }>;
};

async function loadExperimentDetail(experimentId: string) {
  try {
    return await Promise.all([
      getExperimentSummary(experimentId),
      getAcceptancePolicyPresets(),
      getExperimentPerformanceSeries(experimentId),
      getExperimentAnalytics(experimentId),
    ]);
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) {
      notFound();
    }

    throw error;
  }
}

export default async function ExperimentDetailPage({ params }: ExperimentDetailPageProps) {
  const { experimentId, locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const [experiment, acceptancePolicyPresets, performanceSeries, analytics] =
    await loadExperimentDetail(experimentId);

  return (
    <ExperimentDetail
      experiment={experiment}
      locale={locale}
      acceptancePolicyPresets={acceptancePolicyPresets}
      analytics={analytics}
      performanceSeries={performanceSeries}
    />
  );
}
