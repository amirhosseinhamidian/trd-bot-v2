import { notFound } from 'next/navigation';

import MonitoringDashboard from '@/components/dashboard/monitoring-dashboard';
import { getMonitoringSummary } from '@/lib/api/client';

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
