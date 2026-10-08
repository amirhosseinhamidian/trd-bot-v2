'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

import type { PlatformLocale } from '@/platform/i18n';
import type { ExperimentParameter } from '@/features/experiments/api/types';
import { getOptimizationExecution } from '@/features/optimizations/api/client';
import type {
  OptimizationExecution,
  OptimizationExecutionStatus,
  OptimizationTrialEvaluation,
} from '@/features/optimizations/api/types';
import { getOptimizationCopy } from '@/features/optimizations/optimization-copy';
import {
  Badge,
  type BadgeVariant,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui';
import { formatStrategyParameter, getStrategyDisplayName } from '@/lib/strategies/presentation';
import { PageFrame } from '@/components/platform/page-frame';
import { PageHeader } from '@/components/platform/page-header';

const POLLING_INTERVAL_MS = 1000;

type OptimizationDetailProps = {
  initialExecution: OptimizationExecution;
  locale: PlatformLocale;
};

type MetricProps = {
  label: string;
  value: string;
};

function formatNumber(value: number, locale: PlatformLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
}

function formatDate(value: string | null, locale: PlatformLocale, fallback: string): string {
  if (value === null) {
    return fallback;
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function formatDecimal(value: string, locale: PlatformLocale): string {
  const parsed = Number(value);

  if (!Number.isFinite(parsed)) {
    return value;
  }

  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    maximumFractionDigits: 6,
  }).format(parsed);
}

function formatPercent(value: string, locale: PlatformLocale): string {
  const parsed = Number(value);

  if (!Number.isFinite(parsed)) {
    return value;
  }

  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    style: 'percent',
    maximumFractionDigits: 2,
  }).format(parsed);
}

function formatObjectiveValue(value: string, locale: PlatformLocale): string {
  return formatPercent(value, locale);
}

function statusVariant(status: OptimizationExecutionStatus): BadgeVariant {
  if (status === 'succeeded') {
    return 'success';
  }
  if (status === 'failed') {
    return 'danger';
  }
  if (status === 'running') {
    return 'info';
  }
  return 'neutral';
}

function Metric({ label, value }: MetricProps) {
  return (
    <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
      <dt className="text-xs text-app-muted">{label}</dt>
      <dd className="mt-2 text-sm font-semibold break-words text-app-foreground">{value}</dd>
    </div>
  );
}

function trialParameters(
  execution: OptimizationExecution,
  trialNumber: number,
): ExperimentParameter[] {
  return (
    execution.plan.trials.find((trial) => trial.trial_number === trialNumber)?.parameters ?? []
  );
}

function EvidenceLinks({
  evaluation,
  locale,
}: {
  evaluation: OptimizationTrialEvaluation;
  locale: PlatformLocale;
}) {
  return (
    <div className="flex min-w-48 flex-col gap-2 text-xs">
      <Link
        href={`/${locale}/experiments/${encodeURIComponent(evaluation.experiment_id)}`}
        dir="ltr"
        className="rounded-sm text-left font-semibold break-all text-app-accent transition hover:opacity-80 focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none"
      >
        {evaluation.experiment_id}
      </Link>
      <Link
        href={`/${locale}/walk-forward/${encodeURIComponent(evaluation.walk_forward_run_id)}`}
        dir="ltr"
        className="rounded-sm text-left font-semibold break-all text-app-accent transition hover:opacity-80 focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none"
      >
        {evaluation.walk_forward_run_id}
      </Link>
    </div>
  );
}

export default function OptimizationDetail({ initialExecution, locale }: OptimizationDetailProps) {
  const copy = getOptimizationCopy(locale);
  const direction = locale === 'fa' ? 'rtl' : 'ltr';
  const [execution, setExecution] = useState(initialExecution);
  const [refreshError, setRefreshError] = useState(false);
  const isActive = execution.status === 'queued' || execution.status === 'running';

  useEffect(() => {
    if (!isActive) {
      return;
    }

    let active = true;
    let timeoutId: number | null = null;

    async function refresh(): Promise<void> {
      try {
        const current = await getOptimizationExecution(execution.execution_id);

        if (!active) {
          return;
        }

        setExecution(current);
        setRefreshError(false);

        if (current.status === 'queued' || current.status === 'running') {
          timeoutId = window.setTimeout(() => void refresh(), POLLING_INTERVAL_MS);
        }
      } catch {
        if (active) {
          setRefreshError(true);
        }
      }
    }

    timeoutId = window.setTimeout(() => void refresh(), POLLING_INTERVAL_MS);

    return () => {
      active = false;
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [execution.execution_id, isActive]);

  const progressPercent = Math.round((execution.completed_trials / execution.total_trials) * 100);
  const robustnessPlan = execution.robustness_plan;
  const ranking = execution.robustness_ranking;
  const rejectedEvaluations = execution.trial_evaluations.filter(
    (evaluation) => !evaluation.eligible,
  );

  return (
    <PageFrame dir={direction} className="space-y-6">
      <PageHeader
        backLink={
          <Link
            href={`/${locale}/optimizations`}
            className="rounded-sm text-sm font-medium text-app-accent transition hover:opacity-80 focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none"
          >
            <span aria-hidden="true">{locale === 'fa' ? '→' : '←'}</span> {copy.detail.back}
          </Link>
        }
        eyebrow={copy.detail.eyebrow}
        title={getStrategyDisplayName(execution.strategy_name, locale)}
        metadata={
          <p dir="ltr" className="text-left text-sm font-semibold break-all text-app-muted">
            {execution.execution_id}
          </p>
        }
        actions={
          <>
            <Badge variant="warning">{copy.historicalOnly}</Badge>
            <Badge variant={statusVariant(execution.status)}>
              {copy.statuses[execution.status]}
            </Badge>
          </>
        }
      />

      <Card className="border-app-warning-border bg-app-warning-soft">
        <CardContent className="pt-6">
          <p className="text-sm leading-7 text-app-warning">{copy.detail.disclaimer}</p>
        </CardContent>
      </Card>

      {isActive ? (
        <Card className="border-app-accent-border bg-app-accent-soft">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <Spinner className="text-app-accent" />
                <p className="text-sm text-app-accent">
                  {execution.status === 'queued' ? copy.form.queuedState : copy.form.runningState}
                </p>
              </div>
              <span dir="ltr" className="font-semibold text-app-accent">
                {progressPercent}%
              </span>
            </div>
            <div
              role="progressbar"
              aria-label={copy.form.progress}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progressPercent}
              className="mt-4 h-2 overflow-hidden rounded-full bg-app-border"
            >
              <div
                className="h-full rounded-full bg-app-accent transition-[width]"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </CardContent>
        </Card>
      ) : null}

      {refreshError ? (
        <p
          role="alert"
          className="rounded-xl border border-app-danger-border bg-app-danger-soft p-4 text-sm text-app-danger"
        >
          {copy.form.errors.statusUnavailable}
        </p>
      ) : null}

      {execution.status === 'failed' ? (
        <Card className="border-app-danger-border bg-app-danger-soft">
          <CardContent className="pt-6">
            <p className="font-semibold text-app-danger">
              {execution.error_code ?? copy.form.errors.executionFailed}
            </p>
            {execution.error_message ? (
              <p className="mt-2 text-sm text-app-danger">{execution.error_message}</p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>{copy.detail.summary}</CardTitle>
          <CardDescription>{copy.detail.summaryDescription}</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric
              label={copy.detail.fields.strategy}
              value={getStrategyDisplayName(execution.strategy_name, locale)}
            />
            <Metric label={copy.detail.fields.version} value={execution.strategy_version} />
            <Metric label={copy.detail.fields.status} value={copy.statuses[execution.status]} />
            <Metric
              label={copy.detail.fields.objective}
              value={copy.objectives[execution.objective]}
            />
            <Metric
              label={copy.detail.fields.createdAt}
              value={formatDate(execution.created_at, locale, copy.fields.notAvailable)}
            />
            <Metric
              label={copy.detail.fields.finishedAt}
              value={formatDate(execution.finished_at, locale, copy.fields.notAvailable)}
            />
            <Metric
              label={copy.detail.fields.totalTrials}
              value={formatNumber(execution.total_trials, locale)}
            />
            <Metric
              label={copy.detail.fields.completedTrials}
              value={formatNumber(execution.completed_trials, locale)}
            />
          </dl>

          <dl className="mt-4 grid gap-4 sm:grid-cols-2">
            <Metric label={copy.detail.fields.datasetId} value={execution.dataset_id} />
            <Metric label={copy.detail.fields.executionId} value={execution.execution_id} />
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{copy.detail.plan}</CardTitle>
          <CardDescription>{copy.detail.planDescription}</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="mb-6 grid gap-4 sm:grid-cols-3">
            <Metric
              label={copy.detail.fields.requested}
              value={formatNumber(execution.plan.requested_combinations, locale)}
            />
            <Metric
              label={copy.detail.fields.skipped}
              value={formatNumber(execution.plan.skipped_combinations, locale)}
            />
            <Metric
              label={copy.detail.fields.totalTrials}
              value={formatNumber(execution.plan.total_trials, locale)}
            />
          </dl>

          <Table scrollLabel={copy.detail.planTableScroll} className="min-w-[38rem]">
            <TableHeader>
              <TableRow>
                <TableHead>{copy.detail.fields.trial}</TableHead>
                <TableHead>{copy.detail.fields.parameters}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {execution.plan.trials.map((trial) => (
                <TableRow key={trial.trial_number}>
                  <TableCell>{formatNumber(trial.trial_number, locale)}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-2">
                      {trial.parameters.map((parameter) => (
                        <Badge key={parameter.name} variant="neutral">
                          {formatStrategyParameter(parameter, locale)}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{copy.detail.ranking}</CardTitle>
          <CardDescription>{copy.detail.rankingDescription}</CardDescription>
        </CardHeader>
        <CardContent>
          {ranking === null ? (
            <p className="rounded-xl border border-app-border bg-app-surface-muted p-4 text-sm text-app-muted">
              {copy.detail.noRanking}
            </p>
          ) : (
            <>
              <dl className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Metric
                  label={copy.detail.fields.evaluatedTrials}
                  value={formatNumber(ranking.evaluated_trials, locale)}
                />
                <Metric
                  label={copy.detail.fields.eligibleTrials}
                  value={formatNumber(ranking.eligible_trials, locale)}
                />
                <Metric
                  label={copy.detail.fields.rejectedTrials}
                  value={formatNumber(ranking.rejected_trials, locale)}
                />
                <Metric label={copy.detail.fields.scoreVersion} value={ranking.score_version} />
              </dl>

              <Table scrollLabel={copy.detail.rankingTableScroll} className="min-w-[92rem]">
                <TableHeader>
                  <TableRow>
                    <TableHead>#</TableHead>
                    <TableHead>{copy.detail.fields.trial}</TableHead>
                    <TableHead>{copy.detail.fields.parameters}</TableHead>
                    <TableHead>{copy.detail.fields.score}</TableHead>
                    <TableHead>{copy.detail.fields.inSample}</TableHead>
                    <TableHead>{copy.detail.fields.outOfSample}</TableHead>
                    <TableHead>{copy.detail.fields.medianExcess}</TableHead>
                    <TableHead>{copy.detail.fields.positiveFolds}</TableHead>
                    <TableHead>{copy.detail.fields.tradedFolds}</TableHead>
                    <TableHead>{copy.detail.fields.dispersion}</TableHead>
                    <TableHead>{copy.detail.fields.drawdown}</TableHead>
                    <TableHead>{copy.detail.fields.gap}</TableHead>
                    <TableHead>{copy.detail.fields.evidence}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {ranking.entries.map((entry) => {
                    const evaluation = entry.evaluation;
                    const parameters = trialParameters(execution, evaluation.trial_number);

                    return (
                      <TableRow key={evaluation.experiment_id}>
                        <TableCell>{formatNumber(entry.position, locale)}</TableCell>
                        <TableCell>{formatNumber(evaluation.trial_number, locale)}</TableCell>
                        <TableCell>
                          <div className="flex min-w-48 flex-wrap gap-2">
                            {parameters.map((parameter) => (
                              <Badge key={parameter.name} variant="neutral">
                                {formatStrategyParameter(parameter, locale)}
                              </Badge>
                            ))}
                          </div>
                        </TableCell>
                        <TableCell dir="ltr">
                          {formatDecimal(evaluation.breakdown.total_score, locale)}
                        </TableCell>
                        <TableCell dir="ltr">
                          {formatObjectiveValue(evaluation.in_sample_objective_value, locale)}
                        </TableCell>
                        <TableCell dir="ltr">
                          {formatObjectiveValue(evaluation.out_of_sample_objective_value, locale)}
                        </TableCell>
                        <TableCell dir="ltr">
                          {formatPercent(evaluation.median_excess_return, locale)}
                        </TableCell>
                        <TableCell dir="ltr">
                          {formatPercent(evaluation.positive_return_fraction, locale)}
                        </TableCell>
                        <TableCell dir="ltr">
                          {formatNumber(evaluation.traded_folds, locale)}/
                          {formatNumber(evaluation.total_folds, locale)}
                        </TableCell>
                        <TableCell dir="ltr">
                          {formatPercent(evaluation.return_mean_absolute_deviation, locale)}
                        </TableCell>
                        <TableCell dir="ltr">
                          {formatPercent(evaluation.worst_max_drawdown_fraction, locale)}
                        </TableCell>
                        <TableCell dir="ltr">
                          {formatPercent(evaluation.generalization_gap, locale)}
                        </TableCell>
                        <TableCell>
                          <EvidenceLinks evaluation={evaluation} locale={locale} />
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{copy.detail.rejected}</CardTitle>
          <CardDescription>{copy.detail.rejectedDescription}</CardDescription>
        </CardHeader>
        <CardContent>
          {rejectedEvaluations.length === 0 ? (
            <p className="rounded-xl border border-app-border bg-app-surface-muted p-4 text-sm text-app-muted">
              {copy.detail.noRejected}
            </p>
          ) : (
            <Table scrollLabel={copy.detail.rejectedTableScroll} className="min-w-[52rem]">
              <TableHeader>
                <TableRow>
                  <TableHead>{copy.detail.fields.trial}</TableHead>
                  <TableHead>{copy.detail.fields.parameters}</TableHead>
                  <TableHead>{copy.detail.fields.reason}</TableHead>
                  <TableHead>{copy.detail.fields.tradedFolds}</TableHead>
                  <TableHead>{copy.detail.fields.evidence}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rejectedEvaluations.map((evaluation) => (
                  <TableRow key={evaluation.experiment_id}>
                    <TableCell>{formatNumber(evaluation.trial_number, locale)}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-2">
                        {trialParameters(execution, evaluation.trial_number).map((parameter) => (
                          <Badge key={parameter.name} variant="neutral">
                            {formatStrategyParameter(parameter, locale)}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell>
                      {evaluation.rejection_reasons
                        .map((reason) => copy.detail.rejectionReasons[reason])
                        .join(', ')}
                    </TableCell>
                    <TableCell dir="ltr">
                      {formatNumber(evaluation.traded_folds, locale)}/
                      {formatNumber(evaluation.total_folds, locale)}
                    </TableCell>
                    <TableCell>
                      <EvidenceLinks evaluation={evaluation} locale={locale} />
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
          <CardTitle>{copy.detail.configuration}</CardTitle>
          <CardDescription>{copy.detail.configurationDescription}</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric
              label={copy.detail.fields.horizon}
              value={formatNumber(execution.horizon_candles, locale)}
            />
            <Metric
              label={copy.detail.fields.totalFolds}
              value={
                robustnessPlan
                  ? formatNumber(robustnessPlan.total_folds, locale)
                  : copy.fields.notAvailable
              }
            />
            <Metric
              label={copy.detail.fields.validationRuns}
              value={
                robustnessPlan
                  ? formatNumber(robustnessPlan.validation_runs, locale)
                  : copy.fields.notAvailable
              }
            />
            <Metric
              label={copy.detail.fields.scoreVersion}
              value={robustnessPlan?.score_version ?? copy.fields.notAvailable}
            />
            <Metric
              label={copy.detail.fields.mode}
              value={
                robustnessPlan
                  ? copy.modes[robustnessPlan.walk_forward_config.mode]
                  : copy.fields.notAvailable
              }
            />
            <Metric
              label={copy.detail.fields.trainCandles}
              value={
                robustnessPlan
                  ? formatNumber(robustnessPlan.walk_forward_config.train_candles, locale)
                  : copy.fields.notAvailable
              }
            />
            <Metric
              label={copy.detail.fields.testCandles}
              value={
                robustnessPlan
                  ? formatNumber(robustnessPlan.walk_forward_config.test_candles, locale)
                  : copy.fields.notAvailable
              }
            />
            <Metric
              label={copy.detail.fields.stepCandles}
              value={
                robustnessPlan
                  ? formatNumber(robustnessPlan.walk_forward_config.step_candles, locale)
                  : copy.fields.notAvailable
              }
            />
            <Metric
              label={copy.detail.fields.gapCandles}
              value={
                robustnessPlan
                  ? formatNumber(robustnessPlan.walk_forward_config.gap_candles, locale)
                  : copy.fields.notAvailable
              }
            />
            <Metric
              label={copy.detail.fields.startingBalance}
              value={formatDecimal(execution.backtest_config.starting_balance, locale)}
            />
            <Metric
              label={copy.detail.fields.allocationFraction}
              value={formatPercent(execution.backtest_config.allocation_fraction, locale)}
            />
            <Metric
              label={copy.detail.fields.feeRate}
              value={formatPercent(execution.backtest_config.fee_rate, locale)}
            />
            <Metric
              label={copy.detail.fields.slippageRate}
              value={formatPercent(execution.backtest_config.slippage_rate, locale)}
            />
          </dl>
        </CardContent>
      </Card>
    </PageFrame>
  );
}
