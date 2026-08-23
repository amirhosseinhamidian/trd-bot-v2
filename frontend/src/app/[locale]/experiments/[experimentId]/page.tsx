import { notFound } from 'next/navigation';

import { ExperimentDetail } from '@/components/dashboard/experiment-detail';
import type { ExperimentDetailLocale } from '@/components/dashboard/experiment-detail-copy';
import { ApiRequestError, getExperimentSummary } from '@/lib/api/client';

type ExperimentDetailPageProps = {
  params: Promise<{
    experimentId: string;
    locale: string;
  }>;
};

function normalizeLocale(locale: string): ExperimentDetailLocale {
  return locale === 'fa' ? 'fa' : 'en';
}

export default async function ExperimentDetailPage({ params }: ExperimentDetailPageProps) {
  const { experimentId, locale } = await params;
  const normalizedLocale = normalizeLocale(locale);

  try {
    const experiment = await getExperimentSummary(experimentId);

    return <ExperimentDetail experiment={experiment} locale={normalizedLocale} />;
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) {
      notFound();
    }

    throw error;
  }
}
