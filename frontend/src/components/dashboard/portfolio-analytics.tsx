import { HistoricalLineChart } from '@/components/charts/historical-line-chart';
import { CHART_SERIES_COLORS } from '@/components/charts/chart-colors';
import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { portfolioAnalyticsCopy } from '@/components/dashboard/portfolio-analytics-copy';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui';
import type { PortfolioAnalyticsReport } from '@/lib/api/portfolio-analytics';

const metrics = [
  'starting_equity',
  'ending_equity',
  'net_pnl',
  'return_fraction',
  'fees_paid',
  'closed_net_pnl',
  'open_gross_unrealized_pnl',
  'open_entry_fees',
  'open_net_pnl',
  'closed_count',
  'open_count',
  'winning_count',
  'losing_count',
  'breakeven_count',
  'win_rate',
  'profit_factor',
  'expectancy',
  'average_hold_seconds',
  'duration_seconds',
  'max_drawdown_fraction',
  'max_drawdown_duration_seconds',
  'current_drawdown_duration_seconds',
  'open_exposure',
  'exposure_fraction',
] as const;

export function PortfolioAnalytics({
  report,
  locale,
}: {
  report: PortfolioAnalyticsReport;
  locale: DashboardLocale;
}) {
  const copy = portfolioAnalyticsCopy[locale];
  const numberLocale = locale === 'fa' ? 'fa-IR' : 'en-US';
  const decimal = new Intl.NumberFormat(numberLocale, { maximumFractionDigits: 8 });
  const percent = new Intl.NumberFormat(numberLocale, {
    style: 'percent',
    maximumFractionDigits: 4,
  });
  function value(raw: string | number | null, isPercent = false): string {
    if (raw === null) return copy.unavailable;
    return (isPercent ? percent : decimal).format(Number(raw));
  }
  function date(raw: string): string {
    return new Intl.DateTimeFormat(numberLocale, {
      dateStyle: 'short',
      timeStyle: 'short',
      timeZone: 'UTC',
    }).format(new Date(raw));
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{copy.title}</CardTitle>
        <CardDescription>{copy.description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <p className="text-sm text-app-muted">
          {copy.asOf}: <time dateTime={report.as_of}>{date(report.as_of)}</time>
        </p>
        <p className="text-sm text-app-muted">{copy.accounting}</p>
        <p className="text-sm text-app-muted">{copy.timing}</p>
        {report.closed_count === 0 && <p role="status">{copy.noTrades}</p>}
        {report.profit_factor_status === 'no_losses' && <p role="status">{copy.noLosses}</p>}
        <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {metrics.map((key) => (
            <div key={key} className="rounded-xl border border-app-border p-3">
              <dt className="text-xs text-app-muted">{copy[key]}</dt>
              <dd className="mt-2 font-semibold" dir="ltr">
                {value(report[key], key.endsWith('_fraction') || key === 'win_rate')}
              </dd>
            </div>
          ))}
        </dl>
        <p className="text-sm text-app-muted">{copy.exposureNote}</p>
        {(['equity', 'return_fraction', 'drawdown_fraction'] as const).map((key) => {
          const label =
            key === 'equity'
              ? copy.equity
              : key === 'return_fraction'
                ? copy.returns
                : copy.drawdown;
          return (
            <section key={key} aria-label={label}>
              <h3 className="mb-3 font-semibold">{label}</h3>
              <HistoricalLineChart
                ariaLabel={label}
                emptyLabel={copy.empty}
                minimumDomainSpan={key === 'equity' ? 1 : 0.01}
                formatDate={date}
                formatValue={(raw) => value(raw, key !== 'equity')}
                series={[
                  {
                    label,
                    color:
                      key === 'drawdown_fraction'
                        ? CHART_SERIES_COLORS.rose
                        : CHART_SERIES_COLORS.cyan,
                    curve: 'step_after',
                    points: report.equity_points.map((point) => ({
                      timestamp: point.timestamp,
                      value: Number(point[key]),
                    })),
                  },
                ]}
              />
            </section>
          );
        })}
        <section className="overflow-x-auto">
          <h3 className="mb-3 font-semibold">{copy.pairs}</h3>
          {report.trades_by_pair.length === 0 ? (
            <p>{copy.empty}</p>
          ) : (
            <table className="w-full text-start text-sm" aria-label={copy.pairs}>
              <thead>
                <tr>
                  {[
                    copy.pair,
                    copy.closed_count,
                    copy.open_count,
                    copy.closed_net_pnl,
                    copy.fees_paid,
                  ].map((label) => (
                    <th key={label} className="p-2 text-start">
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {report.trades_by_pair.map((item) => (
                  <tr
                    key={`${item.pair.base_asset}/${item.pair.quote_asset}/${item.pair.market_type}`}
                  >
                    <th className="p-2 text-start" scope="row">
                      {item.pair.base_asset}/{item.pair.quote_asset}
                    </th>
                    <td className="p-2">{value(item.closed_count)}</td>
                    <td className="p-2">{value(item.open_count)}</td>
                    <td className="p-2">{value(item.net_realized_pnl)}</td>
                    <td className="p-2">{value(item.fees_paid)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
        <section>
          <h3 className="mb-3 font-semibold">{copy.exits}</h3>
          <p className="text-sm text-app-muted">{copy.exitNote}</p>
          <ul>
            {report.exit_mix.map((item) => (
              <li key={item.reason}>
                {copy.reasons[item.reason as keyof typeof copy.reasons] ?? item.reason}:{' '}
                {value(item.count)}
              </li>
            ))}
          </ul>
        </section>
        <details>
          <summary className="cursor-pointer">{copy.evidence}</summary>
          <div className="max-h-96 overflow-auto">
            <table className="w-full text-sm" aria-label={copy.evidence}>
              <thead>
                <tr>
                  {[copy.sequence, copy.asOf, copy.equity, copy.returns, copy.drawdown].map(
                    (label) => (
                      <th key={label} className="p-2 text-start">
                        {label}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {report.equity_points.map((point) => (
                  <tr key={point.event_id}>
                    <th scope="row" className="p-2 text-start">
                      {point.sequence_number}
                    </th>
                    <td className="p-2">{date(point.timestamp)}</td>
                    <td className="p-2">{value(point.equity)}</td>
                    <td className="p-2">{value(point.return_fraction, true)}</td>
                    <td className="p-2">{value(point.drawdown_fraction, true)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
        <p className="text-xs text-app-muted">{report.analytics_version}</p>
      </CardContent>
    </Card>
  );
}
