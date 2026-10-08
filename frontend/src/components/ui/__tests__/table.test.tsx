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
      'min-w-0',
      'max-w-full',
      'touch-pan-x',
      'touch-pan-y',
      'overflow-x-auto',
      'overflow-y-hidden',
      'overscroll-x-contain',
      '[scrollbar-gutter:stable]',
      'focus-visible:border-app-control-border',
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

  it('propagates direction and provides compact responsive cells', () => {
    render(
      <Table dir="rtl" scrollLabel="جدول نتایج">
        <TableHeader>
          <TableRow>
            <TableHead>مجموعه‌داده</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow data-state="selected">
            <TableCell>BTC/USDT</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );

    const region = screen.getByRole('region', { name: 'جدول نتایج' });
    const table = screen.getByRole('table');
    const selectedRow = screen.getByRole('row', { name: 'BTC/USDT' });

    expect(region).toHaveAttribute('dir', 'rtl');
    expect(table).toHaveAttribute('dir', 'rtl');
    expect(screen.getByRole('columnheader')).toHaveClass('px-3', 'sm:px-4', 'font-semibold');
    expect(screen.getByRole('cell')).toHaveClass('px-3', 'sm:px-4', 'align-middle');
    expect(selectedRow).toHaveClass(
      'focus-within:bg-app-hover',
      'data-[state=selected]:bg-app-accent-soft',
    );
  });
});
