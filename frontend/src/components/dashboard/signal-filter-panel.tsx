'use client';

import { useState, type FormEvent } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getSignalsCopy } from '@/components/dashboard/signals-copy';
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Select,
  SelectOption,
} from '@/components/ui';
import type {
  ExperimentSignalSortDirection,
  ExperimentSummary,
  SignalDirection,
} from '@/lib/api/types';

export type SignalFilterValues = {
  experimentId: string;
  direction: SignalDirection | 'all';
  candleCloseTimeFrom: string;
  candleCloseTimeTo: string;
  sortDirection: ExperimentSignalSortDirection;
};

type SignalFilterPanelProps = {
  experiments: ExperimentSummary[];
  initialExperimentId: string;
  isLoading: boolean;
  locale: DashboardLocale;
  onApply: (filters: SignalFilterValues) => void;
};

function createDefaultFilters(experimentId: string): SignalFilterValues {
  return {
    experimentId,
    direction: 'all',
    candleCloseTimeFrom: '',
    candleCloseTimeTo: '',
    sortDirection: 'desc',
  };
}

export default function SignalFilterPanel({
  experiments,
  initialExperimentId,
  isLoading,
  locale,
  onApply,
}: SignalFilterPanelProps) {
  const copy = getSignalsCopy(locale);
  const direction = locale === 'fa' ? 'rtl' : 'ltr';

  const [filters, setFilters] = useState<SignalFilterValues>(() =>
    createDefaultFilters(initialExperimentId),
  );

  function updateFilter<Key extends keyof SignalFilterValues>(
    key: Key,
    value: SignalFilterValues[Key],
  ): void {
    setFilters((current) => ({
      ...current,
      [key]: value,
    }));
  }

  function submitFilters(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onApply(filters);
  }

  function resetFilters(): void {
    const defaultFilters = createDefaultFilters(initialExperimentId);

    setFilters(defaultFilters);
    onApply(defaultFilters);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{copy.filters.title}</CardTitle>
        <CardDescription>{copy.filters.description}</CardDescription>
      </CardHeader>

      <CardContent>
        <form onSubmit={submitFilters} className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Select
            dir={direction}
            label={copy.filters.experiment}
            placeholder={copy.filters.experimentPlaceholder}
            value={filters.experimentId}
            disabled={isLoading || experiments.length === 0}
            onValueChange={(value) => updateFilter('experimentId', value)}
          >
            {experiments.map((experiment) => (
              <SelectOption key={experiment.experiment_id} value={experiment.experiment_id}>
                {experiment.strategy_name} · {experiment.experiment_id.slice(-6)}
              </SelectOption>
            ))}
          </Select>

          <Select
            dir={direction}
            label={copy.filters.direction}
            value={filters.direction}
            disabled={isLoading}
            onValueChange={(value) => updateFilter('direction', value as SignalDirection | 'all')}
          >
            <SelectOption value="all">{copy.filters.allDirections}</SelectOption>
            <SelectOption value="long">{copy.directions.long}</SelectOption>
            <SelectOption value="short">{copy.directions.short}</SelectOption>
            <SelectOption value="neutral">{copy.directions.neutral}</SelectOption>
          </Select>

          <Input
            type="date"
            label={copy.filters.closedFrom}
            value={filters.candleCloseTimeFrom}
            max={filters.candleCloseTimeTo || undefined}
            disabled={isLoading}
            onChange={(event) => updateFilter('candleCloseTimeFrom', event.target.value)}
          />

          <Input
            type="date"
            label={copy.filters.closedTo}
            value={filters.candleCloseTimeTo}
            min={filters.candleCloseTimeFrom || undefined}
            disabled={isLoading}
            onChange={(event) => updateFilter('candleCloseTimeTo', event.target.value)}
          />

          <Select
            dir={direction}
            label={copy.filters.sortDirection}
            value={filters.sortDirection}
            disabled={isLoading}
            onValueChange={(value) =>
              updateFilter('sortDirection', value as ExperimentSignalSortDirection)
            }
          >
            <SelectOption value="desc">{copy.filters.descending}</SelectOption>
            <SelectOption value="asc">{copy.filters.ascending}</SelectOption>
          </Select>

          <div className="flex flex-wrap gap-3 md:col-span-2 xl:col-span-4">
            <Button
              type="submit"
              disabled={!filters.experimentId}
              isLoading={isLoading}
              loadingText={copy.filters.applying}
            >
              {copy.filters.apply}
            </Button>

            <Button
              type="button"
              variant="secondary"
              disabled={isLoading || experiments.length === 0}
              onClick={resetFilters}
            >
              {copy.filters.reset}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
