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

export default async function WalkForwardDetailPage({ params }: WalkForwardDetailPageProps) {
  const { executionId, locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  try {
    const [run, stability] = await Promise.all([
      getWalkForwardRunSummary(executionId),
      getWalkForwardStabilityReport(executionId),
    ]);

    return <WalkForwardDetail locale={locale} run={run} stability={stability} />;
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) {
      notFound();
    }

    throw error;
  }
}
