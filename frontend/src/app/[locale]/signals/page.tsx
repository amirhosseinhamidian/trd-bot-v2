import { notFound } from 'next/navigation';

import SignalCatalog from '@/components/dashboard/signal-catalog';
import { getExperiments, getExperimentSignals } from '@/lib/api/client';
import type { Page, StrategySignal } from '@/lib/api/types';

type SignalsPageProps = {
  params: Promise<{
    locale: string;
  }>;
};

function emptySignalPage(): Page<StrategySignal> {
  return {
    items: [],
    total: 0,
    limit: 20,
    offset: 0,
    count: 0,
    has_next: false,
    has_previous: false,
  };
}

export default async function SignalsPage({ params }: SignalsPageProps) {
  const { locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const experimentsPage = await getExperiments({
    sortBy: 'created_at',
    sortDirection: 'desc',
    limit: 100,
    offset: 0,
  });

  const initialExperimentId = experimentsPage.items[0]?.experiment_id ?? '';

  const initialPage = initialExperimentId
    ? await getExperimentSignals(initialExperimentId, {
        sortDirection: 'desc',
        limit: 20,
        offset: 0,
      })
    : emptySignalPage();

  return (
    <SignalCatalog
      experiments={experimentsPage.items}
      initialExperimentId={initialExperimentId}
      initialPage={initialPage}
      locale={locale}
    />
  );
}
