import Link from 'next/link';

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
} from '@/components/ui';
import type { ExperimentSummary } from '@/features/experiments/api/types';
import type {
  ResearchStrategyMetadata,
  StrategyParameterMetadata,
} from '@/features/strategies/api/types';
import { getStrategyWorkspaceCopy } from '@/features/strategies/strategy-workspace-copy';
import type { Page } from '@/lib/api/core/types';
import { getExecutableResearchStrategies } from '@/lib/strategies/catalog';
import { getStrategyParameterLabel } from '@/lib/strategies/presentation';
import type { PlatformLocale } from '@/platform/i18n';

type StrategyDetailProps = {
  locale: PlatformLocale;
  strategy: ResearchStrategyMetadata;
  experimentHistory?: Page<ExperimentSummary>;
};

function formatNumber(value: number, locale: PlatformLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
}

function formatDate(value: string, locale: PlatformLocale): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function formatMinimum(
  parameter: StrategyParameterMetadata,
  copy: ReturnType<typeof getStrategyWorkspaceCopy>,
): string {
  if (parameter.minimum === null) {
    return copy.detail.noMinimum;
  }

  return `${parameter.minimum_exclusive ? '>' : '≥'} ${parameter.minimum}`;
}

function formatMaximum(
  parameter: StrategyParameterMetadata,
  copy: ReturnType<typeof getStrategyWorkspaceCopy>,
): string {
  if (parameter.maximum === null) {
    return copy.detail.noMaximum;
  }

  return `${parameter.maximum_exclusive ? '<' : '≤'} ${parameter.maximum}`;
}

export default function StrategyDetail({
  locale,
  strategy,
  experimentHistory,
}: StrategyDetailProps) {
  const copy = getStrategyWorkspaceCopy(locale);
  const isExecutable = getExecutableResearchStrategies([strategy]).length === 1;
  const encodedStrategyName = encodeURIComponent(strategy.name);
  const encodedStrategyVersion = encodeURIComponent(strategy.version);
  const lifecycleStatus = strategy.lifecycle_status ?? 'active';

  const metadata = [
    {
      label: copy.detail.identifier,
      value: strategy.name,
      direction: 'ltr' as const,
    },
    {
      label: copy.detail.version,
      value: strategy.version,
      direction: 'ltr' as const,
    },
    {
      label: copy.detail.parameterCount,
      value: formatNumber(strategy.parameters.length, locale),
      direction: undefined,
    },
    {
      label: copy.detail.lifecycleStatus,
      value: copy.detail.statuses[lifecycleStatus],
      direction: undefined,
    },
    {
      label: copy.detail.fingerprint,
      value: strategy.behavior_fingerprint ?? copy.detail.legacyFingerprint,
      direction: strategy.behavior_fingerprint ? ('ltr' as const) : undefined,
    },
  ];

  return (
    <PageFrame>
      <PageHeader
        backLink={
          <Link
            href={`/${locale}/strategies`}
            className="text-sm font-semibold text-app-accent transition hover:underline focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none"
          >
            ← {copy.detail.back}
          </Link>
        }
        eyebrow={copy.detail.eyebrow}
        title={strategy.display_name}
        description={strategy.description}
        actions={
          <Badge variant="info">
            {copy.detail.version} {strategy.version}
          </Badge>
        }
      />

      <AdvancedDisclosure
        title={copy.detail.metadataTitle}
        description={copy.detail.metadataDescription}
      >
        <div>
          <dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            {metadata.map((item) => (
              <div
                key={item.label}
                className="rounded-xl border border-app-border bg-app-surface-muted p-4"
              >
                <dt className="text-xs text-app-muted">{item.label}</dt>
                <dd
                  dir={item.direction}
                  className={[
                    'mt-2 text-sm font-semibold break-all text-app-foreground',
                    item.direction === 'ltr' ? 'text-left' : '',
                  ].join(' ')}
                >
                  {item.value}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </AdvancedDisclosure>

      <AdvancedDisclosure
        title={copy.detail.parametersTitle}
        description={copy.detail.parametersDescription}
      >
        <div>
          {strategy.parameters.length === 0 ? (
            <p className="text-sm leading-7 text-app-muted">{copy.detail.noParameters}</p>
          ) : (
            <div className="space-y-4">
              {strategy.parameters.map((parameter) => (
                <article
                  key={parameter.name}
                  className="rounded-xl border border-app-border bg-app-surface-muted p-5"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="font-semibold text-app-foreground">
                        {getStrategyParameterLabel(parameter.name, locale)}
                      </h2>
                      {getStrategyParameterLabel(parameter.name, locale) !== parameter.name ? (
                        <p
                          dir="ltr"
                          className="mt-1 text-left text-xs font-semibold text-app-subtle"
                        >
                          {parameter.name}
                        </p>
                      ) : null}
                    </div>

                    <Badge variant="neutral">{copy.detail.kinds[parameter.kind]}</Badge>
                  </div>

                  <dl className="mt-5 grid gap-3 sm:grid-cols-3">
                    <div>
                      <dt className="text-xs text-app-muted">{copy.detail.defaultValue}</dt>
                      <dd
                        dir="ltr"
                        className="mt-2 text-left text-sm font-semibold text-app-foreground"
                      >
                        {parameter.default_value}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-app-muted">{copy.detail.minimum}</dt>
                      <dd
                        dir="ltr"
                        className="mt-2 text-left text-sm font-semibold text-app-foreground"
                      >
                        {formatMinimum(parameter, copy)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-app-muted">{copy.detail.maximum}</dt>
                      <dd
                        dir="ltr"
                        className="mt-2 text-left text-sm font-semibold text-app-foreground"
                      >
                        {formatMaximum(parameter, copy)}
                      </dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          )}
        </div>
      </AdvancedDisclosure>

      <Card>
        <CardHeader>
          <CardTitle>{copy.detail.launchTitle}</CardTitle>
          <CardDescription>{copy.detail.launchDescription}</CardDescription>
        </CardHeader>

        <CardContent>
          {isExecutable ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <Link
                href={`/${locale}/experiments?strategy=${encodedStrategyName}&strategy_version=${encodedStrategyVersion}`}
                className="inline-flex min-h-11 items-center justify-center rounded-xl border border-app-accent-border bg-app-accent-soft px-4 py-3 text-sm font-semibold text-app-accent transition hover:bg-app-hover focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none"
              >
                {copy.detail.experimentAction}
              </Link>

              <Link
                href={`/${locale}/walk-forward?strategy=${encodedStrategyName}&strategy_version=${encodedStrategyVersion}`}
                className="inline-flex min-h-11 items-center justify-center rounded-xl border border-app-border bg-app-surface px-4 py-3 text-sm font-semibold text-app-foreground transition hover:border-app-accent-border hover:bg-app-hover hover:text-app-accent focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none"
              >
                {copy.detail.walkForwardAction}
              </Link>
            </div>
          ) : (
            <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
              <p className="font-semibold text-app-foreground">{copy.detail.unavailableTitle}</p>
              <p className="mt-2 text-sm leading-7 text-app-muted">
                {copy.detail.unavailableDescription}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      <AdvancedDisclosure
        title={copy.detail.historyTitle}
        description={copy.detail.historyDescription}
      >
        <div>
          <Badge variant="info" className="mb-5">
            {copy.detail.historyTotal}: {formatNumber(experimentHistory?.total ?? 0, locale)}
          </Badge>
          {!experimentHistory || experimentHistory.items.length === 0 ? (
            <p className="text-sm leading-7 text-app-muted">{copy.detail.historyEmpty}</p>
          ) : (
            <div className="space-y-3">
              {experimentHistory.items.map((experiment) => (
                <article
                  key={experiment.experiment_id}
                  className="flex flex-col gap-4 rounded-xl border border-app-border bg-app-surface-muted p-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0">
                    <p
                      dir="ltr"
                      className="truncate text-left text-sm font-semibold text-app-foreground"
                    >
                      {experiment.experiment_id}
                    </p>
                    <p className="mt-2 text-xs leading-6 text-app-muted">
                      {copy.detail.historyDataset}: <span dir="ltr">{experiment.dataset_id}</span>
                      {' · '}
                      {copy.detail.historyCreatedAt}: {formatDate(experiment.created_at, locale)}
                    </p>
                  </div>
                  <Link
                    href={`/${locale}/experiments/${encodeURIComponent(experiment.experiment_id)}`}
                    className="inline-flex min-h-10 shrink-0 items-center justify-center rounded-xl border border-app-border bg-app-surface px-4 py-2 text-sm font-semibold text-app-foreground transition hover:border-app-accent-border hover:text-app-accent focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none"
                  >
                    {copy.detail.viewExperiment}
                  </Link>
                </article>
              ))}
            </div>
          )}
        </div>
      </AdvancedDisclosure>

      <Card>
        <CardHeader>
          <CardTitle>{copy.detail.registryTitle}</CardTitle>
          <CardDescription>{copy.detail.registryDescription}</CardDescription>
        </CardHeader>
      </Card>
    </PageFrame>
  );
}
