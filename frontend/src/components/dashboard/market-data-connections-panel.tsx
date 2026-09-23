'use client';

import { type FormEvent, useState } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getConnectionsCopy } from '@/components/dashboard/connections-copy';
import HistoricalDatasetImportForm from '@/components/dashboard/historical-dataset-import-form';
import MarketDataImportHistory from '@/components/dashboard/market-data-import-history';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  Input,
  Pagination,
  Select,
  SelectOption,
  Spinner,
} from '@/components/ui';
import {
  createMarketDataConnection,
  disableMarketDataConnection,
  enableMarketDataConnection,
  getMarketDataConnections,
  testMarketDataConnection,
} from '@/lib/api/client';
import type {
  MarketDataConnection,
  MarketDataConnectionHealth,
  MarketDataProviderSummary,
  Page,
} from '@/lib/api/types';

const PAGE_SIZE = 12;

type ConnectionAction = 'test' | 'enable' | 'disable';

type MarketDataConnectionsPanelProps = {
  initialProviders: MarketDataProviderSummary[];
  initialPage: Page<MarketDataConnection>;
  locale: DashboardLocale;
};

function getInitialProviderId(providers: MarketDataProviderSummary[]): string {
  return (
    providers.find((provider) => provider.access_mode === 'direct')?.provider_id ??
    providers[0]?.provider_id ??
    ''
  );
}

function formatCandleLimit(value: number, locale: DashboardLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
}

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

function healthVariant(health: MarketDataConnectionHealth): 'neutral' | 'success' | 'danger' {
  if (health === 'healthy') {
    return 'success';
  }
  if (health === 'unhealthy') {
    return 'danger';
  }
  return 'neutral';
}

export default function MarketDataConnectionsPanel({
  initialProviders,
  initialPage,
  locale,
}: MarketDataConnectionsPanelProps) {
  const copy = getConnectionsCopy(locale);
  const [page, setPage] = useState(initialPage);
  const [providerId, setProviderId] = useState(getInitialProviderId(initialProviders));
  const [displayName, setDisplayName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [activeAction, setActiveAction] = useState<{
    connectionId: string;
    action: ConnectionAction;
  } | null>(null);
  const [hasError, setHasError] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [historyRefreshVersions, setHistoryRefreshVersions] = useState<Record<string, number>>({});

  function updateConnection(updated: MarketDataConnection): void {
    setPage((current) => ({
      ...current,
      items: current.items.map((connection) =>
        connection.connection_id === updated.connection_id ? updated : connection,
      ),
    }));
  }

  function markImportHistoryUpdated(connectionId: string): void {
    setHistoryRefreshVersions((current) => ({
      ...current,
      [connectionId]: (current[connectionId] ?? 0) + 1,
    }));
  }

  async function loadConnections(offset: number): Promise<void> {
    setIsLoading(true);
    setHasError(false);

    try {
      setPage(
        await getMarketDataConnections({
          limit: PAGE_SIZE,
          offset,
        }),
      );
    } catch {
      setHasError(true);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const normalizedName = displayName.trim();
    if (!providerId || !normalizedName) {
      return;
    }

    setIsCreating(true);
    setHasError(false);
    setFeedback(null);

    try {
      await createMarketDataConnection({
        provider_id: providerId,
        display_name: normalizedName,
      });
      setDisplayName('');
      setFeedback(copy.createdMessage);
      await loadConnections(0);
    } catch {
      setHasError(true);
    } finally {
      setIsCreating(false);
    }
  }

  async function runAction(
    connection: MarketDataConnection,
    action: ConnectionAction,
  ): Promise<void> {
    setActiveAction({
      connectionId: connection.connection_id,
      action,
    });
    setHasError(false);
    setFeedback(null);

    try {
      const updated =
        action === 'test'
          ? await testMarketDataConnection(connection.connection_id)
          : action === 'enable'
            ? await enableMarketDataConnection(connection.connection_id)
            : await disableMarketDataConnection(connection.connection_id);

      updateConnection(updated);
      setFeedback(
        action === 'test'
          ? copy.testedMessage
          : action === 'enable'
            ? copy.enabledMessage
            : copy.disabledMessage,
      );
    } catch {
      setHasError(true);
    } finally {
      setActiveAction(null);
    }
  }

  return (
    <div className="space-y-8">
      <section>
        <p className="text-xs font-semibold tracking-[0.25em] text-app-accent uppercase">
          {copy.eyebrow}
        </p>
        <h1 className="mt-3 text-3xl font-bold tracking-tight text-app-foreground sm:text-4xl">
          {copy.title}
        </h1>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-app-muted sm:text-base">
          {copy.description}
        </p>
        <p className="mt-4 rounded-2xl border border-app-warning-border bg-app-warning-soft px-4 py-3 text-sm leading-6 text-app-warning">
          {copy.readOnlyNotice}
        </p>
      </section>

      <section>
        <div className="mb-4">
          <h2 className="text-xl font-semibold text-app-foreground">{copy.providersTitle}</h2>
          <p className="mt-1 text-sm text-app-muted">{copy.providersDescription}</p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {initialProviders.map((provider) => (
            <Card key={provider.provider_id}>
              <CardHeader>
                <CardTitle>{provider.display_name}</CardTitle>
                <CardDescription>{provider.provider_id}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="mb-4">
                  <Badge variant={provider.requires_credentials ? 'warning' : 'success'}>
                    {provider.requires_credentials ? copy.provider : copy.noCredentials}
                  </Badge>
                </div>
                <dl className="space-y-3 text-sm">
                  <div className="flex items-start justify-between gap-4">
                    <dt className="text-app-muted">{copy.access}</dt>
                    <dd>
                      <Badge variant={provider.access_mode === 'direct' ? 'success' : 'warning'}>
                        {copy.accessModes[provider.access_mode]}
                      </Badge>
                    </dd>
                  </div>
                  <div className="flex items-start justify-between gap-4">
                    <dt className="text-app-muted">{copy.defaultPair}</dt>
                    <dd dir="ltr" className="text-end text-app-foreground">
                      {provider.default_pair.base_asset}/{provider.default_pair.quote_asset}
                    </dd>
                  </div>
                  <div className="flex items-start justify-between gap-4">
                    <dt className="text-app-muted">{copy.marketTypes}</dt>
                    <dd className="text-end text-app-foreground">
                      {provider.supported_market_types.join(', ')}
                    </dd>
                  </div>
                  <div className="flex items-start justify-between gap-4">
                    <dt className="text-app-muted">{copy.timeframes}</dt>
                    <dd dir="ltr" className="text-end text-app-foreground">
                      {provider.supported_timeframes.join(', ')}
                    </dd>
                  </div>
                  <div className="flex items-start justify-between gap-4">
                    <dt className="text-app-muted">{copy.historyCoverage}</dt>
                    <dd className="max-w-48 text-end text-app-foreground">
                      {provider.max_closed_candles === null
                        ? copy.fullHistory
                        : copy.recentHistory.replace(
                            '{count}',
                            formatCandleLimit(provider.max_closed_candles, locale),
                          )}
                    </dd>
                  </div>
                </dl>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>{copy.createTitle}</CardTitle>
          <CardDescription>{copy.createDescription}</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)_auto] md:items-end"
            onSubmit={(event) => void handleCreate(event)}
          >
            <Select
              label={copy.provider}
              value={providerId}
              onValueChange={setProviderId}
              disabled={isCreating || initialProviders.length === 0}
            >
              {initialProviders.map((provider) => (
                <SelectOption key={provider.provider_id} value={provider.provider_id}>
                  {provider.display_name}
                </SelectOption>
              ))}
            </Select>
            <Input
              label={copy.displayName}
              placeholder={copy.displayNamePlaceholder}
              value={displayName}
              maxLength={100}
              disabled={isCreating}
              onChange={(event) => setDisplayName(event.target.value)}
            />
            <Button
              type="submit"
              isLoading={isCreating}
              loadingText={copy.creating}
              disabled={!providerId || !displayName.trim()}
            >
              {copy.create}
            </Button>
          </form>
        </CardContent>
      </Card>

      <section aria-busy={isLoading}>
        <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-app-foreground">{copy.connectionsTitle}</h2>
            <p className="mt-1 text-sm text-app-muted">{copy.connectionsDescription}</p>
          </div>
          <Badge variant="info">
            {copy.total}:{' '}
            {new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(page.total)}
          </Badge>
        </div>

        <div aria-live="polite" className="mb-4 min-h-6 text-sm text-app-muted">
          {feedback}
        </div>

        {hasError ? (
          <ErrorState
            title={copy.errorTitle}
            description={copy.errorDescription}
            retryLabel={copy.retry}
            onRetry={() => void loadConnections(page.offset)}
          />
        ) : isLoading ? (
          <div className="flex min-h-48 items-center justify-center rounded-2xl border border-app-border bg-app-surface">
            <Spinner size="lg" label={copy.loading} className="text-app-accent" />
          </div>
        ) : page.items.length === 0 ? (
          <EmptyState title={copy.emptyTitle} description={copy.emptyDescription} />
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {page.items.map((connection) => {
              const providerMetadata = initialProviders.find(
                (provider) => provider.provider_id === connection.provider_id,
              );
              const isTesting =
                activeAction?.connectionId === connection.connection_id &&
                activeAction.action === 'test';
              const isEnabling =
                activeAction?.connectionId === connection.connection_id &&
                activeAction.action === 'enable';
              const isDisabling =
                activeAction?.connectionId === connection.connection_id &&
                activeAction.action === 'disable';
              const hasActiveAction = activeAction?.connectionId === connection.connection_id;

              return (
                <Card key={connection.connection_id}>
                  <CardHeader>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <CardTitle>{connection.display_name}</CardTitle>
                        <CardDescription className="mt-1">{connection.provider_id}</CardDescription>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant={connection.state === 'enabled' ? 'info' : 'neutral'}>
                          {copy.states[connection.state]}
                        </Badge>
                        <Badge variant={healthVariant(connection.health_status)}>
                          {copy.healthStatuses[connection.health_status]}
                        </Badge>
                        {providerMetadata ? (
                          <Badge
                            variant={
                              providerMetadata.access_mode === 'direct' ? 'success' : 'warning'
                            }
                          >
                            {copy.accessModes[providerMetadata.access_mode]}
                          </Badge>
                        ) : null}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <dl className="space-y-3 text-sm">
                      <div className="flex justify-between gap-4">
                        <dt className="text-app-muted">{copy.state}</dt>
                        <dd className="text-app-foreground">{copy.states[connection.state]}</dd>
                      </div>
                      <div className="flex justify-between gap-4">
                        <dt className="text-app-muted">{copy.health}</dt>
                        <dd className="text-app-foreground">
                          {copy.healthStatuses[connection.health_status]}
                        </dd>
                      </div>
                      <div className="flex justify-between gap-4">
                        <dt className="text-app-muted">{copy.lastTested}</dt>
                        <dd className="text-end text-app-foreground">
                          {connection.last_tested_at
                            ? formatDate(connection.last_tested_at, locale)
                            : copy.neverTested}
                        </dd>
                      </div>
                    </dl>

                    {connection.last_error ? (
                      <div className="mt-4 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-500">
                        <span className="font-semibold">{copy.lastError}: </span>
                        {connection.last_error}
                      </div>
                    ) : null}

                    <div className="mt-5 flex flex-wrap gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        isLoading={isTesting}
                        loadingText={copy.testing}
                        disabled={Boolean(hasActiveAction)}
                        onClick={() => void runAction(connection, 'test')}
                      >
                        {copy.test}
                      </Button>
                      <Button
                        size="sm"
                        isLoading={isEnabling}
                        loadingText={copy.enabling}
                        disabled={
                          Boolean(hasActiveAction) ||
                          connection.health_status !== 'healthy' ||
                          connection.state === 'enabled'
                        }
                        onClick={() => void runAction(connection, 'enable')}
                      >
                        {copy.enable}
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        isLoading={isDisabling}
                        loadingText={copy.disabling}
                        disabled={Boolean(hasActiveAction) || connection.state === 'disabled'}
                        onClick={() => void runAction(connection, 'disable')}
                      >
                        {copy.disable}
                      </Button>
                    </div>

                    {connection.state === 'enabled' && connection.health_status === 'healthy' ? (
                      <HistoricalDatasetImportForm
                        connection={connection}
                        locale={locale}
                        provider={providerMetadata}
                        onImported={() => markImportHistoryUpdated(connection.connection_id)}
                      />
                    ) : null}

                    <MarketDataImportHistory
                      connectionId={connection.connection_id}
                      locale={locale}
                      refreshVersion={historyRefreshVersions[connection.connection_id] ?? 0}
                    />
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </section>

      {!hasError && page.total > 0 ? (
        <section className="rounded-2xl border border-app-border bg-app-surface px-5 py-4">
          <Pagination
            total={page.total}
            limit={page.limit}
            offset={page.offset}
            isLoading={isLoading}
            pageLabel={copy.page}
            previousLabel={copy.previous}
            nextLabel={copy.next}
            onOffsetChange={(offset) => void loadConnections(offset)}
          />
        </section>
      ) : null}
    </div>
  );
}
