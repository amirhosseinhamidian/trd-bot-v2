import { CategoryBarChart } from '@/components/charts/category-bar-chart';
import { CHART_SERIES_COLORS } from '@/components/charts/chart-colors';
import { experimentDetailCopy } from '@/features/experiments/experiment-detail-copy';
import type { PlatformLocale } from '@/platform/i18n';
import {
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui';
import type { ExperimentAnalyticsReport, ResearchMetricKey } from '@/lib/api/types';

type ExperimentAnalyticsProps = {
  analytics: ExperimentAnalyticsReport;
  locale: PlatformLocale;
};

type MetricProps = {
  label: string;
  value: string;
};

function formatInteger(value: number, locale: PlatformLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
}

function formatDecimal(
  value: string | null,
  locale: PlatformLocale,
  maximumFractionDigits = 4,
): string {
  if (value === null) {
    return experimentDetailCopy[locale].unavailable;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    maximumFractionDigits,
  }).format(parsed);
}

function formatPercent(value: string | number, locale: PlatformLocale): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return String(value);
  }
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    style: 'percent',
    maximumFractionDigits: 2,
  }).format(parsed);
}

function formatDate(value: string, locale: PlatformLocale): string {
  return new Intl.DateTimeFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    dateStyle: 'medium',
  }).format(new Date(value));
}

function formatMonth(value: string, locale: PlatformLocale): string {
  return new Intl.DateTimeFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(value));
}

function Metric({ label, value }: MetricProps) {
  return (
    <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
      <dt className="text-xs text-app-muted">{label}</dt>
      <dd className="mt-2 text-lg font-semibold text-app-foreground">{value}</dd>
    </div>
  );
}

export function ExperimentAnalytics({ analytics, locale }: ExperimentAnalyticsProps) {
  const copy = experimentDetailCopy[locale];
  const distribution = analytics.trade_distribution;
  const metricLabel = (key: ResearchMetricKey): string =>
    copy.metricLabels[key as keyof typeof copy.metricLabels] ?? key;
  const metricDescription = (key: ResearchMetricKey, fallback: string): string =>
    copy.metricDescriptions[key as keyof typeof copy.metricDescriptions] ?? fallback;

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>{copy.tradeDistribution}</CardTitle>
          <CardDescription>{copy.tradeDistributionDescription}</CardDescription>
        </CardHeader>

        <CardContent className="space-y-8">
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric
              label={copy.winningTrades}
              value={formatInteger(distribution.winning_trades, locale)}
            />
            <Metric
              label={copy.losingTrades}
              value={formatInteger(distribution.losing_trades, locale)}
            />
            <Metric
              label={copy.flatTrades}
              value={formatInteger(distribution.flat_trades, locale)}
            />
            <Metric
              label={copy.longShortTrades}
              value={`${formatInteger(distribution.long_trades, locale)} / ${formatInteger(
                distribution.short_trades,
                locale,
              )}`}
            />
            <Metric
              label={copy.averageTradePnl}
              value={formatDecimal(distribution.average_net_pnl, locale)}
            />
            <Metric
              label={copy.medianTradePnl}
              value={formatDecimal(distribution.median_net_pnl, locale)}
            />
            <Metric
              label={copy.bestTradePnl}
              value={formatDecimal(distribution.best_net_pnl, locale)}
            />
            <Metric
              label={copy.worstTradePnl}
              value={formatDecimal(distribution.worst_net_pnl, locale)}
            />
            <Metric
              label={copy.grossProfit}
              value={formatDecimal(distribution.gross_profit, locale)}
            />
            <Metric label={copy.grossLoss} value={formatDecimal(distribution.gross_loss, locale)} />
            <Metric label={copy.totalFees} value={formatDecimal(distribution.total_fees, locale)} />
          </dl>

          <CategoryBarChart
            ariaLabel={copy.tradeDistributionChart}
            emptyLabel={copy.emptyTradeDistribution}
            minimumDomainSpan={1}
            formatValue={(value) => formatInteger(value, locale)}
            series={[
              {
                label: copy.closedTrades,
                color: CHART_SERIES_COLORS.cyan,
                points:
                  distribution.total_trades === 0
                    ? []
                    : [
                        { category: copy.winningTrades, value: distribution.winning_trades },
                        { category: copy.losingTrades, value: distribution.losing_trades },
                        { category: copy.flatTrades, value: distribution.flat_trades },
                      ],
              },
            ]}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{copy.periodReturns}</CardTitle>
          <CardDescription>{copy.periodReturnsDescription}</CardDescription>
        </CardHeader>

        <CardContent className="space-y-8">
          <CategoryBarChart
            ariaLabel={copy.periodReturnsChart}
            emptyLabel={copy.emptyPeriodReturns}
            minimumDomainSpan={0.01}
            formatValue={(value) => formatPercent(value, locale)}
            series={[
              {
                label: copy.returnContribution,
                color: CHART_SERIES_COLORS.blue,
                points: analytics.returns_by_period.map((period) => ({
                  category: formatMonth(period.started_at, locale),
                  value: Number(period.return_contribution),
                })),
              },
            ]}
          />

          <Table scrollLabel={copy.periodReturnsTableScrollLabel} className="min-w-[44rem]">
            <TableHeader>
              <TableRow>
                <TableHead>{copy.period}</TableHead>
                <TableHead>{copy.returnContribution}</TableHead>
                <TableHead>{copy.periodNetPnl}</TableHead>
                <TableHead>{copy.totalTrades}</TableHead>
                <TableHead>{copy.endingBalance}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {analytics.returns_by_period.map((period) => (
                <TableRow key={period.period}>
                  <TableCell>{formatMonth(period.started_at, locale)}</TableCell>
                  <TableCell dir="ltr">
                    {formatPercent(period.return_contribution, locale)}
                  </TableCell>
                  <TableCell dir="ltr">{formatDecimal(period.net_pnl, locale)}</TableCell>
                  <TableCell>{formatInteger(period.total_trades, locale)}</TableCell>
                  <TableCell dir="ltr">{formatDecimal(period.ending_balance, locale)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{copy.drawdownEpisodes}</CardTitle>
          <CardDescription>{copy.drawdownEpisodesDescription}</CardDescription>
        </CardHeader>

        <CardContent>
          {analytics.drawdown_episodes.length === 0 ? (
            <p className="rounded-xl border border-dashed border-app-border bg-app-surface-muted p-6 text-sm text-app-muted">
              {copy.noDrawdownEpisodes}
            </p>
          ) : (
            <Table scrollLabel={copy.drawdownTableScrollLabel} className="min-w-[48rem]">
              <TableHeader>
                <TableRow>
                  <TableHead>{copy.episode}</TableHead>
                  <TableHead>{copy.startedAt}</TableHead>
                  <TableHead>{copy.troughAt}</TableHead>
                  <TableHead>{copy.recoveredAt}</TableHead>
                  <TableHead>{copy.maximumDepth}</TableHead>
                  <TableHead>{copy.tradesUnderwater}</TableHead>
                  <TableHead>{copy.recoveryStatus}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {analytics.drawdown_episodes.map((episode) => (
                  <TableRow key={episode.episode_number}>
                    <TableCell>{formatInteger(episode.episode_number, locale)}</TableCell>
                    <TableCell>{formatDate(episode.started_at, locale)}</TableCell>
                    <TableCell>{formatDate(episode.trough_at, locale)}</TableCell>
                    <TableCell>
                      {episode.recovered_at === null
                        ? copy.unavailable
                        : formatDate(episode.recovered_at, locale)}
                    </TableCell>
                    <TableCell dir="ltr">
                      {formatPercent(episode.max_drawdown_fraction, locale)}
                    </TableCell>
                    <TableCell>{formatInteger(episode.trades_underwater, locale)}</TableCell>
                    <TableCell>
                      <Badge variant={episode.status === 'recovered' ? 'success' : 'warning'}>
                        {copy.drawdownStatuses[episode.status]}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{copy.metricDefinitions}</CardTitle>
          <CardDescription>{copy.metricDefinitionsDescription}</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 lg:grid-cols-2">
            {analytics.metric_definitions.map((definition) => (
              <div
                key={definition.key}
                className="rounded-xl border border-app-border bg-app-surface-muted p-4"
              >
                <dt className="font-semibold text-app-foreground">{metricLabel(definition.key)}</dt>
                <dd className="mt-2 text-sm leading-6 text-app-muted">
                  {metricDescription(definition.key, definition.definition)}
                </dd>
                <dd dir="ltr" className="mt-3 font-mono text-xs break-all text-app-accent">
                  {definition.formula}
                </dd>
                <dd className="mt-3 text-xs text-app-muted">
                  {copy.metricPreferences[definition.preference]}
                </dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>
    </>
  );
}
