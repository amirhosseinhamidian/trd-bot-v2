import { notFound } from 'next/navigation';

import {
  getMarketContextMonitoringSummary,
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

  const [summary, marketData, marketContext] = await Promise.all([
    getMonitoringSummary(),
    getMarketDataMonitoringSummary(),
    getMarketContextMonitoringSummary(),
  ]);

  return (
    <MonitoringDashboard
      locale={locale}
      marketContext={marketContext}
      marketData={marketData}
      summary={summary}
    />
  );
}
