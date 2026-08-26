import { notFound } from 'next/navigation';

import CandidateCatalog from '@/components/dashboard/candidate-catalog';
import { getCandidateProjections } from '@/lib/api/client';

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
