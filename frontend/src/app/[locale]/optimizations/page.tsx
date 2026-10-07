import { notFound } from 'next/navigation';

import OptimizationCatalog from '@/features/optimizations/optimization-catalog';
import { getOptimizationExecutions } from '@/lib/api/client';
import {
  parseOptimizationExecutionId,
  type OptimizationSearchParams,
} from '@/lib/optimizations/run-params';

type OptimizationsPageProps = {
  params: Promise<{
    locale: string;
  }>;
  searchParams: Promise<OptimizationSearchParams>;
};

export default async function OptimizationsPage({ params, searchParams }: OptimizationsPageProps) {
  const { locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const initialExecutionId = parseOptimizationExecutionId(await searchParams);
  const initialPage = await getOptimizationExecutions({
    limit: 12,
    offset: 0,
  });

  return (
    <OptimizationCatalog
      locale={locale}
      initialPage={initialPage}
      initialExecutionId={initialExecutionId}
    />
  );
}
