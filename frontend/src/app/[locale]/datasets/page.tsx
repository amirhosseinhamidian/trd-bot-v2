import { notFound } from 'next/navigation';

import DatasetCatalog from '@/components/dashboard/dataset-catalog';
import { getDatasets } from '@/lib/api/client';

type DatasetsPageProps = {
  params: Promise<{
    locale: string;
  }>;
};

export default async function DatasetsPage({ params }: DatasetsPageProps) {
  const { locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const initialPage = await getDatasets({
    sortBy: 'created_at',
    sortDirection: 'desc',
    limit: 12,
    offset: 0,
  });

  return <DatasetCatalog locale={locale} initialPage={initialPage} />;
}
