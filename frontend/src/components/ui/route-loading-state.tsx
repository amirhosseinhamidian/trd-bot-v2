import type { HTMLAttributes } from 'react';

import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils/cn';

export type RouteLoadingVariant = 'overview' | 'catalog' | 'detail' | 'monitoring';

export type RouteLoadingStateProps = HTMLAttributes<HTMLDivElement> & {
  label?: string;
  variant?: RouteLoadingVariant;
};

function HeaderSkeleton() {
  return (
    <section className="space-y-4">
      <Skeleton className="h-3 w-48" />
      <Skeleton className="h-10 w-72 max-w-full" />
      <Skeleton className="h-4 w-full max-w-3xl" />
    </section>
  );
}

function OverviewSkeleton() {
  return (
    <>
      <HeaderSkeleton />

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-32" />
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.35fr_1fr]">
        <Skeleton className="h-80" />
        <Skeleton className="h-80" />
      </section>

      <Skeleton className="h-80" />
    </>
  );
}

function CatalogSkeleton() {
  return (
    <>
      <HeaderSkeleton />

      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-52 max-w-full" />
          <Skeleton className="h-4 w-96 max-w-full" />
        </CardHeader>

        <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, index) => (
            <Skeleton key={index} className="h-11" />
          ))}
        </CardContent>
      </Card>

      <section className="grid gap-4 lg:grid-cols-2">
        {Array.from({ length: 4 }).map((_, index) => (
          <Card key={index}>
            <CardHeader>
              <Skeleton className="h-6 w-48 max-w-full" />
              <Skeleton className="h-4 w-full" />
            </CardHeader>

            <CardContent className="space-y-4">
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-28 w-full" />
              <Skeleton className="h-10 w-full" />
            </CardContent>
          </Card>
        ))}
      </section>
    </>
  );
}

function DetailSkeleton() {
  const sectionItemCounts = [8, 8, 6, 4];

  return (
    <>
      <HeaderSkeleton />

      {sectionItemCounts.map((itemCount, sectionIndex) => (
        <Card key={sectionIndex}>
          <CardHeader>
            <Skeleton className="h-6 w-52 max-w-full" />
            <Skeleton className="h-4 w-80 max-w-full" />
          </CardHeader>

          <CardContent>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {Array.from({ length: itemCount }).map((_, itemIndex) => (
                <Skeleton key={itemIndex} className="h-24" />
              ))}
            </div>
          </CardContent>
        </Card>
      ))}
    </>
  );
}

function MonitoringSkeleton() {
  return (
    <>
      <HeaderSkeleton />

      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-52 max-w-full" />
          <Skeleton className="h-4 w-80 max-w-full" />
        </CardHeader>

        <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-48" />
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-64 max-w-full" />
          <Skeleton className="h-4 w-96 max-w-full" />
        </CardHeader>

        <CardContent className="grid gap-4 lg:grid-cols-2">
          {Array.from({ length: 2 }).map((_, index) => (
            <Skeleton key={index} className="h-40" />
          ))}
        </CardContent>
      </Card>
    </>
  );
}

function LoadingContent({ variant }: { variant: RouteLoadingVariant }) {
  if (variant === 'overview') {
    return <OverviewSkeleton />;
  }

  if (variant === 'detail') {
    return <DetailSkeleton />;
  }

  if (variant === 'monitoring') {
    return <MonitoringSkeleton />;
  }

  return <CatalogSkeleton />;
}

export function RouteLoadingState({
  className,
  label = 'Loading content / در حال بارگذاری محتوا',
  variant = 'catalog',
  ...props
}: RouteLoadingStateProps) {
  return (
    <div
      {...props}
      role="status"
      aria-label={label}
      aria-busy="true"
      aria-live="polite"
      className={cn('space-y-8', className)}
    >
      <LoadingContent variant={variant} />
    </div>
  );
}
