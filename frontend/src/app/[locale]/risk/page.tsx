import { notFound } from 'next/navigation';

import { getSimulatedPortfolios } from '@/features/portfolios/api/client';
import { getLatestDecisionEvaluation } from '@/features/decision-intelligence/api/client';
import { getRiskDashboard } from '@/features/risk/api/client';
import RiskDashboard from '@/features/risk/risk-dashboard';

type RiskPageProps = {
  params: Promise<{
    locale: string;
  }>;
};

export default async function RiskPage({ params }: RiskPageProps) {
  const { locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const [initialReport, portfolioPage, decisionEvidence] = await Promise.all([
    getRiskDashboard(),
    getSimulatedPortfolios({ limit: 100, offset: 0 }),
    getLatestDecisionEvaluation({ stage: 'risk_gate' }),
  ]);

  return (
    <RiskDashboard
      initialReport={initialReport}
      locale={locale}
      portfolios={portfolioPage.items}
      decisionEvidence={decisionEvidence}
    />
  );
}
