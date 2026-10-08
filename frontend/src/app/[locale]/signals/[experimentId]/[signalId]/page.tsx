import { notFound } from 'next/navigation';

import { getExperimentSummary } from '@/features/experiments/api/client';
import { getExperimentSignal } from '@/features/signals/api/client';
import SignalDetail from '@/features/signals/signal-detail';
import { ApiRequestError } from '@/lib/api/core/transport';

type SignalDetailPageProps = {
  params: Promise<{
    locale: string;
    experimentId: string;
    signalId: string;
  }>;
};

async function loadSignalDetail(experimentId: string, signalId: string) {
  try {
    return await Promise.all([
      getExperimentSummary(experimentId),
      getExperimentSignal(experimentId, signalId),
    ]);
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) {
      notFound();
    }

    throw error;
  }
}

export default async function SignalDetailPage({ params }: SignalDetailPageProps) {
  const { locale, experimentId, signalId } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const [experiment, signal] = await loadSignalDetail(experimentId, signalId);

  return <SignalDetail experiment={experiment} locale={locale} signal={signal} />;
}
