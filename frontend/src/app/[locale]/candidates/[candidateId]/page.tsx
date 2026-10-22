import { notFound } from 'next/navigation';

import { getCandidateLineage, getCandidateProjection } from '@/features/candidates/api/client';
import { getLatestDecisionEvaluation } from '@/features/decision-intelligence/api/client';
import CandidateDetail from '@/features/candidates/candidate-detail';

type CandidateDetailPageProps = {
  params: Promise<{
    locale: string;
    candidateId: string;
  }>;
};

export default async function CandidateDetailPage({ params }: CandidateDetailPageProps) {
  const { locale, candidateId } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const candidate = await getCandidateProjection(candidateId);
  const [initialLineage, decisionEvidence] = await Promise.all([
    getCandidateLineage(candidateId, {
      limit: 10,
      offset: 0,
    }),
    getLatestDecisionEvaluation({ signalId: candidate.candidate.signal_id }),
  ]);

  return (
    <CandidateDetail
      candidate={candidate}
      initialLineage={initialLineage}
      locale={locale}
      decisionEvidence={decisionEvidence}
    />
  );
}
