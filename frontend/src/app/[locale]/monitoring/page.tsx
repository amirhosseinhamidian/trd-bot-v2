import { notFound } from 'next/navigation';

import {
  getMarketDataMonitoringSummary,
  getMonitoringSummary,
} from '@/features/monitoring/api/client';
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

  const [summary, marketData] = await Promise.all([
    getMonitoringSummary(),
    getMarketDataMonitoringSummary(),
  ]);

  return <MonitoringDashboard locale={locale} marketData={marketData} summary={summary} />;
}
