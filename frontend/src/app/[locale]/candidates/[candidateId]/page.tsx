import { notFound } from 'next/navigation';

import CandidateDetail from '@/components/dashboard/candidate-detail';
import { getCandidateLineage, getCandidateProjection } from '@/lib/api/client';

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

  const [candidate, initialLineage] = await Promise.all([
    getCandidateProjection(candidateId),
    getCandidateLineage(candidateId, {
      limit: 10,
      offset: 0,
    }),
  ]);

  return <CandidateDetail candidate={candidate} initialLineage={initialLineage} locale={locale} />;
}
