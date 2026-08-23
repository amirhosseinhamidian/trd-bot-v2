import { notFound } from 'next/navigation';

import OverviewDashboard from '@/components/dashboard/overview-dashboard';
import { getResearchActivity, getResearchOverview } from '@/lib/api/client';

type LocalePageProps = {
  params: Promise<{
    locale: string;
  }>;
};

export default async function LocalePage({ params }: LocalePageProps) {
  const { locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const [overview, activityPage] = await Promise.all([
    getResearchOverview(),
    getResearchActivity({
      limit: 10,
      offset: 0,
    }),
  ]);

  return <OverviewDashboard locale={locale} overview={overview} activityPage={activityPage} />;
}
