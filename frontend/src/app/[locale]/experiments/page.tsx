import { notFound } from 'next/navigation';

import ExperimentCatalog from '@/components/dashboard/experiment-catalog';
import { getExperiments } from '@/lib/api/client';
import {
  parseExperimentRunSearchParams,
  type ExperimentRunSearchParams,
} from '@/lib/experiments/run-params';

type ExperimentsPageProps = {
  params: Promise<{
    locale: string;
  }>;
  searchParams: Promise<ExperimentRunSearchParams>;
};

export default async function ExperimentsPage({ params, searchParams }: ExperimentsPageProps) {
  const { locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const resolvedSearchParams = await searchParams;

  const initialRunValues = parseExperimentRunSearchParams(resolvedSearchParams);

  const initialPage = await getExperiments({
    sortBy: 'created_at',
    sortDirection: 'desc',
    limit: 12,
    offset: 0,
  });

  return (
    <ExperimentCatalog
      locale={locale}
      initialPage={initialPage}
      initialRunValues={initialRunValues}
    />
  );
}
