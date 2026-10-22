import { notFound } from 'next/navigation';

import {
  getAlertExpirySummary,
  getAlertOutcomes,
  getAlertOutcomeSummary,
  getAlertPublicationPolicy,
  getAlertSimulations,
  getAlertSimulationSummary,
  getAlerts,
  getAlertSummary,
} from '@/features/alerts/api/client';
import AlertCenter from '@/features/alerts/alert-center';

type AlertsPageProps = {
  params: Promise<{ locale: string }>;
};

export default async function AlertsPage({ params }: AlertsPageProps) {
  const { locale } = await params;
  if (locale !== 'fa' && locale !== 'en') notFound();

  const [
    initialPage,
    initialSummary,
    initialPolicy,
    initialExpirySummary,
    initialSimulations,
    initialSimulationSummary,
    initialOutcomes,
    initialOutcomeSummary,
  ] = await Promise.all([
    getAlerts({ limit: 12, offset: 0 }),
    getAlertSummary(),
    getAlertPublicationPolicy(),
    getAlertExpirySummary(),
    getAlertSimulations({ limit: 100, offset: 0 }),
    getAlertSimulationSummary(),
    getAlertOutcomes({ limit: 100, offset: 0 }),
    getAlertOutcomeSummary(),
  ]);

  return (
    <AlertCenter
      initialPage={initialPage}
      initialSummary={initialSummary}
      initialPolicy={initialPolicy}
      initialExpirySummary={initialExpirySummary}
      initialSimulations={initialSimulations.items}
      initialSimulationSummary={initialSimulationSummary}
      initialOutcomes={initialOutcomes.items}
      initialOutcomeSummary={initialOutcomeSummary}
      locale={locale}
    />
  );
}
