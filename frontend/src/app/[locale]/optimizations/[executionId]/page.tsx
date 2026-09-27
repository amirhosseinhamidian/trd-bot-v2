import { notFound } from 'next/navigation';

import OptimizationDetail from '@/components/dashboard/optimization-detail';
import { ApiRequestError, getOptimizationExecution } from '@/lib/api/client';

type OptimizationDetailPageProps = {
  params: Promise<{
    executionId: string;
    locale: string;
  }>;
};

async function loadOptimizationExecution(executionId: string) {
  try {
    return await getOptimizationExecution(executionId);
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) {
      notFound();
    }

    throw error;
  }
}

export default async function OptimizationDetailPage({ params }: OptimizationDetailPageProps) {
  const { executionId, locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const execution = await loadOptimizationExecution(executionId);

  return <OptimizationDetail initialExecution={execution} locale={locale} />;
}
