import { notFound } from 'next/navigation';

import WalkForwardCatalog from '@/components/dashboard/walk-forward-catalog';
import { getWalkForwardRuns } from '@/lib/api/client';

type WalkForwardPageProps = {
  params: Promise<{
    locale: string;
  }>;
};

export default async function WalkForwardPage({ params }: WalkForwardPageProps) {
  const { locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const initialPage = await getWalkForwardRuns({
    sortBy: 'created_at',
    sortDirection: 'desc',
    limit: 12,
    offset: 0,
  });

  return <WalkForwardCatalog locale={locale} initialPage={initialPage} />;
}
