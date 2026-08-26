import { notFound } from 'next/navigation';

import WalkForwardCatalog from '@/components/dashboard/walk-forward-catalog';
import { getWalkForwardRuns } from '@/lib/api/client';
import {
  parseWalkForwardExecutionId,
  type WalkForwardRunSearchParams,
} from '@/lib/walk-forward/run-params';

type WalkForwardPageProps = {
  params: Promise<{
    locale: string;
  }>;
  searchParams: Promise<WalkForwardRunSearchParams>;
};

export default async function WalkForwardPage({ params, searchParams }: WalkForwardPageProps) {
  const { locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const resolvedSearchParams = await searchParams;
  const initialExecutionId = parseWalkForwardExecutionId(resolvedSearchParams);

  const initialPage = await getWalkForwardRuns({
    sortBy: 'created_at',
    sortDirection: 'desc',
    limit: 12,
    offset: 0,
  });

  return (
    <WalkForwardCatalog
      locale={locale}
      initialPage={initialPage}
      initialExecutionId={initialExecutionId}
    />
  );
}
