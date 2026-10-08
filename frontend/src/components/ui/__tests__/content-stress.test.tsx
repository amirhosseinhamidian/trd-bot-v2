import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { PageHeader } from '@/components/platform/page-header';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorState } from '@/components/ui/error-state';

const LONG_IDENTIFIER = `candidate_${'a'.repeat(128)}_BTC-USDT`;
const LONG_COPY = `پیام${'بسیارطولانی'.repeat(24)}`;

describe('content stress contracts', () => {
  it('contains long mixed-direction content inside shared layout primitives', () => {
    render(
      <main dir="rtl">
        <PageHeader
          title={LONG_COPY}
          metadata={<code dir="ltr">{LONG_IDENTIFIER}</code>}
          actions={<Button>{LONG_COPY}</Button>}
        />

        <Card data-testid="stress-card">
          <CardHeader data-testid="stress-card-header">
            <CardTitle>{LONG_COPY}</CardTitle>
            <CardDescription dir="ltr">{LONG_IDENTIFIER}</CardDescription>
          </CardHeader>
          <CardContent>
            <Badge>{LONG_COPY}</Badge>
          </CardContent>
        </Card>
      </main>,
    );

    const heading = screen.getByRole('heading', { level: 1, name: LONG_COPY });
    const identifier = screen.getAllByText(LONG_IDENTIFIER)[0];
    const action = screen.getByRole('button', { name: LONG_COPY });
    const badge = screen.getByText(LONG_COPY, { selector: 'span.inline-flex' });

    expect(heading.closest('main')).toHaveAttribute('dir', 'rtl');
    expect(heading).toHaveClass('max-w-full', 'break-words');
    expect(identifier).toHaveAttribute('dir', 'ltr');
    expect(identifier.parentElement).toHaveClass('min-w-0', 'break-words');
    expect(action).toHaveClass('min-w-0', 'max-w-full');
    expect(action.firstElementChild).toHaveClass('min-w-0', 'max-w-full', 'break-words');
    expect(screen.getByTestId('stress-card')).toHaveClass('min-w-0');
    expect(screen.getByTestId('stress-card-header')).toHaveClass('min-w-0');
    expect(badge).toHaveClass('max-w-full', 'whitespace-normal', 'break-words');
  });

  it('wraps long empty and error copy without weakening live-region semantics', () => {
    const { rerender } = render(
      <EmptyState
        title={LONG_COPY}
        description={LONG_IDENTIFIER}
        action={<Button>{LONG_COPY}</Button>}
      />,
    );

    const status = screen.getByRole('status');

    expect(status).toHaveClass('min-w-0');
    expect(screen.getByRole('heading', { name: LONG_COPY })).toHaveClass(
      'max-w-full',
      'break-words',
    );
    expect(screen.getByText(LONG_IDENTIFIER)).toHaveClass('max-w-full', 'break-words');

    rerender(
      <ErrorState
        title={LONG_COPY}
        description={LONG_COPY}
        details={<code dir="ltr">{LONG_IDENTIFIER}</code>}
        retryLabel={LONG_COPY}
        onRetry={() => undefined}
      />,
    );

    const alert = screen.getByRole('alert');
    const details = screen.getByText(LONG_IDENTIFIER).parentElement;

    expect(alert).toHaveAttribute('aria-live', 'assertive');
    expect(details).toHaveClass('min-w-0', 'max-w-full', 'break-words');
    expect(screen.getByRole('button', { name: LONG_COPY })).toHaveClass('max-w-full');
  });
});
