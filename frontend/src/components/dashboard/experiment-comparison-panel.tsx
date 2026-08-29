'use client';

import { useState } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getExperimentComparisonCopy } from '@/components/dashboard/experiment-comparison-copy';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Select,
  SelectOption,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui';
import { compareExperiments } from '@/lib/api/client';
import type {
  ExperimentComparisonMetric,
  ExperimentComparisonResult,
  ExperimentSummary,
} from '@/lib/api/types';

type ExperimentComparisonPanelProps = {
  locale: DashboardLocale;
  onClearSelection: () => void;
  selectedExperiments: ExperimentSummary[];
};

function formatNumber(value: number, locale: DashboardLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
}

function formatPercent(value: string, locale: DashboardLocale): string {
  const parsedValue = Number(value);

  if (!Number.isFinite(parsedValue)) {
    return value;
  }

  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    style: 'percent',
    maximumFractionDigits: 2,
  }).format(parsedValue);
}

export default function ExperimentComparisonPanel({
  locale,
  onClearSelection,
  selectedExperiments,
}: ExperimentComparisonPanelProps) {
  const copy = getExperimentComparisonCopy(locale);
  const direction = locale === 'fa' ? 'rtl' : 'ltr';

  const [metric, setMetric] = useState<ExperimentComparisonMetric>('excess_return');
  const [result, setResult] = useState<ExperimentComparisonResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);

  const canCompare = selectedExperiments.length >= 2 && selectedExperiments.length <= 10;

  async function runComparison(): Promise<void> {
    if (!canCompare) {
      return;
    }

    setIsLoading(true);
    setHasError(false);
    setResult(null);

    try {
      const comparison = await compareExperiments(
        selectedExperiments.map((experiment) => experiment.experiment_id),
        metric,
      );

      setResult(comparison);
    } catch {
      setHasError(true);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Card dir={direction} className="border-app-accent-border">
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <CardTitle>{copy.title}</CardTitle>
            <CardDescription className="mt-1.5">{copy.description}</CardDescription>
          </div>

          <Badge variant="info">
            {copy.selectedCount}: {formatNumber(selectedExperiments.length, locale)}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        <p className="text-sm leading-6 text-app-muted">{copy.selectionHint}</p>

        {selectedExperiments.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {selectedExperiments.map((experiment) => (
              <Badge
                key={experiment.experiment_id}
                variant="neutral"
                title={experiment.experiment_id}
              >
                {experiment.strategy_name} · {experiment.experiment_id.slice(-6)}
              </Badge>
            ))}
          </div>
        ) : null}

        <div className="grid items-end gap-4 lg:grid-cols-[1fr_auto_auto]">
          <Select
            dir={direction}
            label={copy.metricLabel}
            value={metric}
            disabled={isLoading}
            onValueChange={(value) => {
              setMetric(value as ExperimentComparisonMetric);
              setResult(null);
              setHasError(false);
            }}
          >
            <SelectOption value="excess_return">{copy.metrics.excess_return}</SelectOption>

            <SelectOption value="total_return">{copy.metrics.total_return}</SelectOption>

            <SelectOption value="max_drawdown_fraction">
              {copy.metrics.max_drawdown_fraction}
            </SelectOption>
          </Select>

          <Button
            disabled={!canCompare}
            isLoading={isLoading}
            loadingText={copy.comparing}
            onClick={() => void runComparison()}
          >
            {copy.compare}
          </Button>

          <Button
            variant="secondary"
            disabled={isLoading || selectedExperiments.length === 0}
            onClick={onClearSelection}
          >
            {copy.clearSelection}
          </Button>
        </div>

        {!canCompare ? (
          <p className="text-sm text-app-warning">{copy.insufficientSelection}</p>
        ) : null}

        {hasError ? (
          <div role="alert" className="rounded-xl border border-red-500/20 bg-red-500/5 p-4">
            <p className="text-sm text-red-500">{copy.error}</p>

            <Button
              className="mt-4"
              size="sm"
              variant="danger"
              onClick={() => void runComparison()}
            >
              {copy.retry}
            </Button>
          </div>
        ) : null}

        {result ? (
          <div className="space-y-4 border-t border-app-border pt-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h3 className="text-base font-semibold text-app-foreground">{copy.resultTitle}</h3>

                <p className="mt-1 text-sm leading-6 text-app-muted">{copy.resultDescription}</p>
              </div>

              <Badge variant="warning">{copy.rankingDirections[result.ranking_direction]}</Badge>
            </div>

            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{copy.fields.position}</TableHead>
                  <TableHead>{copy.fields.experiment}</TableHead>
                  <TableHead>{copy.fields.strategy}</TableHead>
                  <TableHead>{copy.fields.parameters}</TableHead>
                  <TableHead>{copy.fields.metricValue}</TableHead>
                </TableRow>
              </TableHeader>

              <TableBody>
                {result.entries.map((entry) => {
                  const isFirst = entry.experiment.experiment_id === result.best_experiment_id;

                  return (
                    <TableRow
                      key={entry.experiment.experiment_id}
                      className={isFirst ? 'bg-app-accent-soft' : undefined}
                    >
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <span>{formatNumber(entry.position, locale)}</span>

                          {isFirst ? (
                            <Badge variant="info">{copy.firstHistoricalRank}</Badge>
                          ) : null}
                        </div>
                      </TableCell>

                      <TableCell
                        dir="ltr"
                        className="max-w-64 truncate text-left text-xs font-semibold"
                        title={entry.experiment.experiment_id}
                      >
                        {entry.experiment.experiment_id}
                      </TableCell>

                      <TableCell>{entry.experiment.strategy_name}</TableCell>

                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {entry.experiment.parameters.map((parameter) => (
                            <Badge key={parameter.name} variant="neutral">
                              {parameter.name}={parameter.value}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>

                      <TableCell dir="ltr" className="font-extrabold">
                        {formatPercent(entry.metric_value, locale)}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>

            <p className="rounded-xl border border-app-warning-border bg-app-warning-soft p-4 text-sm text-app-warning">
              {copy.historicalOnly}
            </p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
