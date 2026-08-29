'use client';

import { useState, type FormEvent } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getExperimentsCopy } from '@/components/dashboard/experiments-copy';
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
import type { ExperimentSortDirection, ExperimentSortField } from '@/lib/api/types';

export type ExperimentFilterValues = {
  datasetId: string;
  strategyName: string;
  strategyVersion: string;
  horizonCandles: string;
  createdAtFrom: string;
  createdAtTo: string;
  sortBy: ExperimentSortField;
  sortDirection: ExperimentSortDirection;
};

export const DEFAULT_EXPERIMENT_FILTERS: ExperimentFilterValues = {
  datasetId: '',
  strategyName: '',
  strategyVersion: '',
  horizonCandles: '',
  createdAtFrom: '',
  createdAtTo: '',
  sortBy: 'created_at',
  sortDirection: 'desc',
};

type ExperimentFilterPanelProps = {
  isLoading: boolean;
  locale: DashboardLocale;
  onApply: (filters: ExperimentFilterValues) => void;
};

export default function ExperimentFilterPanel({
  isLoading,
  locale,
  onApply,
}: ExperimentFilterPanelProps) {
  const copy = getExperimentsCopy(locale);
  const direction = locale === 'fa' ? 'rtl' : 'ltr';

  const [filters, setFilters] = useState<ExperimentFilterValues>(DEFAULT_EXPERIMENT_FILTERS);

  function updateFilter<Key extends keyof ExperimentFilterValues>(
    key: Key,
    value: ExperimentFilterValues[Key],
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
    setFilters(DEFAULT_EXPERIMENT_FILTERS);
    onApply(DEFAULT_EXPERIMENT_FILTERS);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{copy.filters.title}</CardTitle>
        <CardDescription>{copy.filters.description}</CardDescription>
      </CardHeader>

      <CardContent>
        <form onSubmit={submitFilters} className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Input
            dir="ltr"
            label={copy.filters.datasetId}
            placeholder={copy.filters.datasetIdPlaceholder}
            value={filters.datasetId}
            maxLength={100}
            disabled={isLoading}
            className="text-left"
            onChange={(event) => updateFilter('datasetId', event.target.value)}
          />

          <Input
            label={copy.filters.strategyName}
            placeholder={copy.filters.strategyNamePlaceholder}
            value={filters.strategyName}
            maxLength={100}
            disabled={isLoading}
            onChange={(event) => updateFilter('strategyName', event.target.value)}
          />

          <Input
            dir="ltr"
            label={copy.filters.strategyVersion}
            placeholder={copy.filters.strategyVersionPlaceholder}
            value={filters.strategyVersion}
            maxLength={30}
            disabled={isLoading}
            className="text-left"
            onChange={(event) => updateFilter('strategyVersion', event.target.value)}
          />

          <Input
            type="number"
            min={1}
            step={1}
            label={copy.filters.horizonCandles}
            value={filters.horizonCandles}
            disabled={isLoading}
            onChange={(event) => updateFilter('horizonCandles', event.target.value)}
          />

          <Input
            type="date"
            label={copy.filters.createdFrom}
            value={filters.createdAtFrom}
            max={filters.createdAtTo || undefined}
            disabled={isLoading}
            onChange={(event) => updateFilter('createdAtFrom', event.target.value)}
          />

          <Input
            type="date"
            label={copy.filters.createdTo}
            value={filters.createdAtTo}
            min={filters.createdAtFrom || undefined}
            disabled={isLoading}
            onChange={(event) => updateFilter('createdAtTo', event.target.value)}
          />

          <Select
            dir={direction}
            label={copy.filters.sortBy}
            value={filters.sortBy}
            disabled={isLoading}
            onValueChange={(value) => updateFilter('sortBy', value as ExperimentSortField)}
          >
            <SelectOption value="created_at">{copy.filters.sortFields.createdAt}</SelectOption>

            <SelectOption value="horizon_candles">
              {copy.filters.sortFields.horizonCandles}
            </SelectOption>
          </Select>

          <Select
            dir={direction}
            label={copy.filters.sortDirection}
            value={filters.sortDirection}
            disabled={isLoading}
            onValueChange={(value) =>
              updateFilter('sortDirection', value as ExperimentSortDirection)
            }
          >
            <SelectOption value="desc">{copy.filters.directions.descending}</SelectOption>

            <SelectOption value="asc">{copy.filters.directions.ascending}</SelectOption>
          </Select>

          <div className="flex flex-wrap gap-3 md:col-span-2 xl:col-span-4">
            <Button type="submit" isLoading={isLoading} loadingText={copy.filters.applying}>
              {copy.filters.apply}
            </Button>

            <Button type="button" variant="secondary" disabled={isLoading} onClick={resetFilters}>
              {copy.filters.reset}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
