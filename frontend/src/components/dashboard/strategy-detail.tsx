import Link from 'next/link';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getStrategyWorkspaceCopy } from '@/components/dashboard/strategy-workspace-copy';
import { Badge, Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui';
import type { ResearchStrategyMetadata, StrategyParameterMetadata } from '@/lib/api/types';
import { getExecutableResearchStrategies } from '@/lib/strategies/catalog';
import { getStrategyParameterLabel } from '@/lib/strategies/presentation';

type StrategyDetailProps = {
  locale: DashboardLocale;
  strategy: ResearchStrategyMetadata;
};

function formatNumber(value: number, locale: DashboardLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
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

export default function StrategyDetail({ locale, strategy }: StrategyDetailProps) {
  const copy = getStrategyWorkspaceCopy(locale);
  const isExecutable = getExecutableResearchStrategies([strategy]).length === 1;
  const encodedStrategyName = encodeURIComponent(strategy.name);

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
  ];

  return (
    <div className="space-y-8">
      <section>
        <Link
          href={`/${locale}/strategies`}
          className="text-sm font-semibold text-app-accent transition hover:underline focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none"
        >
          ← {copy.detail.back}
        </Link>

        <div className="mt-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-[0.25em] text-app-accent uppercase">
              {copy.detail.eyebrow}
            </p>
            <h1 className="mt-3 text-3xl font-bold tracking-tight text-app-foreground sm:text-4xl">
              {strategy.display_name}
            </h1>
          </div>

          <Badge variant="info">
            {copy.detail.version} {strategy.version}
          </Badge>
        </div>

        <p className="mt-4 max-w-3xl text-sm leading-7 text-app-muted sm:text-base">
          {strategy.description}
        </p>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>{copy.detail.metadataTitle}</CardTitle>
          <CardDescription>{copy.detail.metadataDescription}</CardDescription>
        </CardHeader>

        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-3">
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
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{copy.detail.parametersTitle}</CardTitle>
          <CardDescription>{copy.detail.parametersDescription}</CardDescription>
        </CardHeader>

        <CardContent>
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
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{copy.detail.launchTitle}</CardTitle>
          <CardDescription>{copy.detail.launchDescription}</CardDescription>
        </CardHeader>

        <CardContent>
          {isExecutable ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <Link
                href={`/${locale}/experiments?strategy=${encodedStrategyName}`}
                className="inline-flex min-h-11 items-center justify-center rounded-xl border border-app-accent-border bg-app-accent-soft px-4 py-3 text-sm font-semibold text-app-accent transition hover:bg-app-hover focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none"
              >
                {copy.detail.experimentAction}
              </Link>

              <Link
                href={`/${locale}/walk-forward?strategy=${encodedStrategyName}`}
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

      <Card>
        <CardHeader>
          <CardTitle>{copy.detail.registryTitle}</CardTitle>
          <CardDescription>{copy.detail.registryDescription}</CardDescription>
        </CardHeader>
      </Card>
    </div>
  );
}
