'use client';

import { useMemo, useState } from 'react';

import { getExperimentAcceptanceCopy } from '@/components/dashboard/experiment-acceptance-copy';
import type { ExperimentDetailLocale } from '@/components/dashboard/experiment-detail-copy';
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
} from '@/components/ui';
import { getExperimentReportByPreset, getExperimentReportCsv } from '@/lib/api/client';
import type {
  AcceptancePolicyPreset,
  ExperimentAcceptanceCheck,
  ExperimentAcceptanceOutcome,
  PresetExperimentResearchReport,
} from '@/lib/api/types';

type ExperimentAcceptancePanelProps = {
  experimentId: string;
  locale: ExperimentDetailLocale;
  presets: AcceptancePolicyPreset[];
};

function formatInteger(value: number, locale: ExperimentDetailLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
}

function formatPercent(value: string, locale: ExperimentDetailLocale): string {
  const parsedValue = Number(value);

  if (!Number.isFinite(parsedValue)) {
    return value;
  }

  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    style: 'percent',
    maximumFractionDigits: 2,
  }).format(parsedValue);
}

function formatCheckValue(
  check: ExperimentAcceptanceCheck,
  value: string,
  locale: ExperimentDetailLocale,
): string {
  if (check.name === 'minimum_total_trades') {
    return formatInteger(Number(value), locale);
  }

  return formatPercent(value, locale);
}

function outcomeVariant(outcome: ExperimentAcceptanceOutcome): 'success' | 'danger' | 'warning' {
  if (outcome === 'accepted') {
    return 'success';
  }

  if (outcome === 'rejected') {
    return 'danger';
  }

  return 'warning';
}

export function ExperimentAcceptancePanel({
  experimentId,
  locale,
  presets,
}: ExperimentAcceptancePanelProps) {
  const copy = getExperimentAcceptanceCopy(locale);
  const direction = locale === 'fa' ? 'rtl' : 'ltr';

  const [selectedPresetId, setSelectedPresetId] = useState(presets[0]?.preset_id ?? '');
  const [report, setReport] = useState<PresetExperimentResearchReport | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [hasDownloadError, setHasDownloadError] = useState(false);

  const selectedPreset = useMemo(
    () => presets.find((preset) => preset.preset_id === selectedPresetId) ?? null,
    [presets, selectedPresetId],
  );

  async function runAssessment(): Promise<void> {
    if (!selectedPresetId) {
      return;
    }

    setIsLoading(true);
    setHasError(false);

    try {
      const result = await getExperimentReportByPreset(experimentId, selectedPresetId);

      setReport(result);
    } catch {
      setHasError(true);
      setReport(null);
    } finally {
      setIsLoading(false);
    }
  }

  async function downloadCsvReport(): Promise<void> {
    if (!report) {
      return;
    }

    setIsDownloading(true);
    setHasDownloadError(false);

    try {
      const presetId = report.preset.preset_id;

      const file = await getExperimentReportCsv(experimentId, presetId);

      const downloadUrl = URL.createObjectURL(file);
      const downloadLink = document.createElement('a');

      downloadLink.href = downloadUrl;
      downloadLink.download = `experiment-report-${experimentId}-${presetId}.csv`;

      document.body.appendChild(downloadLink);
      downloadLink.click();
      downloadLink.remove();

      window.setTimeout(() => {
        URL.revokeObjectURL(downloadUrl);
      }, 0);
    } catch {
      setHasDownloadError(true);
    } finally {
      setIsDownloading(false);
    }
  }

  return (
    <Card dir={direction}>
      <CardHeader>
        <CardTitle>{copy.title}</CardTitle>
        <CardDescription>{copy.description}</CardDescription>
      </CardHeader>

      <CardContent className="space-y-6">
        <div className="grid items-end gap-4 lg:grid-cols-[1fr_auto]">
          <Select
            dir={direction}
            label={copy.policyLabel}
            placeholder={copy.policyPlaceholder}
            value={selectedPresetId}
            disabled={isLoading || presets.length === 0}
            onValueChange={(value) => {
              setSelectedPresetId(value);
              setReport(null);
              setHasError(false);
              setHasDownloadError(false);
            }}
          >
            {presets.map((preset) => (
              <SelectOption key={preset.preset_id} value={preset.preset_id}>
                {copy.presetNames[preset.name] ?? preset.name} — v
                {formatInteger(preset.version, locale)}
              </SelectOption>
            ))}
          </Select>

          <Button
            variant="primary"
            disabled={!selectedPresetId}
            isLoading={isLoading}
            loadingText={copy.runningAssessment}
            onClick={() => void runAssessment()}
          >
            {copy.runAssessment}
          </Button>
        </div>

        {selectedPreset ? (
          <div className="space-y-4 rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-200">{copy.thresholds}</h3>

              <p className="mt-2 text-sm leading-6 text-slate-500">{selectedPreset.description}</p>
            </div>

            <dl className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-slate-800 p-3">
                <dt className="text-xs text-slate-500">{copy.minimumTrades}</dt>
                <dd className="mt-2 font-semibold text-slate-200">
                  {formatInteger(selectedPreset.policy.minimum_total_trades, locale)}
                </dd>
              </div>

              <div className="rounded-xl border border-slate-800 p-3">
                <dt className="text-xs text-slate-500">{copy.minimumExcessReturn}</dt>
                <dd className="mt-2 font-semibold text-slate-200">
                  {formatPercent(selectedPreset.policy.minimum_excess_return, locale)}
                </dd>
              </div>

              <div className="rounded-xl border border-slate-800 p-3">
                <dt className="text-xs text-slate-500">{copy.maximumDrawdown}</dt>
                <dd className="mt-2 font-semibold text-slate-200">
                  {formatPercent(selectedPreset.policy.maximum_drawdown_fraction, locale)}
                </dd>
              </div>
            </dl>
          </div>
        ) : null}

        {hasError ? (
          <div role="alert" className="rounded-xl border border-red-400/20 bg-red-400/5 p-4">
            <p className="text-sm text-red-300">{copy.error}</p>

            <Button
              className="mt-4"
              size="sm"
              variant="danger"
              onClick={() => void runAssessment()}
            >
              {copy.retry}
            </Button>
          </div>
        ) : null}

        {report ? (
          <div className="space-y-4 border-t border-slate-800 pt-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-base font-semibold text-white">{copy.result}</h3>

              <div className="flex flex-wrap items-center gap-3">
                <Badge variant={outcomeVariant(report.report.acceptance.outcome)}>
                  {copy.outcomes[report.report.acceptance.outcome]}
                </Badge>

                <Button
                  size="sm"
                  variant="secondary"
                  isLoading={isDownloading}
                  loadingText={copy.downloadingCsv}
                  onClick={() => void downloadCsvReport()}
                >
                  {copy.downloadCsv}
                </Button>
              </div>
            </div>

            {hasDownloadError ? (
              <p
                role="alert"
                className="rounded-xl border border-red-400/20 bg-red-400/5 p-3 text-sm text-red-300"
              >
                {copy.downloadError}
              </p>
            ) : null}

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/5 p-4">
                <p className="text-xs text-emerald-300">{copy.passedChecks}</p>
                <p className="mt-2 text-xl font-bold text-emerald-200">
                  {formatInteger(report.report.passed_checks, locale)}
                </p>
              </div>

              <div className="rounded-xl border border-red-400/20 bg-red-400/5 p-4">
                <p className="text-xs text-red-300">{copy.failedChecks}</p>
                <p className="mt-2 text-xl font-bold text-red-200">
                  {formatInteger(report.report.failed_checks, locale)}
                </p>
              </div>
            </div>

            <div className="space-y-3">
              {report.report.acceptance.checks.map((check) => (
                <div
                  key={check.name}
                  className="grid gap-4 rounded-xl border border-slate-800 bg-slate-950/50 p-4 sm:grid-cols-[1fr_auto_auto]"
                >
                  <div>
                    <p className="text-sm font-medium text-slate-200">{copy.checks[check.name]}</p>

                    <Badge className="mt-2" variant={check.passed ? 'success' : 'danger'}>
                      {check.passed ? copy.passed : copy.failed}
                    </Badge>
                  </div>

                  <div>
                    <p className="text-xs text-slate-500">{copy.actualValue}</p>
                    <p className="mt-2 text-sm font-semibold text-slate-200">
                      {formatCheckValue(check, check.actual_value, locale)}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs text-slate-500">{copy.thresholdValue}</p>
                    <p className="mt-2 text-sm font-semibold text-slate-200">
                      {formatCheckValue(check, check.threshold_value, locale)}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            <p className="rounded-xl border border-amber-400/20 bg-amber-400/5 p-4 text-sm leading-6 text-amber-200/80">
              {copy.historicalOnly}
            </p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
