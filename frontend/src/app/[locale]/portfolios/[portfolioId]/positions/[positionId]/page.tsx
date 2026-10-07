import { notFound } from 'next/navigation';

import PositionDetail from '@/features/portfolios/position-detail';
import { getSimulatedPositionDetail } from '@/lib/api/client';

type PositionDetailPageProps = {
  params: Promise<{
    locale: string;
    portfolioId: string;
    positionId: string;
  }>;
};

export default async function PositionDetailPage({ params }: PositionDetailPageProps) {
  const { locale, portfolioId, positionId } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const report = await getSimulatedPositionDetail(portfolioId, positionId);
  return <PositionDetail locale={locale} report={report} />;
}
