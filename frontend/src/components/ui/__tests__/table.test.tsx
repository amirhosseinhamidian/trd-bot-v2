import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

describe('Table', () => {
  it('exposes a labeled keyboard-focusable region when a scroll label is provided', () => {
    render(
      <Table scrollLabel="Historical candles table">
        <TableBody>
          <TableRow>
            <TableCell>BTC/USDT</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );

    const region = screen.getByRole('region', {
      name: 'Historical candles table',
    });

    expect(region).toHaveAttribute('tabindex', '0');
    expect(region).toHaveClass(
      'overflow-x-auto',
      'overscroll-x-contain',
      'focus-visible:ring-2',
      'focus-visible:ring-app-accent',
    );
  });

  it('gives column headers an explicit column scope', () => {
    render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Dataset</TableHead>
          </TableRow>
        </TableHeader>
      </Table>,
    );

    expect(
      screen.getByRole('columnheader', {
        name: 'Dataset',
      }),
    ).toHaveAttribute('scope', 'col');
  });

  it('does not add an unnamed landmark when no scroll label is provided', () => {
    render(
      <Table>
        <TableBody>
          <TableRow>
            <TableCell>BTC/USDT</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );

    expect(screen.queryByRole('region')).not.toBeInTheDocument();
  });
});
