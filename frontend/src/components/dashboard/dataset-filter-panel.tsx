'use client';

import { useState, type FormEvent } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getDatasetsCopy } from '@/components/dashboard/datasets-copy';
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
import type { DatasetSortDirection, DatasetSortField, DatasetTimeframe } from '@/lib/api/types';

export type DatasetFilterValues = {
  source: string;
  baseAsset: string;
  quoteAsset: string;
  timeframe: 'all' | DatasetTimeframe;
  createdAtFrom: string;
  createdAtTo: string;
  sortBy: DatasetSortField;
  sortDirection: DatasetSortDirection;
};

export const DEFAULT_DATASET_FILTERS: DatasetFilterValues = {
  source: '',
  baseAsset: '',
  quoteAsset: '',
  timeframe: 'all',
  createdAtFrom: '',
  createdAtTo: '',
  sortBy: 'created_at',
  sortDirection: 'desc',
};

type DatasetFilterPanelProps = {
  isLoading: boolean;
  locale: DashboardLocale;
  onApply: (filters: DatasetFilterValues) => void;
};

export default function DatasetFilterPanel({
  isLoading,
  locale,
  onApply,
}: DatasetFilterPanelProps) {
  const copy = getDatasetsCopy(locale);
  const direction = locale === 'fa' ? 'rtl' : 'ltr';

  const [filters, setFilters] = useState<DatasetFilterValues>(DEFAULT_DATASET_FILTERS);

  function updateFilter<Key extends keyof DatasetFilterValues>(
    key: Key,
    value: DatasetFilterValues[Key],
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
    setFilters(DEFAULT_DATASET_FILTERS);
    onApply(DEFAULT_DATASET_FILTERS);
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
            label={copy.filters.source}
            placeholder={copy.filters.sourcePlaceholder}
            value={filters.source}
            maxLength={50}
            disabled={isLoading}
            onChange={(event) => updateFilter('source', event.target.value)}
          />

          <Input
            dir="ltr"
            label={copy.filters.baseAsset}
            placeholder={copy.filters.baseAssetPlaceholder}
            value={filters.baseAsset}
            minLength={2}
            maxLength={15}
            pattern="[A-Za-z0-9]+"
            disabled={isLoading}
            className="text-left uppercase"
            onChange={(event) => updateFilter('baseAsset', event.target.value.toUpperCase())}
          />

          <Input
            dir="ltr"
            label={copy.filters.quoteAsset}
            placeholder={copy.filters.quoteAssetPlaceholder}
            value={filters.quoteAsset}
            minLength={2}
            maxLength={15}
            pattern="[A-Za-z0-9]+"
            disabled={isLoading}
            className="text-left uppercase"
            onChange={(event) => updateFilter('quoteAsset', event.target.value.toUpperCase())}
          />

          <Select
            dir={direction}
            label={copy.filters.timeframe}
            value={filters.timeframe}
            disabled={isLoading}
            onValueChange={(value) =>
              updateFilter('timeframe', value as DatasetFilterValues['timeframe'])
            }
          >
            <SelectOption value="all">{copy.filters.allTimeframes}</SelectOption>
            <SelectOption value="15m">15m</SelectOption>
            <SelectOption value="1h">1h</SelectOption>
            <SelectOption value="4h">4h</SelectOption>
            <SelectOption value="1d">1d</SelectOption>
          </Select>

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
            onValueChange={(value) => updateFilter('sortBy', value as DatasetSortField)}
          >
            <SelectOption value="created_at">{copy.filters.sortFields.createdAt}</SelectOption>
            <SelectOption value="start_time">{copy.filters.sortFields.startTime}</SelectOption>
            <SelectOption value="candle_count">{copy.filters.sortFields.candleCount}</SelectOption>
          </Select>

          <Select
            dir={direction}
            label={copy.filters.sortDirection}
            value={filters.sortDirection}
            disabled={isLoading}
            onValueChange={(value) => updateFilter('sortDirection', value as DatasetSortDirection)}
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
