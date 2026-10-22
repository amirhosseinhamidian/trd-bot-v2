import { notFound } from 'next/navigation';

import { getCandidateProjections } from '@/features/candidates/api/client';
import CandidateCatalog from '@/features/candidates/candidate-catalog';

type CandidatesPageProps = {
  params: Promise<{
    locale: string;
  }>;
};

export default async function CandidatesPage({ params }: CandidatesPageProps) {
  const { locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  const initialPage = await getCandidateProjections({
    limit: 12,
    offset: 0,
  });

  return <CandidateCatalog locale={locale} initialPage={initialPage} />;
}
