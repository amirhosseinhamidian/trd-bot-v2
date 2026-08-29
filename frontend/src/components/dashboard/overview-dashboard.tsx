import ActivityFeed from '@/components/dashboard/activity-feed';
import { type DashboardLocale, getDashboardCopy } from '@/components/dashboard/dashboard-copy';
import type { Page, ResearchActivityItem, ResearchOverview, ResearchStage } from '@/lib/api/types';

type OverviewDashboardProps = {
  locale: DashboardLocale;
  overview: ResearchOverview;
  activityPage: Page<ResearchActivityItem>;
};

function formatNumber(value: number, locale: DashboardLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
}

function formatPercent(value: string, locale: DashboardLocale): string {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return value;
  }

  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    style: 'percent',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(numericValue);
}

export default function OverviewDashboard({
  locale,
  overview,
  activityPage,
}: OverviewDashboardProps) {
  const copy = getDashboardCopy(locale);

  const stageLabels: Record<ResearchStage, string> = {
    empty: copy.overview.stages.empty,
    data_available: copy.overview.stages.dataAvailable,
    experiments_available: copy.overview.stages.experimentsAvailable,
    walk_forward_available: copy.overview.stages.walkForwardAvailable,
  };

  const stageOrder: ResearchStage[] = [
    'empty',
    'data_available',
    'experiments_available',
    'walk_forward_available',
  ];

  const currentStageIndex = stageOrder.indexOf(overview.research_stage);

  const cards = [
    {
      label: copy.overview.cards.datasets,
      value: overview.dataset_count,
      accent: 'bg-violet-400',
    },
    {
      label: copy.overview.cards.experiments,
      value: overview.experiment_count,
      accent: 'bg-cyan-400',
    },
    {
      label: copy.overview.cards.walkForward,
      value: overview.walk_forward_run_count,
      accent: 'bg-blue-400',
    },
    {
      label: copy.overview.cards.policies,
      value: overview.acceptance_policy_preset_count,
      accent: 'bg-emerald-400',
    },
  ];

  return (
    <div className="space-y-8">
      <section>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-[0.25em] text-app-accent uppercase">
              {copy.overview.eyebrow}
            </p>

            <h1 className="mt-3 text-3xl font-bold tracking-tight text-app-foreground sm:text-4xl">
              {copy.overview.title}
            </h1>
          </div>

          <div className="flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-xs font-medium text-emerald-500">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            {copy.overview.connected}
          </div>
        </div>

        <p className="mt-3 max-w-3xl text-sm leading-7 text-app-muted sm:text-base">
          {copy.overview.description}
        </p>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <article
            key={card.label}
            className="rounded-2xl border border-app-border bg-app-surface p-5 shadow-lg shadow-black/10"
          >
            <div className="flex items-center justify-between">
              <p className="text-sm text-app-muted">{card.label}</p>
              <span className={`h-2.5 w-2.5 rounded-full ${card.accent}`} />
            </div>

            <p className="mt-5 text-3xl font-bold text-app-foreground">
              {formatNumber(card.value, locale)}
            </p>
          </article>
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.35fr_1fr]">
        <ActivityFeed locale={locale} initialPage={activityPage} />

        <article className="rounded-2xl border border-app-border bg-app-surface p-6">
          <h2 className="text-lg font-semibold text-app-foreground">
            {copy.overview.stages.title}
          </h2>

          <p className="mt-1 text-sm text-app-muted">{copy.overview.stages.description}</p>

          <div className="mt-6 rounded-xl border border-app-accent-border bg-app-accent-soft p-4">
            <p className="text-xs text-app-accent">{copy.overview.stages.current}</p>

            <p className="mt-2 font-semibold text-app-accent">
              {stageLabels[overview.research_stage]}
            </p>
          </div>

          <div className="mt-6 space-y-4">
            {stageOrder.map((stage, index) => {
              const isCompleted = index <= currentStageIndex;

              return (
                <div key={stage} className="flex items-center gap-3">
                  <span
                    className={[
                      'h-3 w-3 shrink-0 rounded-full',
                      isCompleted ? 'bg-emerald-400' : 'bg-app-border',
                    ].join(' ')}
                  />

                  <span
                    className={
                      isCompleted ? 'text-sm text-app-foreground' : 'text-sm text-app-subtle'
                    }
                  >
                    {stageLabels[stage]}
                  </span>
                </div>
              );
            })}
          </div>
        </article>
      </section>

      <section className="rounded-2xl border border-app-border bg-app-surface p-6">
        <h2 className="text-lg font-semibold text-app-foreground">{copy.overview.latest.title}</h2>

        <p className="mt-1 text-sm text-app-muted">{copy.overview.latest.description}</p>

        <div className="mt-6 grid gap-4 lg:grid-cols-3">
          <article className="rounded-2xl border border-app-border bg-app-surface-muted p-5">
            <p className="text-sm font-medium text-violet-500">{copy.overview.latest.dataset}</p>

            {overview.latest_dataset ? (
              <div className="mt-4 space-y-3">
                <p className="font-semibold text-app-foreground">{overview.latest_dataset.name}</p>

                <p dir="ltr" className="text-left text-sm text-app-muted">
                  {overview.latest_dataset.pair.base_asset}/
                  {overview.latest_dataset.pair.quote_asset}
                </p>

                <div className="flex justify-between gap-4 text-xs text-app-muted">
                  <span>
                    {copy.overview.latest.candles}:{' '}
                    {formatNumber(overview.latest_dataset.candle_count, locale)}
                  </span>
                  <span>
                    {copy.overview.latest.timeframe}: {overview.latest_dataset.timeframe}
                  </span>
                </div>
              </div>
            ) : (
              <p className="mt-4 text-sm text-app-subtle">{copy.overview.latest.noData}</p>
            )}
          </article>

          <article className="rounded-2xl border border-app-border bg-app-surface-muted p-5">
            <p className="text-sm font-medium text-app-accent">{copy.overview.latest.experiment}</p>

            {overview.latest_experiment ? (
              <div className="mt-4 space-y-3">
                <p className="font-semibold text-app-foreground">
                  {overview.latest_experiment.strategy_name}
                </p>

                <p className="text-sm text-app-muted">
                  v{overview.latest_experiment.strategy_version}
                </p>

                <div className="space-y-2 text-xs text-app-muted">
                  <div className="flex justify-between gap-4">
                    <span>{copy.overview.latest.trades}</span>
                    <span>{formatNumber(overview.latest_experiment.total_trades, locale)}</span>
                  </div>

                  <div className="flex justify-between gap-4">
                    <span>{copy.overview.latest.return}</span>
                    <span dir="ltr">
                      {formatPercent(overview.latest_experiment.total_return, locale)}
                    </span>
                  </div>

                  <div className="flex justify-between gap-4">
                    <span>{copy.overview.latest.comparison}</span>
                    <span dir="ltr">{overview.latest_experiment.comparison_outcome}</span>
                  </div>
                </div>
              </div>
            ) : (
              <p className="mt-4 text-sm text-app-subtle">{copy.overview.latest.noData}</p>
            )}
          </article>

          <article className="rounded-2xl border border-app-border bg-app-surface-muted p-5">
            <p className="text-sm font-medium text-blue-500">{copy.overview.latest.walkForward}</p>

            {overview.latest_walk_forward_run ? (
              <div className="mt-4 space-y-3">
                <p className="font-semibold text-app-foreground">
                  {overview.latest_walk_forward_run.strategy_name}
                </p>

                <p className="text-sm text-app-muted">
                  v{overview.latest_walk_forward_run.strategy_version}
                </p>

                <div className="space-y-2 text-xs text-app-muted">
                  <div className="flex justify-between gap-4">
                    <span>{copy.overview.latest.folds}</span>
                    <span>
                      {formatNumber(overview.latest_walk_forward_run.total_folds, locale)}
                    </span>
                  </div>

                  <div className="flex justify-between gap-4">
                    <span>{copy.overview.latest.excessReturn}</span>
                    <span dir="ltr">
                      {formatPercent(
                        overview.latest_walk_forward_run.average_excess_return,
                        locale,
                      )}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <p className="mt-4 text-sm text-app-subtle">{copy.overview.latest.noData}</p>
            )}
          </article>
        </div>
      </section>
    </div>
  );
}
