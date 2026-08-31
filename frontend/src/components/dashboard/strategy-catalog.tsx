import Link from 'next/link';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getStrategyWorkspaceCopy } from '@/components/dashboard/strategy-workspace-copy';
import {
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
  EmptyState,
} from '@/components/ui';
import type { ResearchStrategyMetadata } from '@/lib/api/types';

type StrategyCatalogProps = {
  locale: DashboardLocale;
  strategies: ResearchStrategyMetadata[];
};

function formatNumber(value: number, locale: DashboardLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
}

export default function StrategyCatalog({ locale, strategies }: StrategyCatalogProps) {
  const copy = getStrategyWorkspaceCopy(locale);

  return (
    <div className="space-y-8">
      <section>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-[0.25em] text-app-accent uppercase">
              {copy.catalog.eyebrow}
            </p>
            <h1 className="mt-3 text-3xl font-bold tracking-tight text-app-foreground sm:text-4xl">
              {copy.catalog.title}
            </h1>
          </div>

          <Badge variant="info">
            {copy.catalog.total}: {formatNumber(strategies.length, locale)}
          </Badge>
        </div>

        <p className="mt-3 max-w-3xl text-sm leading-7 text-app-muted sm:text-base">
          {copy.catalog.description}
        </p>
      </section>

      {strategies.length === 0 ? (
        <EmptyState title={copy.catalog.emptyTitle} description={copy.catalog.emptyDescription} />
      ) : (
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {strategies.map((strategy) => (
            <Card key={`${strategy.name}@${strategy.version}`} className="overflow-hidden">
              <CardHeader className="border-b border-app-border">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <CardTitle>{strategy.display_name}</CardTitle>
                    <CardDescription
                      dir="ltr"
                      className="mt-2 truncate text-left text-xs font-semibold"
                    >
                      {strategy.name}@{strategy.version}
                    </CardDescription>
                  </div>

                  <Badge variant="neutral">
                    {copy.catalog.version} {strategy.version}
                  </Badge>
                </div>
              </CardHeader>

              <CardContent className="pt-6">
                <p className="text-sm leading-7 text-app-muted">{strategy.description}</p>

                <dl className="mt-6">
                  <div className="flex items-center justify-between gap-4 border-t border-app-border pt-4">
                    <dt className="text-sm text-app-muted">{copy.catalog.parameters}</dt>
                    <dd className="font-semibold text-app-foreground">
                      {formatNumber(strategy.parameters.length, locale)}
                    </dd>
                  </div>
                </dl>
              </CardContent>

              <CardFooter>
                <Link
                  href={`/${locale}/strategies/${encodeURIComponent(strategy.name)}/${encodeURIComponent(strategy.version)}`}
                  className="inline-flex min-h-10 w-full items-center justify-center rounded-xl border border-app-border bg-app-surface px-4 py-2.5 text-sm font-semibold text-app-foreground transition hover:border-app-accent-border hover:text-app-accent focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none"
                >
                  {copy.catalog.viewDetails}
                </Link>
              </CardFooter>
            </Card>
          ))}
        </section>
      )}
    </div>
  );
}
