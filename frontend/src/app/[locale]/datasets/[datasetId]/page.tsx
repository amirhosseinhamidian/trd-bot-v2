import { notFound } from 'next/navigation';

import DatasetDetail from '@/components/dashboard/dataset-detail';
import { ApiRequestError, getDatasetCandles, getDatasetSummary } from '@/lib/api/client';

type DatasetDetailPageProps = {
  params: Promise<{
    locale: string;
    datasetId: string;
  }>;
};

async function loadDatasetDetail(datasetId: string) {
  try {
    return await Promise.all([
      getDatasetSummary(datasetId),
      getDatasetCandles(datasetId, {
        limit: 25,
        offset: 0,
      }),
    ]);
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) {
      notFound();
    }

    throw error;
  }
}

export default async function DatasetDetailPage({ params }: DatasetDetailPageProps) {
  const { locale, datasetId } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const [dataset, initialCandlesPage] = await loadDatasetDetail(datasetId);

  return (
    <DatasetDetail locale={locale} dataset={dataset} initialCandlesPage={initialCandlesPage} />
  );
}
