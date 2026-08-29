'use client';

import { useRef, useState } from 'react';

import { type ActivityPeriod, getActivityCopy } from '@/components/dashboard/activity-copy';
import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  EmptyState,
  Pagination,
  Select,
  SelectOption,
  Spinner,
} from '@/components/ui';
import { getResearchActivity } from '@/lib/api/client';
import type { Page, ResearchActivityItem, ResearchActivityType } from '@/lib/api/types';

const PAGE_SIZE = 10;

type ActivityTypeFilter = 'all' | ResearchActivityType;

type ActivityFeedProps = {
  initialPage: Page<ResearchActivityItem>;
  locale: DashboardLocale;
};

function formatDate(value: string, locale: DashboardLocale): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function formatNumber(value: number, locale: DashboardLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
}

function createTimeRange(period: ActivityPeriod): {
  fromTime?: string;
  toTime?: string;
} {
  if (period === 'all') {
    return {};
  }

  const now = new Date();
  const fromTime = new Date(now);

  fromTime.setUTCDate(fromTime.getUTCDate() - (period === '7d' ? 7 : 30));

  return {
    fromTime: fromTime.toISOString(),
    toTime: now.toISOString(),
  };
}

export default function ActivityFeed({ initialPage, locale }: ActivityFeedProps) {
  const copy = getActivityCopy(locale);

  const [page, setPage] = useState(initialPage);
  const [activityType, setActivityType] = useState<ActivityTypeFilter>('all');
  const [period, setPeriod] = useState<ActivityPeriod>('all');
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);

  const requestSequence = useRef(0);

  const activityLabels: Record<ResearchActivityType, string> = {
    dataset: copy.dataset,
    experiment: copy.experiment,
    walk_forward_run: copy.walkForward,
  };

  async function loadActivity(
    offset: number,
    nextActivityType: ActivityTypeFilter = activityType,
    nextPeriod: ActivityPeriod = period,
  ): Promise<void> {
    const requestId = ++requestSequence.current;
    const timeRange = createTimeRange(nextPeriod);

    setIsLoading(true);
    setHasError(false);

    try {
      const result = await getResearchActivity({
        activityType: nextActivityType === 'all' ? undefined : nextActivityType,
        fromTime: timeRange.fromTime,
        toTime: timeRange.toTime,
        limit: PAGE_SIZE,
        offset,
      });

      if (requestId === requestSequence.current) {
        setPage(result);
      }
    } catch {
      if (requestId === requestSequence.current) {
        setHasError(true);
      }
    } finally {
      if (requestId === requestSequence.current) {
        setIsLoading(false);
      }
    }
  }

  function changeActivityType(nextType: ActivityTypeFilter): void {
    setActivityType(nextType);
    void loadActivity(0, nextType, period);
  }

  function changePeriod(nextPeriod: ActivityPeriod): void {
    setPeriod(nextPeriod);
    void loadActivity(0, activityType, nextPeriod);
  }

  const typeOptions: Array<{
    label: string;
    value: ActivityTypeFilter;
  }> = [
    {
      label: copy.all,
      value: 'all',
    },
    {
      label: copy.dataset,
      value: 'dataset',
    },
    {
      label: copy.experiment,
      value: 'experiment',
    },
    {
      label: copy.walkForward,
      value: 'walk_forward_run',
    },
  ];

  return (
    <Card>
      <CardHeader className="flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <CardTitle>{copy.title}</CardTitle>
          <CardDescription>{copy.description}</CardDescription>
        </div>

        <div className="flex flex-col gap-4">
          <div>
            <p className="mb-2 text-xs text-app-muted">{copy.typeFilter}</p>

            <div className="flex flex-wrap gap-2">
              {typeOptions.map((option) => {
                const isActive = activityType === option.value;

                return (
                  <Button
                    key={option.value}
                    size="sm"
                    variant={isActive ? 'primary' : 'secondary'}
                    disabled={isLoading}
                    aria-pressed={isActive}
                    onClick={() => changeActivityType(option.value)}
                  >
                    {option.label}
                  </Button>
                );
              })}
            </div>
          </div>

          <Select
            dir={locale === 'fa' ? 'rtl' : 'ltr'}
            label={copy.periodFilter}
            value={period}
            disabled={isLoading}
            containerClassName="min-w-48"
            onValueChange={(value) => changePeriod(value as ActivityPeriod)}
          >
            <SelectOption value="all">{copy.allTime}</SelectOption>
            <SelectOption value="7d">{copy.lastSevenDays}</SelectOption>
            <SelectOption value="30d">{copy.lastThirtyDays}</SelectOption>
          </Select>
        </div>
      </CardHeader>

      <CardContent className="relative min-h-52">
        {isLoading ? (
          <div className="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-app-overlay backdrop-blur-sm">
            <Spinner size="lg" label={copy.loading} className="text-app-accent" />
          </div>
        ) : null}

        {hasError ? (
          <EmptyState
            title={copy.errorTitle}
            description={copy.errorDescription}
            className="border-red-500/20 bg-red-500/10"
            icon={<span className="font-bold text-red-500">!</span>}
            action={
              <Button variant="danger" size="sm" onClick={() => void loadActivity(page.offset)}>
                {copy.retry}
              </Button>
            }
          />
        ) : page.items.length === 0 ? (
          <EmptyState title={copy.emptyTitle} description={copy.emptyDescription} />
        ) : (
          <div className="divide-y divide-app-border">
            {page.items.map((item) => (
              <div
                key={`${item.activity_type}-${item.resource_id}-${item.created_at}`}
                className="flex flex-col gap-3 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="info">{activityLabels[item.activity_type]}</Badge>

                    <p className="truncate text-sm font-medium text-app-foreground">{item.label}</p>
                  </div>

                  {item.strategy_name ? (
                    <p className="mt-2 text-xs text-app-muted">
                      {item.strategy_name}
                      {item.strategy_version ? ` · v${item.strategy_version}` : ''}
                    </p>
                  ) : null}

                  <p
                    dir="ltr"
                    className="mt-2 truncate text-left text-xs font-semibold text-app-subtle"
                  >
                    {item.resource_id}
                  </p>
                </div>

                <time dateTime={item.created_at} className="shrink-0 text-xs text-app-muted">
                  {formatDate(item.created_at, locale)}
                </time>
              </div>
            ))}
          </div>
        )}
      </CardContent>

      <div className="border-t border-app-border px-6 py-4">
        <div className="mb-4 text-xs text-app-muted">
          {copy.total}: {formatNumber(page.total, locale)}
        </div>

        <Pagination
          total={page.total}
          limit={page.limit}
          offset={page.offset}
          isLoading={isLoading}
          pageLabel={copy.page}
          previousLabel={copy.previous}
          nextLabel={copy.next}
          onOffsetChange={(offset) => void loadActivity(offset)}
        />
      </div>
    </Card>
  );
}
