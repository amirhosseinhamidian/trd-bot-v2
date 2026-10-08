'use client';

import { useId, useState, type ReactNode } from 'react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils/cn';

export type ResponsiveChartItem = {
  chart: ReactNode;
  description?: string;
  id: string;
  label: string;
  summary: ReactNode;
};

type ResponsiveChartGroupProps = {
  items: ResponsiveChartItem[];
  selectorLabel: string;
};

export function ResponsiveChartGroup({ items, selectorLabel }: ResponsiveChartGroupProps) {
  const instanceId = useId();
  const [requestedItemId, setRequestedItemId] = useState(items[0]?.id ?? '');
  const activeItemId = items.some((item) => item.id === requestedItemId)
    ? requestedItemId
    : (items[0]?.id ?? '');

  if (items.length === 0) {
    return null;
  }

  return (
    <div className="space-y-8">
      {items.length > 1 ? (
        <div className="md:hidden">
          <p className="mb-3 text-sm font-semibold text-app-foreground">{selectorLabel}</p>
          <div role="group" aria-label={selectorLabel} className="grid gap-2 sm:grid-cols-2">
            {items.map((item) => {
              const isActive = item.id === activeItemId;
              const panelId = `${instanceId}-${item.id}-panel`;

              return (
                <Button
                  key={item.id}
                  aria-controls={panelId}
                  aria-pressed={isActive}
                  className="min-h-11 w-full"
                  variant={isActive ? 'primary' : 'secondary'}
                  onClick={() => setRequestedItemId(item.id)}
                >
                  {item.label}
                </Button>
              );
            })}
          </div>
        </div>
      ) : null}

      {items.map((item, index) => {
        const isActive = item.id === activeItemId;
        const panelId = `${instanceId}-${item.id}-panel`;

        return (
          <section
            key={item.id}
            id={panelId}
            data-testid={`responsive-chart-panel-${item.id}`}
            className={cn(
              'min-w-0',
              isActive ? 'block' : 'hidden md:block',
              index > 0 && 'md:border-t md:border-app-border md:pt-8',
            )}
          >
            <div className="mb-4">
              <h3 className="text-base font-semibold text-app-foreground">{item.label}</h3>
              {item.description ? (
                <p className="mt-1 text-sm leading-6 text-app-muted">{item.description}</p>
              ) : null}
            </div>

            <div className="mb-4 rounded-xl border border-app-border bg-app-surface-muted p-4 text-sm">
              {item.summary}
            </div>

            {item.chart}
          </section>
        );
      })}
    </div>
  );
}
