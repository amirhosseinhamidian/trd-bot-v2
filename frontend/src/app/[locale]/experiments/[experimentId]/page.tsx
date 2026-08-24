import { notFound } from 'next/navigation';

import { ExperimentDetail } from '@/components/dashboard/experiment-detail';
import {
  ApiRequestError,
  getAcceptancePolicyPresets,
  getExperimentPerformanceSeries,
  getExperimentSummary,
} from '@/lib/api/client';

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

  const [experiment, acceptancePolicyPresets, performanceSeries] =
    await loadExperimentDetail(experimentId);

  return (
    <ExperimentDetail
      experiment={experiment}
      locale={locale}
      acceptancePolicyPresets={acceptancePolicyPresets}
      performanceSeries={performanceSeries}
    />
  );
}
