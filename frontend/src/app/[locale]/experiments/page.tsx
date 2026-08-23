import { notFound } from 'next/navigation';

import ExperimentCatalog from '@/components/dashboard/experiment-catalog';
import { getExperiments } from '@/lib/api/client';

type ExperimentsPageProps = {
  params: Promise<{
    locale: string;
  }>;
};

export default async function ExperimentsPage({ params }: ExperimentsPageProps) {
  const { locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const initialPage = await getExperiments({
    sortBy: 'created_at',
    sortDirection: 'desc',
    limit: 12,
    offset: 0,
  });

  return <ExperimentCatalog locale={locale} initialPage={initialPage} />;
}
