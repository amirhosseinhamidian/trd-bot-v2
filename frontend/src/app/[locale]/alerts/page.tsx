import { notFound } from 'next/navigation';

import {
  getAlertExpirySummary,
  getAlertPublicationPolicy,
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

  const [initialPage, initialSummary, initialPolicy, initialExpirySummary] = await Promise.all([
    getAlerts({ limit: 12, offset: 0 }),
    getAlertSummary(),
    getAlertPublicationPolicy(),
    getAlertExpirySummary(),
  ]);

  return (
    <AlertCenter
      initialPage={initialPage}
      initialSummary={initialSummary}
      initialPolicy={initialPolicy}
      initialExpirySummary={initialExpirySummary}
      locale={locale}
    />
  );
}
