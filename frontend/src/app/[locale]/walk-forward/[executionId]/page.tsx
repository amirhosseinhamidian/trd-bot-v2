import { notFound } from 'next/navigation';

import {
  getWalkForwardRunSummary,
  getWalkForwardStabilityReport,
} from '@/features/walk-forward/api/client';
import { WalkForwardDetail } from '@/features/walk-forward/walk-forward-detail';
import { ApiRequestError } from '@/lib/api/core/transport';

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
