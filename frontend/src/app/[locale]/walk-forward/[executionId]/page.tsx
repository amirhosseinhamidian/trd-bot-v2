import { notFound } from 'next/navigation';

import { WalkForwardDetail } from '@/components/dashboard/walk-forward-detail';
import {
  ApiRequestError,
  getWalkForwardRunSummary,
  getWalkForwardStabilityReport,
} from '@/lib/api/client';

type WalkForwardDetailPageProps = {
  params: Promise<{
    executionId: string;
    locale: string;
  }>;
};

async function loadWalkForwardDetail(executionId: string) {
  try {
    return await Promise.all([
      getWalkForwardRunSummary(executionId),
      getWalkForwardStabilityReport(executionId),
    ]);
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) {
      notFound();
    }

    throw error;
  }
}

export default async function WalkForwardDetailPage({ params }: WalkForwardDetailPageProps) {
  const { executionId, locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const [run, stability] = await loadWalkForwardDetail(executionId);

  return <WalkForwardDetail locale={locale} run={run} stability={stability} />;
}
