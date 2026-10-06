import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

describe('Card', () => {
  it('uses the semantic surface and responsive spacing contract', () => {
    render(
      <Card data-testid="card">
        <CardHeader data-testid="header">
          <CardTitle>Dataset quality</CardTitle>
          <CardDescription>Latest immutable version</CardDescription>
        </CardHeader>
        <CardContent data-testid="content">98%</CardContent>
        <CardFooter data-testid="footer">Updated now</CardFooter>
      </Card>,
    );

    expect(screen.getByTestId('card')).toHaveClass(
      'border-app-border',
      'bg-app-surface',
      'shadow-app-surface',
    );
    expect(screen.getByTestId('header')).toHaveClass('p-5', 'sm:p-6');
    expect(screen.getByTestId('content')).toHaveClass('px-5', 'sm:px-6');
    expect(screen.getByTestId('footer')).toHaveClass('border-app-border', 'px-5', 'sm:px-6');
    expect(screen.getByRole('heading', { name: 'Dataset quality', level: 2 })).toHaveClass(
      'text-app-foreground',
    );
    expect(screen.getByText('Latest immutable version')).toHaveClass('text-app-muted');
  });
});
