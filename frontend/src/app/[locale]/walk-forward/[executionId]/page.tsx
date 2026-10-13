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
  searchParams?: Promise<{
    foldOffset?: string | string[];
  }>;
};

function parseFoldOffset(value: string | string[] | undefined): number {
  const candidate = Array.isArray(value) ? value[0] : value;

  if (candidate === undefined || !/^\d+$/.test(candidate)) {
    return 0;
  }

  const parsedValue = Number(candidate);
  return Number.isSafeInteger(parsedValue) ? parsedValue : 0;
}

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

export default async function WalkForwardDetailPage({
  params,
  searchParams,
}: WalkForwardDetailPageProps) {
  const { executionId, locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const [run, stability] = await loadWalkForwardDetail(executionId);
  const foldOffset = parseFoldOffset((await searchParams)?.foldOffset);

  return (
    <WalkForwardDetail locale={locale} run={run} stability={stability} foldOffset={foldOffset} />
  );
}
