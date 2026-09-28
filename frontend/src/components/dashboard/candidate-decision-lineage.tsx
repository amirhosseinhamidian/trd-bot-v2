import Link from 'next/link';

import {
  getCandidateDetailCopy,
  type CandidateLineageReason,
} from '@/components/dashboard/candidate-detail-copy';
import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { Badge, Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui';
import type {
  CandidateDecisionLineage,
  CandidateDecisionLineageNode,
  CandidateExitReason,
  CandidateRiskDecision,
} from '@/lib/api/types';

type CandidateDecisionLineageViewProps = {
  lineage: CandidateDecisionLineage;
  locale: DashboardLocale;
};

function nodeHref(
  node: CandidateDecisionLineageNode,
  experimentId: string | undefined,
  locale: DashboardLocale,
): string | null {
  if (node.kind === 'risk') {
    return '#risk-decision';
  }
  if (node.status !== 'available' || node.resource_id === null) {
    return null;
  }
  if (node.kind === 'dataset') {
    return `/${locale}/datasets/${encodeURIComponent(node.resource_id)}`;
  }
  if (node.kind === 'experiment') {
    return `/${locale}/experiments/${encodeURIComponent(node.resource_id)}`;
  }
  if (node.kind === 'signal' && experimentId) {
    const encodedExperimentId = encodeURIComponent(experimentId);
    const encodedSignalId = encodeURIComponent(node.resource_id);
    return `/${locale}/signals/${encodedExperimentId}/${encodedSignalId}`;
  }
  if (node.kind === 'candidate') {
    return `/${locale}/candidates/${encodeURIComponent(node.resource_id)}`;
  }
  if ((node.kind === 'position' || node.kind === 'exit') && node.portfolio_id) {
    const encodedPortfolioId = encodeURIComponent(node.portfolio_id);
    const encodedPositionId = encodeURIComponent(node.resource_id);
    return `/${locale}/portfolios/${encodedPortfolioId}/positions/${encodedPositionId}`;
  }
  return null;
}

export default function CandidateDecisionLineageView({
  lineage,
  locale,
}: CandidateDecisionLineageViewProps) {
  const copy = getCandidateDetailCopy(locale);
  const experimentId = lineage.nodes.find((node) => node.kind === 'experiment')?.resource_id;

  function outcome(node: CandidateDecisionLineageNode): string | null {
    if (node.outcome === null) {
      return null;
    }
    if (node.kind === 'risk') {
      return copy.riskDecisions[node.outcome as CandidateRiskDecision] ?? node.outcome;
    }
    if (node.kind === 'exit') {
      return copy.exitReasons[node.outcome as CandidateExitReason] ?? node.outcome;
    }
    return node.outcome;
  }

  function reason(reasonCode: string | null): string | null {
    if (reasonCode === null) {
      return null;
    }
    if (reasonCode in copy.lineageReasons) {
      return copy.lineageReasons[reasonCode as CandidateLineageReason];
    }
    return reasonCode;
  }

  return (
    <section>
      <div>
        <h2 className="text-xl font-semibold text-app-foreground">{copy.decisionLineageTitle}</h2>
        <p className="mt-2 text-sm text-app-muted">{copy.decisionLineageDescription}</p>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {lineage.nodes.map((node) => {
          const href = nodeHref(node, experimentId ?? undefined, locale);
          const outcomeLabel = outcome(node);
          const reasonLabel = reason(node.reason);

          return (
            <Card key={node.kind} className="bg-app-surface-muted">
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <CardTitle className="text-base">{copy.lineageKinds[node.kind]}</CardTitle>
                  <Badge
                    variant={
                      node.status === 'available'
                        ? 'success'
                        : node.status === 'not_created'
                          ? 'neutral'
                          : 'warning'
                    }
                  >
                    {copy.lineageStatuses[node.status]}
                  </Badge>
                </div>
                {outcomeLabel ? <CardDescription>{outcomeLabel}</CardDescription> : null}
              </CardHeader>
              <CardContent className="space-y-3">
                {node.resource_id ? (
                  <p dir="ltr" className="text-left text-xs font-semibold break-all text-app-muted">
                    {node.resource_id}
                  </p>
                ) : null}
                {reasonLabel ? (
                  <p className="text-xs leading-5 text-app-muted">{reasonLabel}</p>
                ) : null}
                {href ? (
                  <Link
                    href={href}
                    aria-label={`${copy.viewResource}: ${
                      node.resource_id ?? copy.lineageKinds[node.kind]
                    }`}
                    className="inline-flex text-sm font-semibold text-app-accent hover:opacity-80"
                  >
                    {copy.viewResource}
                  </Link>
                ) : null}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </section>
  );
}
