'use client';

import { useRef, useState } from 'react';

import { PageFrame } from '@/components/platform/page-frame';
import { PageHeader } from '@/components/platform/page-header';
import {
  AdvancedDisclosure,
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  Pagination,
  Spinner,
} from '@/components/ui';
import type { BadgeVariant } from '@/components/ui';
import { getMarketContexts } from '@/features/market-context/api/client';
import type {
  MarketContextProductView,
  MarketTrendRegime,
  MarketVolatilityRegime,
} from '@/features/market-context/api/types';
import { getMarketContextCopy } from '@/features/market-context/market-context-copy';
import type { Page } from '@/lib/api/core/types';
import type { PlatformLocale } from '@/platform/i18n';

const PAGE_SIZE = 12;

type MarketContextDashboardProps = {
  initialPage: Page<MarketContextProductView>;
  locale: PlatformLocale;
};

const trendVariants: Record<MarketTrendRegime, BadgeVariant> = {
  trending_up: 'success',
  trending_down: 'danger',
  ranging: 'info',
  undetermined: 'neutral',
};

const volatilityVariants: Record<MarketVolatilityRegime, BadgeVariant> = {
  low: 'success',
  normal: 'info',
  high: 'danger',
  undetermined: 'neutral',
};

function numberLocale(locale: PlatformLocale): string {
  return locale === 'fa' ? 'fa-IR' : 'en-US';
}

function formatNumber(value: number, locale: PlatformLocale): string {
  return new Intl.NumberFormat(numberLocale(locale)).format(value);
}

function formatDecimal(value: string, locale: PlatformLocale): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return value;
  return new Intl.NumberFormat(numberLocale(locale), { maximumFractionDigits: 12 }).format(parsed);
}

function formatPercent(value: string, locale: PlatformLocale): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return value;
  return new Intl.NumberFormat(numberLocale(locale), {
    style: 'percent',
    maximumFractionDigits: 2,
  }).format(parsed);
}

function formatDate(value: string, locale: PlatformLocale): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(numberLocale(locale), {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

export default function MarketContextDashboard({
  initialPage,
  locale,
}: MarketContextDashboardProps) {
  const copy = getMarketContextCopy(locale);
  const [page, setPage] = useState(initialPage);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const requestSequence = useRef(0);
  const consumableCount = page.items.filter((item) => item.consumable).length;

  async function loadPage(offset: number): Promise<void> {
    const requestId = ++requestSequence.current;
    setIsLoading(true);
    setHasError(false);
    try {
      const result = await getMarketContexts({ limit: PAGE_SIZE, offset });
      if (requestId === requestSequence.current) setPage(result);
    } catch {
      if (requestId === requestSequence.current) setHasError(true);
    } finally {
      if (requestId === requestSequence.current) setIsLoading(false);
    }
  }

  return (
    <PageFrame>
      <PageHeader
        eyebrow={copy.eyebrow}
        title={copy.title}
        description={copy.description}
        actions={
          <>
            <Badge variant="neutral">{copy.readOnly}</Badge>
            <Badge variant="info">
              {copy.total}: {formatNumber(page.total, locale)}
            </Badge>
          </>
        }
      >
        <p className="rounded-2xl border border-app-info-border bg-app-info-soft p-4 text-sm leading-7 text-app-info">
          {copy.disclaimer}
        </p>
      </PageHeader>

      <section className="grid gap-4 sm:grid-cols-2" aria-label={copy.title}>
        <Card>
          <CardContent className="p-5">
            <p className="text-sm text-app-muted">{copy.available}</p>
            <p className="mt-2 text-3xl font-bold text-app-foreground">
              {formatNumber(consumableCount, locale)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <p className="text-sm text-app-muted">{copy.unavailable}</p>
            <p className="mt-2 text-3xl font-bold text-app-foreground">
              {formatNumber(page.items.length - consumableCount, locale)}
            </p>
          </CardContent>
        </Card>
      </section>

      <section className="relative min-h-64" aria-busy={isLoading}>
        {isLoading ? (
          <div className="absolute inset-0 z-20 flex items-center justify-center rounded-2xl bg-app-overlay backdrop-blur-sm">
            <Spinner size="lg" label={copy.loading} className="text-app-accent" />
          </div>
        ) : null}

        {hasError ? (
          <ErrorState
            title={copy.errorTitle}
            description={copy.errorDescription}
            retryLabel={copy.retry}
            onRetry={() => void loadPage(page.offset)}
          />
        ) : page.items.length === 0 ? (
          <EmptyState title={copy.emptyTitle} description={copy.emptyDescription} />
        ) : (
          <div className="grid gap-5 xl:grid-cols-2">
            {page.items.map((view) => {
              const assessment = view.assessment;
              const confidence = Number(assessment.confidence);
              const confidencePercent = Number.isFinite(confidence)
                ? Math.min(Math.max(confidence * 100, 0), 100)
                : 0;

              return (
                <Card key={assessment.assessment_id} className="min-w-0 overflow-hidden">
                  <CardHeader className="border-b border-app-border">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="min-w-0">
                        <CardTitle dir="ltr" className="text-left">
                          {assessment.pair.base_asset}/{assessment.pair.quote_asset}
                        </CardTitle>
                        <CardDescription dir="ltr" className="mt-2 text-left break-all">
                          {copy.source}: {assessment.source}
                        </CardDescription>
                      </div>
                      <Badge variant={view.consumable ? 'success' : 'danger'}>
                        {view.consumable ? copy.available : copy.unavailable}
                      </Badge>
                    </div>
                  </CardHeader>

                  <CardContent className="space-y-5 pt-6">
                    <div className="grid gap-3 sm:grid-cols-3">
                      <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
                        <p className="text-xs text-app-muted">{copy.trend}</p>
                        <Badge className="mt-3" variant={trendVariants[assessment.trend]}>
                          {copy.trends[assessment.trend]}
                        </Badge>
                      </div>
                      <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
                        <p className="text-xs text-app-muted">{copy.volatility}</p>
                        <Badge className="mt-3" variant={volatilityVariants[assessment.volatility]}>
                          {copy.volatilityLevels[assessment.volatility]}
                        </Badge>
                      </div>
                      <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
                        <p className="text-xs text-app-muted">{copy.confidence}</p>
                        <p dir="ltr" className="mt-2 text-left text-xl font-bold">
                          {formatPercent(assessment.confidence, locale)}
                        </p>
                        <div
                          role="progressbar"
                          aria-label={copy.confidence}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-valuenow={Math.round(confidencePercent)}
                          className="mt-3 h-1.5 overflow-hidden rounded-full bg-app-border"
                        >
                          <div
                            className="h-full rounded-full bg-app-accent"
                            style={{ width: `${confidencePercent}%` }}
                          />
                        </div>
                      </div>
                    </div>

                    {!view.consumable ? (
                      <div className="rounded-xl border border-app-warning-border bg-app-warning-soft p-4 text-sm text-app-warning">
                        <p className="font-semibold">{copy.unavailableTitle}</p>
                        <ul className="mt-2 list-inside list-disc space-y-1 leading-6">
                          {view.unavailable_reasons.map((reason) => (
                            <li key={reason}>{copy.unavailableReasons[reason]}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}

                    <dl className="grid gap-4 text-sm sm:grid-cols-2">
                      <div>
                        <dt className="text-xs text-app-muted">{copy.status}</dt>
                        <dd className="mt-1 font-medium text-app-foreground">
                          {copy.assessmentStatuses[assessment.status]}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">{copy.asOf}</dt>
                        <dd className="mt-1 text-app-foreground">
                          {formatDate(assessment.as_of, locale)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">{copy.expectedAsOf}</dt>
                        <dd className="mt-1 text-app-foreground">
                          {formatDate(view.expected_as_of, locale)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">{copy.assessedAt}</dt>
                        <dd className="mt-1 text-app-foreground">
                          {formatDate(assessment.assessed_at, locale)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">{copy.expiresAt}</dt>
                        <dd className="mt-1 text-app-foreground">
                          {formatDate(assessment.expires_at, locale)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">
                          {view.consumable ? copy.expiresIn : copy.boundaryLag}
                        </dt>
                        <dd dir="ltr" className="mt-1 text-left text-app-foreground tabular-nums">
                          {formatNumber(
                            view.consumable ? view.seconds_until_expiry : view.boundary_lag_seconds,
                            locale,
                          )}{' '}
                          {copy.seconds}
                        </dd>
                      </div>
                    </dl>

                    <AdvancedDisclosure
                      title={copy.evidenceTitle}
                      description={copy.evidenceDescription}
                    >
                      <div className="grid gap-3 sm:grid-cols-2">
                        {assessment.evidence.map((evidence) => (
                          <article
                            key={evidence.feature_key}
                            className="min-w-0 rounded-xl border border-app-border bg-app-surface-muted p-4"
                          >
                            <p className="text-xs text-app-muted">{copy.feature}</p>
                            <h4 className="mt-1 text-sm font-semibold break-words text-app-foreground">
                              {copy.featureLabels[evidence.feature_key] ?? evidence.feature_key}
                            </h4>
                            <dl className="mt-4 space-y-2 text-xs">
                              <div className="flex justify-between gap-3">
                                <dt className="text-app-muted">{copy.value}</dt>
                                <dd dir="ltr" className="text-left font-medium tabular-nums">
                                  {formatDecimal(evidence.value, locale)}
                                </dd>
                              </div>
                              <div className="flex justify-between gap-3">
                                <dt className="text-app-muted">{copy.timeframe}</dt>
                                <dd dir="ltr">{evidence.timeframe}</dd>
                              </div>
                              <div className="min-w-0">
                                <dt className="text-app-muted">{copy.calculation}</dt>
                                <dd dir="ltr" className="mt-1 text-left break-all">
                                  {evidence.calculation_version}
                                </dd>
                              </div>
                              <div className="flex justify-between gap-3">
                                <dt className="text-app-muted">{copy.windows}</dt>
                                <dd>
                                  {formatNumber(evidence.window_reference_checksums.length, locale)}
                                </dd>
                              </div>
                            </dl>
                          </article>
                        ))}
                      </div>

                      <div className="mt-5 border-t border-app-border pt-5">
                        <h4 className="font-semibold text-app-foreground">{copy.lineageTitle}</h4>
                        <dl className="mt-4 grid gap-4 text-xs sm:grid-cols-2">
                          {[
                            [copy.assessmentId, assessment.assessment_id],
                            [copy.manifestId, assessment.input_manifest_id],
                            [copy.snapshotId, assessment.feature_snapshot_id ?? '—'],
                            [copy.inputChecksum, assessment.input_checksum],
                            [copy.featureChecksum, assessment.feature_set_checksum],
                            [copy.snapshotChecksum, assessment.feature_snapshot_checksum ?? '—'],
                            [copy.algorithmVersion, assessment.algorithm_version],
                          ].map(([label, value]) => (
                            <div key={label} className="min-w-0">
                              <dt className="text-app-muted">{label}</dt>
                              <dd
                                dir="ltr"
                                className="mt-1 text-left font-mono break-all text-app-foreground"
                              >
                                {value}
                              </dd>
                            </div>
                          ))}
                        </dl>
                      </div>
                    </AdvancedDisclosure>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </section>

      {page.total > page.limit ? (
        <Pagination
          locale={locale}
          isLoading={isLoading}
          limit={page.limit}
          offset={page.offset}
          total={page.total}
          pageLabel={copy.pagination.label}
          previousLabel={copy.pagination.previous}
          nextLabel={copy.pagination.next}
          onOffsetChange={(offset) => void loadPage(offset)}
        />
      ) : null}
    </PageFrame>
  );
}
