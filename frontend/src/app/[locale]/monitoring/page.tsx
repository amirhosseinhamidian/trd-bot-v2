import { notFound } from 'next/navigation';

import { getMonitoringSummary } from '@/features/monitoring/api/client';
import MonitoringDashboard from '@/features/monitoring/monitoring-dashboard';

type MonitoringPageProps = {
  params: Promise<{
    locale: string;
  }>;
};

export default async function MonitoringPage({ params }: MonitoringPageProps) {
  const { locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const summary = await getMonitoringSummary();

  return <MonitoringDashboard locale={locale} summary={summary} />;
}
